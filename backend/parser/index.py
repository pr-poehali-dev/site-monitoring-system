"""
🛡️ СИСТЕМА ЗАЩИТЫ ОТ ЗАВИСАНИЙ ПАРСЕРА

Многоуровневая защита для надёжной работы в cron без ручного вмешательства:

1. ⏱️ Таймаут-защита (20 сек вместо 30)
   - parse_single_year: max_execution_time = 20 сек
   - parse_docs: проверка каждые 20 сек
   - Запас 10 сек до hard timeout Cloud Function

2. 🔄 Автоматический сброс застрявших задач
   - continue_parsing: сбрасывает задачи со статусом 'running' > 5 мин
   - parse_single_year: проверка при старте, сброс если > 5 мин
   - Логирование причины зависания

3. 💾 Непрерывное сохранение прогресса
   - Обновление parsing_state.updated_at после каждой страницы
   - Статус 'partial' при достижении лимита времени
   - Автоматическое продолжение с последней страницы

4. 🚨 Обработка всех ошибок
   - try/except с сохранением last_error
   - Статус 'retry' до MAX_RETRY раз
   - Статус 'failed' после исчерпания попыток

Результат: парсер может упасть/зависнуть на любом этапе — следующий запуск автоматически подберёт и продолжит.
"""

import json
import os
import hashlib
import time
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
import boto3

MAX_RETRY = 3
MAX_DOCS_PER_RUN = 200
MAX_PAGES_PER_RUN = 50
INITIAL_DELAY = 1.5
MAX_DELAY = 10.0
MAX_ITERATIONS_PER_YEAR = 20  # Максимум 20 итераций на год (защита от бесконечных циклов)
EMPTY_PAGES_THRESHOLD = 3  # Сколько пустых страниц подряд = конец данных
STUCK_TASK_TIMEOUT = 300  # 5 минут = задача считается застрявшей
PARSER_BASE_URL = os.environ.get('PARSER_URL', 'https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c')

def handler(event: dict, context) -> dict:
    """API для парсинга документов с автоматическим восстановлением после сбоев"""
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return cors_response()
    
    db_url = os.environ.get('DATABASE_URL')
    schema = os.environ.get('MAIN_DB_SCHEMA', 'public')
    
    if not db_url:
        return error_response('DATABASE_URL не настроен', 500)
    
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        
        if method == 'POST':
            body_raw = event.get('body') or '{}'
            if isinstance(body_raw, dict):
                body = body_raw
            else:
                body_str = str(body_raw).strip()
                if not body_str or body_str == 'None':
                    body_str = '{}'
                body = json.loads(body_str)
            action = body.get('action', 'parse')
            
            if action == 'parse':
                sections = body.get('sections', ['postanovleniya'])
                years = body.get('years', [2025])
                force = body.get('force', False)
                result = parse_docs(conn, schema, sections, years, force)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'parse_single_year':
                section = body.get('section', 'postanovleniya')
                year = body.get('year', 2025)
                result = parse_single_year(conn, schema, section, year)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'monitor':
                result = monitor(conn, schema)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'continue_parsing':
                auto_loop = body.get('auto_loop', False)
                result = continue_parsing(conn, schema, auto_loop)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'download_files':
                limit = body.get('limit', 50)
                auto_loop = body.get('auto_loop', False)
                result = download_files(conn, schema, limit, auto_loop)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'get_download_stats':
                result = get_download_stats(conn, schema)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'reset_stuck':
                result = reset_stuck_tasks(conn, schema)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'find_relations':
                result = find_document_relations(conn, schema)
                conn.commit()
                conn.close()
                return success_response(result)
        
        conn.close()
        return error_response('Неподдерживаемый метод', 400)
        
    except Exception as e:
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                log_create(cursor, schema, 'system', 'error', 
                    f'💥 КРИТИЧЕСКАЯ ОШИБКА HANDLER: {str(e)[:500]}')
                conn.commit()
                conn.close()
            except:
                pass
        return error_response(f'Критическая ошибка обработчика: {str(e)}', 500)


def parse_docs(conn, schema: str, sections: list, years: list, force: bool = False) -> dict:
    """Парсинг по годам с продолжением после таймаутов"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Сортируем разделы по приоритету: programmy → rasporyazheniya → postanovleniya
    section_order = {'programmy': 1, 'rasporyazheniya': 2, 'postanovleniya': 3}
    sorted_sections = sorted(sections, key=lambda s: section_order.get(s, 99))
    
    # Сортируем годы от свежих к старым (2026, 2025, 2024...)
    sorted_years = sorted(years, reverse=True)
    
    # Создаём состояния для ВСЕХ комбинаций раздел+год заранее
    for section in sorted_sections:
        for year in sorted_years:
            cursor.execute(
                f"SELECT id FROM {schema}.parsing_state WHERE section = %s AND year = %s",
                (section, year)
            )
            existing = cursor.fetchone()
            if not existing:
                cursor.execute(
                    f"INSERT INTO {schema}.parsing_state (section, year, page, status, retry_count) VALUES (%s, %s, 1, 'pending', 0)",
                    (section, year)
                )
            elif force:
                # При force сбрасываем completed на pending
                cursor.execute(
                    f"UPDATE {schema}.parsing_state SET status = 'pending', page = 1, retry_count = 0 WHERE section = %s AND year = %s",
                    (section, year)
                )
    conn.commit()
    
    main_log_id = None
    try:
        start_msg = f'Разделов: {len(sorted_sections)} | Годов: {len(sorted_years)}\nПорядок: {", ".join(sorted_sections)}\nОт {sorted_years[0]} до {sorted_years[-1]} года'
        main_log_id = log_create(cursor, schema, 'system', 'info', 
            f'🚀 ПАРСИНГ ЗАПУЩЕН | {start_msg}')
        send_tg_parsing_event(cursor, schema, 'started', start_msg)
        conn.commit()
    except Exception as e:
        cursor.close()
        raise Exception(f'Не удалось создать начальный лог: {str(e)}')
    
    stats = {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 0, 'years_completed': 0}
    t_start = time.time()
    
    try:
        for section in sorted_sections:
            for year in sorted_years:
                try:
                    elapsed = time.time() - t_start
                    if elapsed > 20:
                        msg = f'⏱ ПАРСИНГ ПРИОСТАНОВЛЕН ПО ВРЕМЕНИ\nОбработано годов: {stats["years_completed"]}\nВремя: {int(elapsed*1000)}мс\nПричина: защита от timeout Cloud Function'
                        log_create(cursor, schema, 'system', 'warning', msg)
                        conn.commit()
                        break
                    
                    year_result = parse_single_year(conn, schema, section, year)
                    stats['total_processed'] += year_result.get('total_processed', 0)
                    stats['new_documents'] += year_result.get('new_documents', 0)
                    stats['updated_documents'] += year_result.get('updated_documents', 0)
                    stats['errors'] += year_result.get('errors', 0)
                    stats['years_completed'] += 1
                    conn.commit()
                    
                except Exception as ye:
                    stats['errors'] += 1
                    log_create(cursor, schema, section, 'error', 
                        f'❌ Ошибка при парсинге {year} года: {str(ye)[:500]}')
                    conn.commit()
    
    except Exception as global_err:
        log_create(cursor, schema, 'system', 'error', 
            f'💥 КРИТИЧЕСКАЯ ОШИБКА parse_docs: {str(global_err)[:500]}')
        conn.commit()
        stats['errors'] += 1
    
    total_dur = int((time.time() - t_start) * 1000)
    final_msg = f"""🏁 ПАРСИНГ ЗАВЕРШЕН

