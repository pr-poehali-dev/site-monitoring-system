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
MAX_DOCS_PER_RUN = 30
INITIAL_DELAY = 1.0
MAX_DELAY = 10.0

def handler(event: dict, context) -> dict:
    """API для парсинга документов с умными повторными попытками"""
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
            body = json.loads(event.get('body', '{}'))
            action = body.get('action', 'parse')
            
            if action == 'parse':
                sections = body.get('sections', ['postanovleniya'])
                years = body.get('years', [2025])
                result = parse_docs(conn, schema, sections, years)
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
        
        conn.close()
        return error_response('Неподдерживаемый метод', 400)
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return error_response(f'Критическая ошибка обработчика: {str(e)}', 500)


def parse_docs(conn, schema: str, sections: list, years: list) -> dict:
    """Парсинг по годам с продолжением после таймаутов"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    main_log_id = None
    try:
        main_log_id = log_create(cursor, schema, 'system', 'info', 
            f'🚀 ПАРСИНГ ЗАПУЩЕН | Разделов: {len(sections)} | Годов: {len(years)}')
        conn.commit()
    except Exception as e:
        cursor.close()
        raise Exception(f'Не удалось создать начальный лог: {str(e)}')
    
    stats = {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 0, 'years_completed': 0}
    t_start = time.time()
    
    # Обрабатываем по одному году за раз
    for section in sections:
        for year in years:
            try:
                elapsed = time.time() - t_start
                if elapsed > 25:
                    msg = f'⏱ ПАРСИНГ ПРИОСТАНОВЛЕН ПО ВРЕМЕНИ\nОбработано годов: {stats["years_completed"]}\nВремя: {int(elapsed*1000)}мс'
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
                    f'❌ Ошибка при парсинге {year} года: {str(ye)[:200]}')
                conn.commit()
    
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
    
    # Проверяем состояние парсинга
    cursor.execute(
        f"SELECT * FROM {schema}.parsing_state WHERE section = %s AND year = %s",
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
    elif state['status'] == 'completed':
        log_create(cursor, schema, section, 'info', 
            f'✓ Раздел {section_name}, год {year} уже обработан ранее')
        conn.commit()
        cursor.close()
        return {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 0}
    else:
        cursor.execute(
            f"UPDATE {schema}.parsing_state SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
            (section, year)
        )
        conn.commit()
    
    retry_count = state['retry_count']
    start_page = state.get('page', 1)
    
    log_create(cursor, schema, section, 'info', 
        f'📂 Парсинг: {section_name}, год {year} (попытка {retry_count + 1}/{MAX_RETRY}, стартовая страница: {start_page})')
    conn.commit()
    
    stats = {'new': 0, 'upd': 0, 'skip': 0, 'errors': 0, 'docs_processed': 0}
    t1 = time.time()
    
    year_suffix = f'{year}-god'
    base_section_url = urljoin(base_url, f"{paths[section]}{year_suffix}/")
    
    page = start_page
    delay = INITIAL_DELAY * (2 ** retry_count)
    if delay > MAX_DELAY:
        delay = MAX_DELAY
    
    try:
        while page <= 10 and stats['docs_processed'] < MAX_DOCS_PER_RUN:
            try:
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
                    break
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all('div', class_='docs__item')
                
                if not items:
                    log_create(cursor, schema, section, 'info', 
                        f'✓ Документов больше нет (страница {page}), год завершен')
                    conn.commit()
                    break
                
                pg_new = 0
                pg_upd = 0
                pg_skip = 0
                
                for item in items:
                    if stats['docs_processed'] >= MAX_DOCS_PER_RUN:
                        break
                    
                    try:
                        res = process_doc(cursor, schema, item, section, section_name, 
                                        base_url, url, s3, aws_key, headers)
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
                
                # Обновляем состояние после каждой страницы
                cursor.execute(
                    f"UPDATE {schema}.parsing_state SET page = %s, updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
                    (page, section, year)
                )
                conn.commit()
                
                # Проверяем наличие следующей страницы
                pageline = soup.find('div', class_='b-pageline')
                has_next = False
                if pageline:
                    nl = pageline.find('a', class_='pageline__next2')
                    if nl and nl.get('href'):
                        has_next = True
                
                if not has_next:
                    break
                
                page += 1
                
            except Exception as pe:
                stats['errors'] += 1
                log_create(cursor, schema, section, 'error', 
                    f'❌ Ошибка загрузки страницы {page}: {str(pe)[:150]}')
                conn.commit()
                raise
        
        # Успешно завершили
        cursor.execute(
            f"UPDATE {schema}.parsing_state SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE section = %s AND year = %s",
            (section, year)
        )
        conn.commit()
        
        dur = int((time.time() - t1) * 1000)
        msg = f"✅ ГОД ЗАВЕРШЕН: {year}\nНовых: {stats['new']}, Изменено: {stats['upd']}, Без изменений: {stats['skip']}, Ошибок: {stats['errors']}\nВремя: {dur}мс"
        log_create(cursor, schema, section, 'success', msg)
        conn.commit()
        
        cursor.close()
        return {
            'total_processed': stats['docs_processed'],
            'new_documents': stats['new'],
            'updated_documents': stats['upd'],
            'errors': stats['errors']
        }
        
    except Exception as e:
        # Ошибка - увеличиваем счетчик повторов
        new_retry = retry_count + 1
        
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
            log_create(cursor, schema, section, 'error', 
                f'💥 Парсинг года {year} провален после {MAX_RETRY} попыток: {str(e)[:200]}')
        
        conn.commit()
        cursor.close()
        raise


def process_doc(cursor, schema, item, section, section_name, base_url, page_url, s3, aws_key, headers):
    """Обработка документа с сохранением в S3"""
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
    
    fw = item.find('div', class_='docs__file-link-wrapper')
    if fw:
        fl = fw.find('a', attrs={'download': True})
        file_url = urljoin(base_url, fl.get('href', '')) if fl else urljoin(page_url, te.get('href', ''))
    else:
        file_url = urljoin(page_url, te.get('href', ''))
    
    fsize = 0
    fhash = ''
    fpath = ''
    cdn_url = ''
    
    try:
        fr = requests.get(file_url, headers=headers, timeout=8)
        fc = fr.content
        fsize = len(fc)
        fhash = hashlib.sha256(fc).hexdigest()
        
        if s3 and fsize > 0 and aws_key:
            fext = file_url.split('.')[-1].lower() if '.' in file_url else 'bin'
            fpath = f'docs/{section}/{doc_num or "unk"}_{fhash[:8]}.{fext}'
            s3.put_object(Bucket='files', Key=fpath, Body=fc, ContentType=get_ctype(fext))
            cdn_url = f'https://cdn.poehali.dev/projects/{aws_key}/bucket/{fpath}'
    except Exception:
        fhash = hashlib.sha256(file_url.encode()).hexdigest()
    
    cursor.execute(
        f"SELECT id, content_hash, title, file_size, changes_count FROM {schema}.documents WHERE url = %s",
        (file_url,)
    )
    ex = cursor.fetchone()
    
    if ex:
        if ex['content_hash'] != fhash or ex['file_size'] != fsize:
            cursor.execute(
                f"UPDATE {schema}.documents SET content_hash = %s, title = %s, file_size = %s, file_path = %s, file_cdn_url = %s, updated_at = CURRENT_TIMESTAMP, last_checked_at = CURRENT_TIMESTAMP, changes_count = changes_count + 1 WHERE id = %s",
                (fhash, full_title, fsize, fpath, cdn_url, ex['id'])
            )
            cursor.execute(
                f"INSERT INTO {schema}.document_changes (document_id, change_type, old_content_hash, new_content_hash, old_title, new_title, old_file_size, new_file_size) VALUES (%s, 'modified', %s, %s, %s, %s, %s, %s)",
                (ex['id'], ex['content_hash'], fhash, ex['title'], full_title, ex['file_size'], fsize)
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
            (full_title, file_url, section_name, pub_date, doc_num, doc_date, fhash, fsize, fpath, cdn_url)
        )
        did = cursor.fetchone()['id']
        cursor.execute(
            f"INSERT INTO {schema}.document_changes (document_id, change_type, new_content_hash, new_title, new_file_size) VALUES (%s, 'new', %s, %s, %s)",
            (did, fhash, full_title, fsize)
        )
        return 'new'


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
    """Telegram"""
    emoji = {'new': '🆕', 'modified': '✏️'}.get(change['change_type'], '📄')
    msg = f"{emoji} *{change['change_type'].upper()}*\n\n*{change['title'][:200]}*\nРаздел: {change['section']}\nДата: {change['detected_at'].strftime('%d.%m.%Y %H:%M')}\n[Открыть]({change['url']})"
    requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': cid, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True},
        timeout=10
    )


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