Статистика:
✅ Новых документов: {stats['new_documents']}
🔄 Изменено документов: {stats['updated_documents']}
📅 Обработано годов: {stats['years_completed']}
❌ Ошибок: {stats['errors']}
📊 Всего обработано: {stats['total_processed']}
⏱ Время: {total_dur}мс"""
    
    if main_log_id:
        log_update(cursor, schema, main_log_id, 'success', final_msg, total_dur)
    
    log_create(cursor, schema, 'system', 'success', final_msg)
    conn.commit()
    
    cursor.close()
    return stats


def parse_single_year(conn, schema: str, section: str, year: int) -> dict:
    """Парсинг одного года с retry-механизмом"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        base_url = 'https://sychevka.admin-smolensk.ru'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        s3 = init_s3()
        aws_key = os.environ.get('AWS_ACCESS_KEY_ID', '')
        
        paths = {
            'postanovleniya': '/docs/smolensk/postanovleniya/',
            'rasporyazheniya': '/docs/smolensk/rasporyazheniya/',
            'programmy': '/docs/municipalnye-programmy/'
        }
        
        names = {
            'postanovleniya': 'Постановления',
            'rasporyazheniya': 'Распоряжения',
            'programmy': 'Муниципальные программы'
        }
        
        section_name = names.get(section, section)
        
        cursor.execute(
            f"SELECT *, EXTRACT(EPOCH FROM (NOW() - updated_at)) as seconds_since_update FROM {schema}.parsing_state WHERE section = %s AND year = %s",
            (section, year)
        )
        state = cursor.fetchone()
        
        if not state:
            cursor.execute(
                f"INSERT INTO {schema}.parsing_state (section, year, status, retry_count) VALUES (%s, %s, 'running', 0) RETURNING *",
                (section, year)
            )
            state = cursor.fetchone()
            conn.commit()
        elif state['status'] == 'running' and state.get('seconds_since_update', 0) > STUCK_TASK_TIMEOUT:
            # Если задача в статусе 'running' более 5 минут — это зависание, сбрасываем
            minutes_stuck = int(state['seconds_since_update'] / 60)
            log_create(cursor, schema, section, 'warning', 
                f'⚠️ ОБНАРУЖЕНО ЗАВИСАНИЕ: Задача {section} {year} в статусе "running" {minutes_stuck} мин\n'
                f'Причина: функция не завершилась корректно (timeout или crash)\n'
                f'Действие: автоматический сброс в "pending" для повторной обработки')
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'pending', retry_count = 0, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (section, year)
            )
            conn.commit()
            # Перечитываем состояние после сброса
            cursor.execute(
                f"SELECT *, EXTRACT(EPOCH FROM (NOW() - updated_at)) as seconds_since_update FROM {schema}.parsing_state WHERE section = %s AND year = %s",
                (section, year)
            )
            state = cursor.fetchone()
        elif state['status'] == 'completed':
            log_create(cursor, schema, section, 'info', 
                f'✓ Раздел {section_name}, год {year} уже обработан ранее (все страницы загружены)')
            conn.commit()
            cursor.close()
            return {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 0}
        elif state['status'] == 'failed':
            log_create(cursor, schema, section, 'error', 
                f'❌ Раздел {section_name}, год {year} в статусе FAILED. Ошибка: {state.get("last_error", "неизвестно")}')
            conn.commit()
            cursor.close()
            return {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 1}
        elif state['status'] == 'partial':
            # Продолжаем парсинг со следующей страницы
            log_create(cursor, schema, section, 'info', 
                f'🔄 Продолжение парсинга {section_name}, год {year} со страницы {state.get("page", 1)}')
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (section, year)
            )
            conn.commit()
        else:
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (section, year)
            )
            conn.commit()
        
        retry_count = state['retry_count']
        start_page = state.get('page', 1)
        iteration_count = state.get('retry_count', 0)  # Используем retry_count как счётчик итераций
        
        # Защита от бесконечных итераций
        if iteration_count >= MAX_ITERATIONS_PER_YEAR:
            error_msg = f'Достигнут лимит итераций ({MAX_ITERATIONS_PER_YEAR}) для года {year}. Парсинг остановлен.'
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'failed', last_error = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (error_msg, section, year)
            )
            conn.commit()
            log_create(cursor, schema, section, 'error', f'❌ {error_msg}')
            conn.commit()
            cursor.close()
            return {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 1}
        
        log_create(cursor, schema, section, 'info', 
            f'📂 Парсинг: {section_name}, год {year} (итерация {iteration_count + 1}/{MAX_ITERATIONS_PER_YEAR}, стартовая страница: {start_page})')
        conn.commit()
        
        stats = {'new': 0, 'upd': 0, 'skip': 0, 'errors': 0, 'docs_processed': 0}
        t1 = time.time()
        
        year_suffix = f'{year}-god'
        base_section_url = urljoin(base_url, f"{paths[section]}{year_suffix}/")
        
        page = start_page
        delay = INITIAL_DELAY * (2 ** retry_count)
        if delay > MAX_DELAY:
            delay = MAX_DELAY
        
        # Для старых годов (2009-2015) минимальная задержка
        if year <= 2015:
            delay = 0.5
        
        # Максимальное время работы — 20 секунд (большой запас до таймаута Cloud Function 30 сек)
        # КРИТИЧНО: должно быть достаточно времени для сохранения статуса в БД перед hard timeout
        max_execution_time = 20
        
        empty_pages_count = 0  # Счётчик пустых страниц подряд
        year_fully_completed = False  # Флаг: год завершён полностью (все данные загружены)
        
        while page <= MAX_PAGES_PER_RUN and stats['docs_processed'] < MAX_DOCS_PER_RUN:
            # Проверяем время выполнения перед обработкой страницы
            elapsed = time.time() - t1
            if elapsed > max_execution_time:
                # Сохраняем текущую страницу (НЕ page+1) и статус 'partial'
                cursor.execute(
                    f"UPDATE {schema}.parsing_state SET page = %s, status = 'partial', retry_count = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                    (page, iteration_count + 1, section, year)
                )
                conn.commit()
                log_create(cursor, schema, section, 'warning', 
                    f'⏱ Лимит времени ({elapsed:.1f}с), статус PARTIAL. Продолжу со страницы {page} в следующей итерации.')
                conn.commit()
                
                # Автоматический рекурсивный вызов парсера
                try:
                    log_create(cursor, schema, section, 'info', 
                        f'🔄 Автозапуск следующей итерации для {section_name}, год {year}')
                    conn.commit()
                    cursor.close()
                    
                    # Вызываем парсер через HTTP (самого себя)
                    requests.post(PARSER_BASE_URL, 
                        json={'action': 'parse', 'sections': [section], 'years': [year]},
                        timeout=2  # Не ждём ответа, fire-and-forget
                    )
                except:
                    pass  # Игнорируем ошибки HTTP-вызова
                
                return {'total_processed': stats['docs_processed'], 'new_documents': stats['new'], 
                        'updated_documents': stats['upd'], 'errors': stats['errors'], 'status': 'partial'}
                break
            url = base_section_url if page == 1 else urljoin(base_section_url, f"page/{page}/")
            
            log_create(cursor, schema, section, 'info', 
                f'🌐 Загрузка страницы {page}, задержка {delay:.1f}с')
            conn.commit()
            
            time.sleep(delay)
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                log_create(cursor, schema, section, 'warning', 
                    f'⚠️ Код {resp.status_code} на странице {page}, завершаем год')
                conn.commit()
                year_fully_completed = True  # 404/ошибка = конец данных
                break
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all('div', class_='docs__item')
            
            # Проверка на редирект на главную (когда появляется таблица годов)
            if not items:
                # Ищем признак главной страницы архива (таблица с годами)
                year_table = soup.find('table')
                if year_table:
                    # Проверяем, есть ли в таблице ссылки на годы (2025-god, 2024-god и т.д.)
                    year_links = year_table.find_all('a', href=True)
                    has_year_links = any('-god' in link['href'] for link in year_links)
                    if has_year_links:
                        log_create(cursor, schema, section, 'info', 
                            f'⚠️ Редирект на главную архива (страница {page}), документы закончились')
                        conn.commit()
                        year_fully_completed = True  # Редирект = конец данных
                        break
                
                # Проверяем старый табличный формат (2009-2015)
                old_table = soup.find('div', class_='b-editor')
                if old_table:
                    table = old_table.find('table')
                    if table:
                        rows = table.find_all('tr')
                        # Пропускаем заголовок таблицы (первая строка)
                        items = [row for row in rows[1:] if row.find('a')]
                        if items:
                            log_create(cursor, schema, section, 'info', 
                                f'📊 Найден старый табличный формат: {len(items)} документов')
                            conn.commit()
            
            if not items:
                empty_pages_count += 1
                log_create(cursor, schema, section, 'info', 
                    f'⚪️ Пустая страница {page} ({empty_pages_count}/{EMPTY_PAGES_THRESHOLD})')
                conn.commit()
                
                # Если 3 пустые страницы подряд — данные закончились
                if empty_pages_count >= EMPTY_PAGES_THRESHOLD:
                    log_create(cursor, schema, section, 'info', 
                        f'✅ Данных больше нет ({EMPTY_PAGES_THRESHOLD} пустых страниц подряд), год завершен')
                    conn.commit()
                    year_fully_completed = True  # 3 пустые = конец данных
                    break
                
                # Пробуем следующую страницу (возможно пропуск в нумерации)
                page += 1
                continue
            
            # Если нашли документы — сбрасываем счётчик пустых страниц
            empty_pages_count = 0
            
            pg_new = 0
            pg_upd = 0
            pg_skip = 0
            
            for item in items:
                if stats['docs_processed'] >= MAX_DOCS_PER_RUN:
                    break
                
                try:
                    # Определяем формат документа (новый блочный или старый табличный)
                    is_table_row = item.name == 'tr'
                    
                    # Отключаем загрузку в S3 для всех годов (только метаданные)
                    skip_s3 = True
                    
                    if is_table_row:
                        res = process_doc_table(cursor, schema, item, section, section_name, 
                                        base_url, url, None, aws_key, headers, year)
                    else:
                        res = process_doc(cursor, schema, item, section, section_name, 
                                        base_url, url, None, aws_key, headers)
                    stats['docs_processed'] += 1
                    
                    if res == 'new':
                        pg_new += 1
                        stats['new'] += 1
                    elif res == 'upd':
                        pg_upd += 1
                        stats['upd'] += 1
                    elif res == 'skip':
                        pg_skip += 1
                        stats['skip'] += 1
                        
                except Exception as de:
                    stats['errors'] += 1
                    log_create(cursor, schema, section, 'error', 
                        f'❌ Ошибка обработки документа: {str(de)[:150]}')
                    conn.commit()
            
            log_create(cursor, schema, section, 'info', 
                f'📄 Страница {page}: Новых {pg_new}, изменено {pg_upd}, без изменений {pg_skip}')
            conn.commit()
            
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET page = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (page, section, year)
            )
            conn.commit()
            
            pageline = soup.find('div', class_='b-pageline')
            has_next = False
            if pageline:
                nl = pageline.find('a', class_='pageline__next2')
                if nl and nl.get('href'):
                    has_next = True
            
            if not has_next:
                year_fully_completed = True  # Нет кнопки "Далее" = конец данных
                break
            
            page += 1
        
        # Проверяем: завершён ли год ПОЛНОСТЬЮ или по таймауту/лимиту
        dur = int((time.time() - t1) * 1000)
        is_fully_completed = year_fully_completed  # Используем флаг, установленный в цикле
        
        if is_fully_completed:
            # ВСЕ данные загружены — финальный статус 'completed'
            msg = f"✅ ГОД ПОЛНОСТЬЮ ЗАВЕРШЁН: {year}\nНовых: {stats['new']}, Изменено: {stats['upd']}, Без изменений: {stats['skip']}, Ошибок: {stats['errors']}\nВремя: {dur}мс"
            log_create(cursor, schema, section, 'success', msg)
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (section, year)
            )
            conn.commit()
        else:
            # Данные могут быть ещё, но достигнут лимит документов/страниц
            msg = f"⚠️ ГОД ЧАСТИЧНО ЗАВЕРШЁН: {year} (достигнут лимит)\nНовых: {stats['new']}, Изменено: {stats['upd']}, Без изменений: {stats['skip']}, Ошибок: {stats['errors']}\nВремя: {dur}мс"
            log_create(cursor, schema, section, 'warning', msg)
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET page = %s, status = 'partial', retry_count = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (page + 1, iteration_count + 1, section, year)
            )
            conn.commit()
            
            # Автозапуск следующей итерации
            try:
                log_create(cursor, schema, section, 'info', 
                    f'🔄 Автозапуск следующей итерации для {section_name}, год {year}')
                conn.commit()
                requests.post(PARSER_BASE_URL, 
                    json={'action': 'parse', 'sections': [section], 'years': [year]},
                    timeout=2
                )
            except:
                pass
        
        # Проверяем, не завершились ли ВСЕ парсинги (только если год полностью завершён)
        if is_fully_completed:
            cursor.execute(f"SELECT COUNT(*) as pending FROM {schema}.parsing_state WHERE status NOT IN ('completed', 'failed')")
            pending = cursor.fetchone()['pending']
            
            if pending == 0:
                cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.parsing_state")
                total = cursor.fetchone()['total']
                
                cursor.execute(f"SELECT COUNT(*) as total_docs FROM {schema}.documents")
                total_docs = cursor.fetchone()['total_docs']
                
                cursor.execute(f"""
                    SELECT section, COUNT(*) as cnt 
                    FROM {schema}.documents 
                    GROUP BY section
                """)
                by_section = cursor.fetchall()
                section_stats = '\n'.join([f"• {row['section']}: {row['cnt']} док." for row in by_section])
                
                final_msg = f'Обработано задач: {total}\n\n📊 Собрано документов: {total_docs}\n\n{section_stats}'
                log_create(cursor, schema, 'system', 'success', 
                    f'🎉 ПАРСИНГ ПОЛНОСТЬЮ ЗАВЕРШЁН!\n{final_msg}')
                send_tg_parsing_event(cursor, schema, 'completed', final_msg, {'total_docs': total_docs})
                conn.commit()
        
        cursor.close()
        return {
            'total_processed': stats['docs_processed'],
            'new_documents': stats['new'],
            'updated_documents': stats['upd'],
            'errors': stats['errors']
        }
        
    except Exception as e:
        # Безопасная обработка stats (может не быть инициализирована при ошибке)
        if 'stats' not in locals():
            stats = {'docs_processed': 0, 'new': 0, 'upd': 0, 'skip': 0, 'errors': 0}
        stats['errors'] += 1
        
        # Безопасная обработка retry_count
        if 'retry_count' not in locals() or 'state' not in locals():
            retry_count = 0
        new_retry = retry_count + 1
        
        error_msg = f'💥 КРИТИЧЕСКАЯ ОШИБКА parse_single_year ({section}, {year}):\n{str(e)[:500]}'
        
        if new_retry < MAX_RETRY:
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'retry', retry_count = %s, last_error = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (new_retry, str(e)[:500], section, year)
            )
            log_create(cursor, schema, section, 'warning', 
                f'⚠️ Ошибка, будет повтор {new_retry}/{MAX_RETRY}: {str(e)[:200]}')
        else:
            cursor.execute(
                f"UPDATE {schema}.parsing_state SET status = 'failed', last_error = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                (str(e)[:500], section, year)
            )
            log_create(cursor, schema, section, 'error', error_msg)
        
        conn.commit()
        cursor.close()
        return {
            'total_processed': stats.get('docs_processed', 0),
            'new_documents': stats.get('new', 0),
            'updated_documents': stats.get('upd', 0),
            'errors': stats.get('errors', 1)
        }


def process_doc_table(cursor, schema, row, section, section_name, base_url, page_url, s3, aws_key, headers, year):
    """Обработка документа из табличного формата (2009-2015)"""
    cells = row.find_all('td')
    if len(cells) < 4:
        return 'skip'
    
    # Структура: [Номер, Дата, Название, Скачать, Актуальность]
    number_cell = cells[0]
    date_cell = cells[1]
    title_cell = cells[2]
    download_cell = cells[3]
    
    # Извлекаем основную ссылку на файл
    file_link = download_cell.find('a')
    if not file_link:
        return 'skip'
    
    file_url = urljoin(base_url, file_link.get('href', ''))
    
    # Извлекаем номер документа
    doc_num = number_cell.get_text(strip=True)
    
    # Извлекаем дату документа
    doc_date_text = date_cell.get_text(strip=True)
    doc_date = None
    if doc_date_text and '.' in doc_date_text:
        parts = doc_date_text.split('.')
        if len(parts) == 3:
            doc_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
    
    # Извлекаем название
    title = title_cell.get_text(strip=True)
    if not title:
        title = f"Документ №{doc_num} от {doc_date_text}"
    
    # URL документа = URL файла + уникальный идентификатор
    # (в старом формате один файл может использоваться для разных документов)
    unique_id = f"{file_url}#{doc_num}#{doc_date or 'nodate'}"
    doc_url = unique_id
    
    # Обрабатываем файл
    all_files = []
    fsize = 0
    fhash = ''
    fpath = ''
    cdn_url = ''
    
    # Если S3 отключен (для ускорения старых годов), используем URL как хеш
    if not s3:
        fhash = hashlib.sha256(file_url.encode()).hexdigest()
    else:
        try:
            fr = requests.get(file_url, headers=headers, timeout=8)
            fc = fr.content
            fsize = len(fc)
            fhash = hashlib.sha256(fc).hexdigest()
            
            if fsize > 0 and aws_key:
                fext = file_url.split('.')[-1].lower() if '.' in file_url else 'bin'
                fname_part = f"{doc_num or 'unk'}_main_{fhash[:8]}"
                fpath = f'docs/{section}/{fname_part}.{fext}'
                s3.put_object(Bucket='files', Key=fpath, Body=fc, ContentType=get_ctype(fext))
                cdn_url = f'https://cdn.poehali.dev/projects/{aws_key}/bucket/{fpath}'
        except Exception:
            fhash = hashlib.sha256(file_url.encode()).hexdigest()
    
    # Извлекаем имя файла из ссылки
    file_name = file_url.split('/')[-1] if '/' in file_url else 'document'
    
    all_files.append({
        'url': file_url,
        'name': file_name,
        'type': 'main',
        'size': fsize,
        'hash': fhash,
        'path': fpath,
        'cdn_url': cdn_url
    })
    
    if not all_files:
        return 'skip'
    
    main_file = all_files[0]
    
    cursor.execute(
        f"SELECT id, content_hash, title, file_size, changes_count, document_number, document_date, published_date FROM {schema}.documents WHERE url = %s",
        (doc_url,)
    )
    ex = cursor.fetchone()
    
    if ex:
        # Проверяем изменения только в значимых полях (контент, размер, заголовок)
        content_changed = ex['content_hash'] != main_file['hash']
        size_changed = ex['file_size'] != main_file['size']
        title_changed = ex['title'] != title
        
        has_changes = content_changed or size_changed or title_changed
        
        # Обновляем метаданные (номер, даты) без создания записи изменения
        metadata_changed = (
            ex['document_number'] != doc_num or
            str(ex['document_date']) != str(doc_date) or
            str(ex['published_date']) != str(doc_date)
        )
        
        if has_changes or metadata_changed:
            # Обновляем документ (увеличиваем changes_count только при реальных изменениях)
            if has_changes:
                cursor.execute(
                    f"UPDATE {schema}.documents SET content_hash = %s, title = %s, file_size = %s, file_path = %s, file_cdn_url = %s, document_number = %s, document_date = %s, published_date = %s, updated_at = CURRENT_TIMESTAMP, last_checked_at = CURRENT_TIMESTAMP, changes_count = changes_count + 1 WHERE id = %s",
                    (main_file['hash'], title, main_file['size'], main_file['path'], main_file['cdn_url'], doc_num, doc_date, doc_date, ex['id'])
                )
            else:
                # Только метаданные изменились - не увеличиваем changes_count
                cursor.execute(
                    f"UPDATE {schema}.documents SET document_number = %s, document_date = %s, published_date = %s, last_checked_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (doc_num, doc_date, doc_date, ex['id'])
                )
            
            # Записываем изменение только если есть значимые изменения (контент/размер/заголовок)
            if content_changed or size_changed or title_changed:
                cursor.execute(
                    f"INSERT INTO {schema}.document_changes (document_id, change_type, old_content_hash, new_content_hash, old_title, new_title, old_file_size, new_file_size) VALUES (%s, 'modified', %s, %s, %s, %s, %s, %s)",
                    (ex['id'], ex['content_hash'], main_file['hash'], ex['title'], title, ex['file_size'], main_file['size'])
                )
            
            cursor.execute(f"DELETE FROM {schema}.document_files WHERE document_id = %s", (ex['id'],))
            for f in all_files:
                cursor.execute(
                    f"INSERT INTO {schema}.document_files (document_id, file_url, file_type, file_name, file_size, file_path, file_cdn_url, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (ex['id'], f['url'], f['type'], f['name'], f['size'], f['path'], f['cdn_url'], f['hash'])
                )
            
            return 'upd'
        else:
            cursor.execute(
                f"UPDATE {schema}.documents SET last_checked_at = CURRENT_TIMESTAMP WHERE id = %s",
                (ex['id'],)
            )
            return 'skip'
    else:
        cursor.execute(
            f"INSERT INTO {schema}.documents (title, url, section, published_date, document_number, document_date, content_hash, file_size, file_path, file_cdn_url, changes_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0) RETURNING id",
            (title, doc_url, section_name, doc_date, doc_num, doc_date, main_file['hash'], main_file['size'], main_file['path'], main_file['cdn_url'])
        )
        did = cursor.fetchone()['id']
        
        for f in all_files:
            cursor.execute(
                f"INSERT INTO {schema}.document_files (document_id, file_url, file_type, file_name, file_size, file_path, file_cdn_url, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (did, f['url'], f['type'], f['name'], f['size'], f['path'], f['cdn_url'], f['hash'])
            )
        
        return 'new'


def process_doc(cursor, schema, item, section, section_name, base_url, page_url, s3, aws_key, headers):
    """Обработка документа с сохранением в S3 (поддержка множественных файлов)"""
    te = item.find('a', class_='docs__title')
    if not te:
        return 'skip'
    
    title = te.get_text(strip=True)
    doc_num = extract_num(title)
    doc_date = extract_date(title)
    
    inner = item.find('div', class_='docs__inner-title')
    full_title = f"{title}: {inner.get_text(strip=True)}" if inner else title
    
    de = item.find('div', class_='docs__date')
    pub_date = None
    if de:
        dt = de.get_text(strip=True).split()[0]
        if dt and '.' in dt:
            p = dt.split('.')
            if len(p) == 3:
                pub_date = f"{p[2]}-{p[1]}-{p[0]}"
    
    doc_url = urljoin(page_url, te.get('href', ''))
    
    file_wrappers = item.find_all('div', class_='docs__file')
    all_files = []
    
    for idx, fw in enumerate(file_wrappers):
        fl = fw.find('a', attrs={'download': True})
        if not fl:
            continue
        
        file_url = urljoin(base_url, fl.get('href', ''))
        file_name = fl.get_text(strip=True)
        file_type = 'main' if idx == 0 else 'appendix'
        
        fsize = 0
        fhash = ''
        fpath = ''
        cdn_url = ''
        
        # Если S3 отключен, используем URL как хеш (не скачиваем файл)
        if not s3:
            fhash = hashlib.sha256(file_url.encode()).hexdigest()
        else:
            try:
                fr = requests.get(file_url, headers=headers, timeout=8)
                fc = fr.content
                fsize = len(fc)
                fhash = hashlib.sha256(fc).hexdigest()
                
                if fsize > 0 and aws_key:
                    fext = file_url.split('.')[-1].lower() if '.' in file_url else 'bin'
                    fname_part = f"{doc_num or 'unk'}_{file_type}_{fhash[:8]}"
                    fpath = f'docs/{section}/{fname_part}.{fext}'
                    s3.put_object(Bucket='files', Key=fpath, Body=fc, ContentType=get_ctype(fext))
                    cdn_url = f'https://cdn.poehali.dev/projects/{aws_key}/bucket/{fpath}'
            except Exception:
                fhash = hashlib.sha256(file_url.encode()).hexdigest()
        
        all_files.append({
            'url': file_url,
            'name': file_name,
            'type': file_type,
            'size': fsize,
            'hash': fhash,
            'path': fpath,
            'cdn_url': cdn_url
        })
    
    if not all_files:
        return 'skip'
    
    main_file = all_files[0]
    
    cursor.execute(
        f"SELECT id, content_hash, title, file_size, changes_count, document_number, document_date, published_date FROM {schema}.documents WHERE url = %s",
        (doc_url,)
    )
    ex = cursor.fetchone()
    
    if ex:
        # Проверяем изменения только в значимых полях (контент, размер, заголовок)
        content_changed = ex['content_hash'] != main_file['hash']
        size_changed = ex['file_size'] != main_file['size']
        title_changed = ex['title'] != full_title
        
        has_changes = content_changed or size_changed or title_changed
        
        # Обновляем метаданные (номер, даты) без создания записи изменения
        metadata_changed = (
            ex['document_number'] != doc_num or
            str(ex['document_date']) != str(doc_date) or
            str(ex['published_date']) != str(pub_date)
        )
        
        if has_changes or metadata_changed:
            # Обновляем документ (увеличиваем changes_count только при реальных изменениях)
            if has_changes:
                cursor.execute(
                    f"UPDATE {schema}.documents SET content_hash = %s, title = %s, file_size = %s, file_path = %s, file_cdn_url = %s, document_number = %s, document_date = %s, published_date = %s, updated_at = CURRENT_TIMESTAMP, last_checked_at = CURRENT_TIMESTAMP, changes_count = changes_count + 1 WHERE id = %s",
                    (main_file['hash'], full_title, main_file['size'], main_file['path'], main_file['cdn_url'], doc_num, doc_date, pub_date, ex['id'])
                )
            else:
                # Только метаданные изменились - не увеличиваем changes_count
                cursor.execute(
                    f"UPDATE {schema}.documents SET document_number = %s, document_date = %s, published_date = %s, last_checked_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (doc_num, doc_date, pub_date, ex['id'])
                )
            
            # Записываем изменение только если есть значимые изменения (контент/размер/заголовок)
            if content_changed or size_changed or title_changed:
                cursor.execute(
                    f"INSERT INTO {schema}.document_changes (document_id, change_type, old_content_hash, new_content_hash, old_title, new_title, old_file_size, new_file_size) VALUES (%s, 'modified', %s, %s, %s, %s, %s, %s)",
                    (ex['id'], ex['content_hash'], main_file['hash'], ex['title'], full_title, ex['file_size'], main_file['size'])
                )
            
            cursor.execute(f"DELETE FROM {schema}.document_files WHERE document_id = %s", (ex['id'],))
            for f in all_files:
                cursor.execute(
                    f"INSERT INTO {schema}.document_files (document_id, file_url, file_type, file_name, file_size, file_path, file_cdn_url, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (ex['id'], f['url'], f['type'], f['name'], f['size'], f['path'], f['cdn_url'], f['hash'])
                )
            
            return 'upd'
        else:
            cursor.execute(
                f"UPDATE {schema}.documents SET last_checked_at = CURRENT_TIMESTAMP WHERE id = %s",
                (ex['id'],)
            )
            return 'skip'
    else:
        cursor.execute(
            f"INSERT INTO {schema}.documents (title, url, section, published_date, document_number, document_date, content_hash, file_size, file_path, file_cdn_url, changes_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0) RETURNING id",
            (full_title, doc_url, section_name, pub_date, doc_num, doc_date, main_file['hash'], main_file['size'], main_file['path'], main_file['cdn_url'])
        )
        did = cursor.fetchone()['id']
        
        for f in all_files:
            cursor.execute(
                f"INSERT INTO {schema}.document_files (document_id, file_url, file_type, file_name, file_size, file_path, file_cdn_url, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (did, f['url'], f['type'], f['name'], f['size'], f['path'], f['cdn_url'], f['hash'])
            )
        
        return 'new'


def download_files(conn, schema: str, limit: int = 50, auto_loop: bool = False) -> dict:
    """Загрузка файлов из БД в S3 с автоматическим продолжением"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    s3 = init_s3()
    aws_key = os.environ.get('AWS_ACCESS_KEY_ID', '')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    if not s3 or not aws_key:
        return {'error': 'S3 не настроен', 'downloaded': 0}
    
    # Проверяем, есть ли ещё файлы для загрузки
    cursor.execute(f"""
        SELECT COUNT(*) as pending
        FROM {schema}.document_files
        WHERE file_cdn_url IS NULL OR file_cdn_url = ''
    """)
    pending_count = cursor.fetchone()['pending']
    
    if pending_count == 0:
        log_create(cursor, schema, 'download', 'success', 
            '✅ Все файлы уже загружены в S3')
        conn.commit()
        cursor.close()
        return {'status': 'completed', 'downloaded': 0, 'pending': 0, 'message': 'Все файлы загружены'}
    
    # Находим файлы без CDN URL (ещё не загружены в S3)
    cursor.execute(f"""
        SELECT df.id, df.document_id, df.file_url, df.file_type, d.section, d.document_number
        FROM {schema}.document_files df
        JOIN {schema}.documents d ON d.id = df.document_id
        WHERE df.file_cdn_url IS NULL OR df.file_cdn_url = ''
        ORDER BY df.id
        LIMIT %s
    """, (limit,))
    files = cursor.fetchall()
    
    if not files:
        cursor.close()
        return {'status': 'completed', 'downloaded': 0, 'pending': 0}
    
    log_create(cursor, schema, 'download', 'info', 
        f'📥 Загрузка {len(files)} файлов в S3 (осталось {pending_count})')
    conn.commit()
    
    stats = {'downloaded': 0, 'errors': 0, 'skipped': 0}
    t_start = time.time()
    max_execution_time = 25
    
    for f in files:
        # Проверяем лимит времени выполнения
        elapsed = time.time() - t_start
        if elapsed > max_execution_time:
            log_create(cursor, schema, 'download', 'warning', 
                f'⏱ Достигнут лимит времени ({elapsed:.1f}с), загружено {stats["downloaded"]} файлов')
            conn.commit()
            break
        
        try:
            file_url = f['file_url']
            file_type = f['file_type']
            section = f['section']
            doc_num = f['document_number'] or 'unk'
            
            # Скачиваем файл
            resp = requests.get(file_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                stats['errors'] += 1
                continue
            
            content = resp.content
            fsize = len(content)
            fhash = hashlib.sha256(content).hexdigest()
            
            # Загружаем в S3
            fext = file_url.split('.')[-1].lower() if '.' in file_url else 'bin'
            fname_part = f"{doc_num}_{file_type}_{fhash[:8]}"
            fpath = f'docs/{section}/{fname_part}.{fext}'
            
            s3.put_object(
                Bucket='files',
                Key=fpath,
                Body=content,
                ContentType=get_ctype(fext)
            )
            
            cdn_url = f'https://cdn.poehali.dev/projects/{aws_key}/bucket/{fpath}'
            
            # Обновляем запись в БД
            cursor.execute(f"""
                UPDATE {schema}.document_files 
                SET file_size = %s, file_path = %s, file_cdn_url = %s, content_hash = %s
                WHERE id = %s
            """, (fsize, fpath, cdn_url, fhash, f['id']))
            
            # Обновляем главный документ (если это основной файл)
            if file_type == 'main':
                cursor.execute(f"""
                    UPDATE {schema}.documents
                    SET file_size = %s, file_path = %s, file_cdn_url = %s, content_hash = %s
                    WHERE id = %s
                """, (fsize, fpath, cdn_url, fhash, f['document_id']))
            
            stats['downloaded'] += 1
            conn.commit()
            
        except Exception as e:
            stats['errors'] += 1
            log_create(cursor, schema, 'download', 'error', 
                f'❌ Ошибка загрузки файла {f["file_url"][:100]}: {str(e)[:200]}')
            conn.commit()
    
    # Проверяем, остались ли ещё файлы
    cursor.execute(f"""
        SELECT COUNT(*) as pending
        FROM {schema}.document_files
        WHERE file_cdn_url IS NULL OR file_cdn_url = ''
    """)
    remaining = cursor.fetchone()['pending']
    
    duration_ms = int((time.time() - t_start) * 1000)
    
    if remaining > 0:
        log_create(cursor, schema, 'download', 'info', 
            f'✅ Загружено {stats["downloaded"]} файлов за {duration_ms}мс (ошибок: {stats["errors"]}). Осталось: {remaining}')
        conn.commit()
        
        # Если включен auto_loop и есть ещё файлы, запускаем следующую итерацию
        if auto_loop and stats['downloaded'] > 0:
            try:
                requests.post(
                    PARSER_BASE_URL,
                    json={'action': 'download_files', 'limit': limit, 'auto_loop': True},
                    timeout=2
                )
            except:
                pass
        
        cursor.close()
        return {
            'status': 'in_progress',
            'downloaded': stats['downloaded'],
            'errors': stats['errors'],
            'pending': remaining,
            'auto_loop': auto_loop
        }
    else:
        log_create(cursor, schema, 'download', 'success', 
            f'🎉 ВСЕ ФАЙЛЫ ЗАГРУЖЕНЫ! Загружено {stats["downloaded"]} файлов за {duration_ms}мс (ошибок: {stats["errors"]})')
        send_tg_parsing_event(cursor, schema, 'completed', 
            f'Загрузка файлов в S3 завершена!\nВсего загружено файлов: {stats["downloaded"]}\nОшибок: {stats["errors"]}')
        conn.commit()
        cursor.close()
        return {
            'status': 'completed',
            'downloaded': stats['downloaded'],
            'errors': stats['errors'],
            'pending': 0,
            'message': '🎉 Все файлы загружены в S3!'
        }


def get_download_stats(conn, schema: str) -> dict:
    """Статистика загрузки файлов"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total_files,
            COUNT(CASE WHEN file_cdn_url IS NOT NULL AND file_cdn_url != '' THEN 1 END) as downloaded,
            COUNT(CASE WHEN file_cdn_url IS NULL OR file_cdn_url = '' THEN 1 END) as pending
        FROM {schema}.document_files
    """)
    stats = cursor.fetchone()
    
    cursor.close()
    return dict(stats)


def extract_num(title: str) -> str:
    """Номер документа"""
    # Ищем паттерны: "642 от", "1196-р", "123/п" и т.д.
    patterns = [
        r'№?\s*(\d+[-/]\w+)',  # 1196-р, 123/п
        r'№?\s*(\d+)\s+от',     # 642 от
        r'Постановление\s+(\d+)',  # Постановление 642
        r'Распоряжение\s+(\d+)'     # Распоряжение 1196
    ]
    for pattern in patterns:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def extract_date(title: str) -> str:
    """Дата из названия"""
    m = re.search(r'(\d{2}\.\d{2}\.\d{4})', title)
    if m:
        d = m.group(1).split('.')
        return f"{d[2]}-{d[1]}-{d[0]}"
    return None


def init_s3():
    """S3"""
    try:
        ak = os.environ.get('AWS_ACCESS_KEY_ID')
        ase = os.environ.get('AWS_SECRET_ACCESS_KEY')
        if ak and ase:
            return boto3.client('s3', endpoint_url='https://bucket.poehali.dev', 
                              aws_access_key_id=ak, aws_secret_access_key=ase)
    except Exception:
        pass
    return None


def get_ctype(ext: str) -> str:
    """MIME"""
    types = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    return types.get(ext, 'application/octet-stream')


def continue_parsing(conn, schema: str, auto_loop: bool = False) -> dict:
    """Автоматическое продолжение незавершённых парсингов с приоритетом"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 🔧 ШАГ 1: АВТОМАТИЧЕСКИЙ СБРОС ЗАСТРЯВШИХ ЗАДАЧ
    # Находим задачи со статусом 'running' которые обновлялись более STUCK_TASK_TIMEOUT секунд назад
    cursor.execute(f"""
        SELECT section, year, page, status, updated_at,
               EXTRACT(EPOCH FROM (NOW() - updated_at)) as seconds_stuck
        FROM {schema}.parsing_state 
        WHERE status = 'running' 
        AND updated_at < NOW() - INTERVAL '{STUCK_TASK_TIMEOUT} seconds'
    """)
    stuck_tasks = cursor.fetchall()
    
    if stuck_tasks:
        for task in stuck_tasks:
            section = task['section']
            year = task['year']
            page = task['page']
            minutes_stuck = int(task['seconds_stuck'] / 60)
            
            # Сбрасываем статус на 'pending'
            cursor.execute(f"""
                UPDATE {schema}.parsing_state 
                SET status = 'pending', retry_count = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE section = %s AND year = %s
            """, (section, year))
            
            log_create(cursor, schema, 'system', 'warning', 
                f'⚠️ АВТО-СБРОС: Задача {section} {year} год застряла на {minutes_stuck} мин (страница {page})\n'
                f'Причина: статус "running" без обновлений более 5 минут\n'
                f'Действие: сброс в "pending" для повторной обработки')
        
        conn.commit()
        log_create(cursor, schema, 'system', 'info', 
            f'🔄 Автоматически сброшено застрявших задач: {len(stuck_tasks)}')
        conn.commit()
    
    # Приоритет разделов: programmy → rasporyazheniya → postanovleniya
    section_priority = {'programmy': 1, 'rasporyazheniya': 2, 'postanovleniya': 3}
    
    # Ищем незавершённые задачи с приоритетом: сначала по разделам, потом по году (от свежих)
    cursor.execute(f"""
        SELECT section, year, page, status, updated_at,
               EXTRACT(EPOCH FROM (NOW() - updated_at)) as seconds_since_update
        FROM {schema}.parsing_state 
        WHERE status IN ('running', 'retry', 'pending', 'partial')
        ORDER BY 
            CASE section 
                WHEN 'programmy' THEN 1 
                WHEN 'rasporyazheniya' THEN 2 
                WHEN 'postanovleniya' THEN 3 
                ELSE 4 
            END,
            year DESC
        LIMIT 1
    """)
    state = cursor.fetchone()
    
    if not state:
        # Проверяем, все ли задачи завершены
        cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.parsing_state WHERE status = 'completed'")
        completed_count = cursor.fetchone()['total']
        
        cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.parsing_state")
        total_count = cursor.fetchone()['total']
        
        if completed_count > 0 and completed_count == total_count:
            cursor.execute(f"SELECT COUNT(*) as total_docs FROM {schema}.documents")
            total_docs = cursor.fetchone()['total_docs']
            
            cursor.execute(f"""
                SELECT section, COUNT(*) as cnt 
                FROM {schema}.documents 
                GROUP BY section
            """)
            by_section = cursor.fetchall()
            section_stats = '\n'.join([f"• {row['section']}: {row['cnt']} док." for row in by_section])
            
            final_msg = f'Обработано задач: {total_count}\n\n📊 Собрано документов: {total_docs}\n\n{section_stats}'
            log_create(cursor, schema, 'system', 'success', 
                f'🎉 ПАРСИНГ ПОЛНОСТЬЮ ЗАВЕРШЕН!\n{final_msg}')
            send_tg_parsing_event(cursor, schema, 'completed', final_msg, {'total_docs': total_docs})
            conn.commit()
            cursor.close()
            return {'status': 'all_completed', 'message': '🎉 Парсинг полностью завершён!', 'total_tasks': total_count}
        
        cursor.close()
        return {'status': 'no_pending', 'message': 'Нет незавершённых парсингов'}
    
    section = state['section']
    year = state['year']
    page = state['page']
    
    log_create(cursor, schema, 'system', 'info', 
        f'🔄 Автопродолжение (приоритет: {section_priority.get(section, 99)}): {section}, {year} год, страница {page}')
    conn.commit()
    
    result = parse_single_year(conn, schema, section, year)
    
    # Если включён режим авто-цикла, запускаем следующую итерацию
    if auto_loop:
        cursor2 = conn.cursor(cursor_factory=RealDictCursor)
        cursor2.execute(f"SELECT COUNT(*) as pending FROM {schema}.parsing_state WHERE status IN ('running', 'retry', 'pending', 'partial')")
        pending = cursor2.fetchone()['pending']
        cursor2.close()
        
        if pending > 0:
            try:
                requests.post(
                    PARSER_BASE_URL,
                    json={'action': 'continue_parsing', 'auto_loop': True},
                    timeout=2
                )
            except:
                pass
    
    cursor.close()
    return {
        'status': 'continued',
        'section': section,
        'year': year,
        'page': page,
        'result': result
    }


def reset_stuck_tasks(conn, schema: str) -> dict:
    """Сброс застрявших задач со статусом 'running' более 10 минут"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Находим задачи со статусом 'running' которые обновлялись более 10 минут назад
    cursor.execute(f"""
        SELECT section, year, page, status, updated_at 
        FROM {schema}.parsing_state 
        WHERE status = 'running' 
        AND updated_at < NOW() - INTERVAL '10 minutes'
    """)
    stuck_tasks = cursor.fetchall()
    
    if not stuck_tasks:
        log_create(cursor, schema, 'system', 'info', '✅ Застрявших задач не обнаружено')
        conn.commit()
        cursor.close()
        return {'status': 'ok', 'reset_count': 0, 'message': 'Застрявших задач нет'}
    
    reset_count = 0
    for task in stuck_tasks:
        section = task['section']
        year = task['year']
        page = task['page']
        
        # Сбрасываем статус на 'pending'
        cursor.execute(f"""
            UPDATE {schema}.parsing_state 
            SET status = 'pending', retry_count = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE section = %s AND year = %s
        """, (section, year))
        
        log_create(cursor, schema, 'system', 'warning', 
            f'🔄 Сброшена застрявшая задача: {section} {year} год (страница {page})')
        reset_count += 1
    
    conn.commit()
    cursor.close()
    
    msg = f'Сброшено застрявших задач: {reset_count}'
    return {'status': 'reset', 'reset_count': reset_count, 'message': msg}


def monitor(conn, schema: str) -> dict:
    """Мониторинг"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        f"SELECT dc.id, dc.change_type, dc.detected_at, d.title, d.url, d.section FROM {schema}.document_changes dc JOIN {schema}.documents d ON dc.document_id = d.id WHERE dc.notified = false ORDER BY dc.detected_at DESC LIMIT 100"
    )
    changes = cursor.fetchall()
    
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    cid = ''
    sent = 0
    
    if changes:
        cursor.execute(f"SELECT value FROM {schema}.monitoring_settings WHERE key = 'telegram_chat_id'")
        r = cursor.fetchone()
        cid = r['value'] if r else ''
        
        if token and cid:
            for ch in changes:
                send_tg(token, cid, ch)
                cursor.execute(
                    f"UPDATE {schema}.document_changes SET notified = true WHERE id = %s",
                    (ch['id'],)
                )
                sent += 1
    
    cursor.close()
    return {'changes_found': len(changes), 'notifications_sent': sent}


def send_tg(token: str, cid: str, change: dict):
    """Telegram уведомление об изменении документа"""
    emoji = {'new': '🆕', 'modified': '✏️'}.get(change['change_type'], '📄')
    msg = f"{emoji} *{change['change_type'].upper()}*\n\n*{change['title'][:200]}*\nРаздел: {change['section']}\nДата: {change['detected_at'].strftime('%d.%m.%Y %H:%M')}\n[Открыть]({change['url']})"
    requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': cid, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True},
        timeout=10
    )


def send_tg_parsing_event(cursor, schema: str, event_type: str, message: str, stats: dict = None):
    """Отправка уведомления о событии парсинга в Telegram"""
    try:
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not token:
            return
        
        cursor.execute(f"SELECT value FROM {schema}.monitoring_settings WHERE key = 'telegram_chat_id'")
        r = cursor.fetchone()
        cid = r['value'] if r else ''
        
        if not cid:
            return
        
        if event_type == 'started':
            emoji = '🚀'
            title = 'ПАРСИНГ ЗАПУЩЕН'
        elif event_type == 'completed':
            emoji = '🎉'
            title = 'ПАРСИНГ ЗАВЕРШЁН'
        elif event_type == 'year_completed':
            emoji = '✅'
            title = 'ГОД ЗАВЕРШЁН'
        else:
            emoji = 'ℹ️'
            title = 'СОБЫТИЕ'
        
        msg = f"{emoji} *{title}*\n\n{message}"
        
        if stats:
            msg += f"\n\n📊 *Статистика:*"
            if 'new' in stats:
                msg += f"\n🆕 Новых: {stats['new']}"
            if 'upd' in stats:
                msg += f"\n✏️ Изменено: {stats['upd']}"
            if 'skip' in stats:
                msg += f"\n⏭ Без изменений: {stats['skip']}"
            if 'total_docs' in stats:
                msg += f"\n📄 Всего документов: {stats['total_docs']}"
            if 'errors' in stats and stats['errors'] > 0:
                msg += f"\n❌ Ошибок: {stats['errors']}"
        
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': cid, 'text': msg, 'parse_mode': 'Markdown'},
            timeout=10
        )
    except Exception:
        pass


def log_create(cursor, schema: str, section: str, status: str, message: str) -> int:
    """Лог"""
    cursor.execute(
        f"INSERT INTO {schema}.parsing_logs (section, status, message) VALUES (%s, %s, %s) RETURNING id",
        (section, status, message)
    )
    return cursor.fetchone()['id']


def log_update(cursor, schema: str, lid: int, status: str, message: str, dur: int):
    """Обновление лога"""
    cursor.execute(
        f"UPDATE {schema}.parsing_logs SET status = %s, message = %s, duration_ms = %s, finished_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, message, dur, lid)
    )


def find_document_relations(conn, schema: str) -> dict:
    """Поиск связей между документами через анализ файлов (полная логика из link-finder)"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Константы для парсинга (из link-finder)
    VERSION_KEYWORDS = [
        r'утратившим\s+силу', r'утрачива[ею]т\s+силу', r'считать\s+утратившим',
        r'признать\s+утратившим', r'внести\s+изменени[яе]', r'внесены\s+изменения',
        r'вносятся\s+изменения', r'с\s+изменениями,\s+внесенными',
        r'дополнить', r'дополняется', r'дополнен',
        r'изложить\s+в\s+новой\s+редакции', r'в\s+редакции\s+постановлени',
        r'действует\s+в\s+редакции', r'отменить', r'отменяется', r'отменен',
        r'заменить', r'исключить'
    ]
    
    RELATED_KEYWORDS = [
        r'в\s+соответствии\s+с', r'на\s+основании', r'руководствуясь',
        r'в\s+целях', r'согласно', r'во\s+исполнение'
    ]
    
    DOCUMENT_PATTERNS = [
        (r'от\s+(\d{2}\.\d{2}\.\d{4})\s+г(?:ода)?\.?\s+№\s*(\d+)', 'date_first'),
        (r'от\s+(\d{2}\.\d{2}\.\d{4})\s+г(?:ода)?\.?\s+N\s*(\d+)', 'date_first'),
        (r'постановлени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        (r'постановлени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        (r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        (r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    ]
    
    EXCLUSION_PHRASES = [
        r'правительств[ао]\s+смоленской\s+области',
        r'администраци[ия]\s+смоленской\s+области',
        r'правительств[ао]\s+российской\s+федерации',
        r'правительств[ао]\s+рф',
    ]
    
    # Получаем ОБЩУЮ статистику (всего документов с файлами)
    cursor.execute(f"""
        SELECT COUNT(*) as total
        FROM {schema}.documents
        WHERE file_cdn_url IS NOT NULL
          AND (is_phantom IS NULL OR is_phantom = FALSE)
          AND (file_cdn_url LIKE '%.docx' OR file_cdn_url LIKE '%.doc' OR file_cdn_url LIKE '%.pdf')
    """)
    total_all = cursor.fetchone()['total']
    
    # Получаем количество УЖЕ обработанных (документы с хотя бы одной связью)
    cursor.execute(f"""
        SELECT COUNT(DISTINCT source_document_id) as cnt
        FROM (
            SELECT source_document_id FROM {schema}.document_relations
            UNION
            SELECT source_document_id FROM {schema}.related_documents
        ) t
    """)
    already_processed = cursor.fetchone()['cnt']
    
    remaining = total_all - already_processed
    
    t_start = time.time()
    log_create(cursor, schema, 'system', 'info', 
        f'🔗 ПОИСК СВЯЗЕЙ ЗАПУЩЕН\n📊 Всего документов: {total_all}\n✅ Обработано ранее: {already_processed}\n⏳ Осталось обработать: {remaining}')
    conn.commit()
    
    # Если все уже обработаны - выходим
    if remaining == 0:
        log_create(cursor, schema, 'system', 'success', '✅ Все документы уже обработаны!')
        conn.commit()
        cursor.close()
        return {
            'status': 'completed',
            'total_documents': total_all,
            'already_processed': already_processed,
            'remaining': 0,
            'message': 'Все документы уже обработаны'
        }
    
    # Получаем документы БЕЗ связей (еще не обработанные) - ПАКЕТ 50 шт
    cursor.execute(f"""
        SELECT d.id, d.title, d.document_number, d.document_date, d.section, d.file_cdn_url
        FROM {schema}.documents d
        LEFT JOIN {schema}.document_relations dr ON dr.source_document_id = d.id
        LEFT JOIN {schema}.related_documents rd ON rd.source_document_id = d.id
        WHERE d.file_cdn_url IS NOT NULL
          AND (d.is_phantom IS NULL OR d.is_phantom = FALSE)
          AND (d.file_cdn_url LIKE '%.docx' OR d.file_cdn_url LIKE '%.doc' OR d.file_cdn_url LIKE '%.pdf')
          AND dr.id IS NULL
          AND rd.id IS NULL
        ORDER BY d.document_date DESC NULLS LAST
        LIMIT 50
    """)
    documents = cursor.fetchall()
    
    batch_size = len(documents)
    log_create(cursor, schema, 'system', 'info', f'📦 Обрабатываем пакет: {batch_size} документов')
    conn.commit()
    
    total_versions = 0
    total_related = 0
    total_phantoms = 0
    processed = 0
    
    for doc in documents:
        try:
            # Скачиваем файл
            response = requests.get(doc['file_cdn_url'], timeout=30)
            if response.status_code != 200:
                continue
            
            file_bytes = response.content
            file_ext = doc['file_cdn_url'].split('.')[-1].lower()
            
            # Парсим файл
            text = ""
            if file_ext == 'docx':
                try:
                    from docx import Document
                    from io import BytesIO
                    docx_doc = Document(BytesIO(file_bytes))
                    for i, para in enumerate(docx_doc.paragraphs):
                        if i >= 25:
                            break
                        text += para.text + "\n"
                except:
                    continue
            elif file_ext == 'doc':
                try:
                    text = file_bytes.decode('cp1251', errors='ignore')
                    text = ''.join(c if c.isprintable() or c in '\n\r\t' else ' ' for c in text)
                    text = text[:5000]  # Первые 5000 символов
                except:
                    continue
            elif file_ext == 'pdf':
                try:
                    import PyPDF2
                    from io import BytesIO
                    pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
                    for i in range(min(3, len(pdf.pages))):
                        text += pdf.pages[i].extract_text() + "\n"
                except:
                    continue
            
            if not text:
                continue
            
            # Ищем ВЕРСИИ
            version_refs = []
            for keyword_pattern in VERSION_KEYWORDS:
                for match in re.finditer(keyword_pattern, text, re.IGNORECASE):
                    start_pos = max(0, match.start() - 200)
                    end_pos = min(len(text), match.end() + 300)
                    context = text[start_pos:end_pos]
                    
                    for pattern, order in DOCUMENT_PATTERNS:
                        for ref_match in re.finditer(pattern, context, re.IGNORECASE):
                            try:
                                if order == 'date_first':
                                    date_str, number = ref_match.group(1), ref_match.group(2)
                                else:
                                    number, date_str = ref_match.group(1), ref_match.group(2)
                                
                                # Валидация
                                if len(number) > 5 or not number.isdigit():
                                    continue
                                
                                parts = date_str.split('.')
                                if len(parts) != 3:
                                    continue
                                
                                ref_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                version_refs.append((number, ref_date))
                            except:
                                continue
            
            # Ищем СВЯЗАННЫЕ
            related_refs = []
            for keyword_pattern in RELATED_KEYWORDS:
                for match in re.finditer(keyword_pattern, text, re.IGNORECASE):
                    start_pos = max(0, match.start() - 50)
                    end_pos = min(len(text), match.end() + 500)
                    context = text[start_pos:end_pos]
                    
                    for pattern, order in DOCUMENT_PATTERNS:
                        for ref_match in re.finditer(pattern, context, re.IGNORECASE):
                            try:
                                if order == 'date_first':
                                    date_str, number = ref_match.group(1), ref_match.group(2)
                                else:
                                    number, date_str = ref_match.group(1), ref_match.group(2)
                                
                                if len(number) > 5 or not number.isdigit():
                                    continue
                                
                                parts = date_str.split('.')
                                if len(parts) != 3:
                                    continue
                                
                                ref_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                related_refs.append((number, ref_date))
                            except:
                                continue
            
            # Убираем дубликаты
            version_refs = list(set(version_refs))
            related_refs = list(set(related_refs))
            
            # Исключаем из related те что в versions
            version_keys = set(version_refs)
            related_refs = [r for r in related_refs if r not in version_keys]
            
            # Создаем связи ВЕРСИЙ
            for ref_num, ref_date in version_refs:
                cursor.execute(f"""
                    SELECT id FROM {schema}.documents
                    WHERE document_number = %s AND document_date = %s AND id != %s
                    LIMIT 1
                """, (ref_num, ref_date, doc['id']))
                
                target_doc = cursor.fetchone()
                if target_doc:
                    cursor.execute(f"""
                        SELECT 1 FROM {schema}.document_relations
                        WHERE source_document_id = %s AND target_document_id = %s
                    """, (doc['id'], target_doc['id']))
                    if not cursor.fetchone():
                        cursor.execute(f"""
                            INSERT INTO {schema}.document_relations 
                            (source_document_id, target_document_id, relation_type)
                            VALUES (%s, %s, 'previous_version')
                        """, (doc['id'], target_doc['id']))
                        total_versions += 1
            
            # Создаем связи СВЯЗАННЫХ
            for ref_num, ref_date in related_refs:
                cursor.execute(f"""
                    SELECT id FROM {schema}.documents
                    WHERE document_number = %s AND document_date = %s AND id != %s
                    LIMIT 1
                """, (ref_num, ref_date, doc['id']))
                
                target_doc = cursor.fetchone()
                if target_doc:
                    cursor.execute(f"""
                        SELECT 1 FROM {schema}.related_documents
                        WHERE source_document_id = %s AND related_document_id = %s
                    """, (doc['id'], target_doc['id']))
                    if not cursor.fetchone():
                        cursor.execute(f"""
                            INSERT INTO {schema}.related_documents 
                            (source_document_id, related_document_id, relation_type, context)
                            VALUES (%s, %s, 'reference', %s)
                        """, (doc['id'], target_doc['id'], text[:200]))
                        total_related += 1
            
            processed += 1
            if processed % 50 == 0:
                conn.commit()
                log_create(cursor, schema, 'system', 'info', 
                    f'📦 {processed}/{total_docs} | Версий: {total_versions} | Связанных: {total_related}')
                conn.commit()
                
        except Exception as e:
            continue
    
    conn.commit()
    
    duration_ms = int((time.time() - t_start) * 1000)
    
    # Обновляем статистику после обработки пакета
    cursor.execute(f"""
        SELECT COUNT(DISTINCT source_document_id) as cnt
        FROM (
            SELECT source_document_id FROM {schema}.document_relations
            UNION
            SELECT source_document_id FROM {schema}.related_documents
        ) t
    """)
    total_processed_now = cursor.fetchone()['cnt']
    remaining_now = total_all - total_processed_now
    
    # Общая статистика по ВСЕМ связям (не только из текущего пакета)
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.document_relations")
    total_versions_db = cursor.fetchone()['cnt']
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.related_documents")
    total_related_db = cursor.fetchone()['cnt']
    
    summary = f"""📦 ПАКЕТ ОБРАБОТАН

📊 Обработано в пакете: {processed}/{batch_size}
📎 Версий найдено: {total_versions}
🔗 Связанных найдено: {total_related}
⏱ Время: {duration_ms}мс

🎯 ОБЩИЙ ПРОГРЕСС:
✅ Обработано всего: {total_processed_now}/{total_all} ({int(total_processed_now*100/total_all)}%)
⏳ Осталось: {remaining_now}
📎 Всего версий в БД: {total_versions_db}
🔗 Всего связей в БД: {total_related_db}"""
    
    log_create(cursor, schema, 'system', 'info', summary)
    conn.commit()
    
    # Если ещё есть необработанные - запускаем следующий пакет
    if remaining_now > 0:
        log_create(cursor, schema, 'system', 'info', 
            f'🔄 Автозапуск следующего пакета (осталось {remaining_now} документов)...')
        conn.commit()
        
        try:
            requests.post(
                PARSER_BASE_URL,
                json={'action': 'find_relations'},
                timeout=2
            )
        except:
            pass  # Игнорируем ошибки HTTP-вызова
        
        cursor.close()
        return {
            'status': 'in_progress',
            'batch_processed': processed,
            'batch_versions': total_versions,
            'batch_related': total_related,
            'total_documents': total_all,
            'total_processed': total_processed_now,
            'remaining': remaining_now,
            'progress_percent': int(total_processed_now*100/total_all),
            'duration_ms': duration_ms
        }
    else:
        # Все документы обработаны!
        final_summary = f"""🎉 ПОИСК СВЯЗЕЙ ПОЛНОСТЬЮ ЗАВЕРШЁН!

📊 Обработано документов: {total_all}
📎 Найдено версий: {total_versions_db}
🔗 Найдено связей: {total_related_db}
⏱ Общее время последнего пакета: {duration_ms}мс"""
        
        log_create(cursor, schema, 'system', 'success', final_summary)
        conn.commit()
        
        cursor.close()
        return {
            'status': 'completed',
            'total_documents': total_all,
            'total_processed': total_processed_now,
            'total_versions': total_versions_db,
            'total_related': total_related_db,
            'duration_ms': duration_ms
        }


def cors_response():
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': '',
        'isBase64Encoded': False
    }


def success_response(data: dict) -> dict:
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data, ensure_ascii=False, default=str),
        'isBase64Encoded': False
    }


def error_response(msg: str, sc: int = 400) -> dict:
    return {
        'statusCode': sc,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': msg}, ensure_ascii=False),
        'isBase64Encoded': False
    }