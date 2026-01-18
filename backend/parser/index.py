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

def handler(event: dict, context) -> dict:
    """API для парсинга документов"""
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
    """Парсинг документов"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    main_log_id = None
    try:
        main_log_id = log_create(cursor, schema, 'system', 'info', f'🚀 ПАРСИНГ ЗАПУЩЕН | Разделов: {len(sections)} | Годов: {len(years)}')
        conn.commit()
    except Exception as e:
        cursor.close()
        raise Exception(f'Не удалось создать начальный лог: {str(e)}')
    
    base_url = 'https://sychevka.admin-smolensk.ru'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    s3 = init_s3()
    
    stats = {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0, 'errors': 0}
    
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
    
    t_start = time.time()
    
    for section in sections:
        section_log_id = None
        try:
            section_log_id = log_create(cursor, schema, section, 'info', f'📂 Начинаем обработку раздела: {names[section]}')
            conn.commit()
            
            t1 = time.time()
            s_stats = {'new': 0, 'upd': 0, 'skip': 0, 'pages': 0, 'errors': 0}
            
            for year in years:
                try:
                    log_create(cursor, schema, section, 'info', f'📅 Обрабатываем документы за {year} год')
                    conn.commit()
                    
                    year_suffix = f'{year}-god'
                    base_section_url = urljoin(base_url, f"{paths[section]}{year_suffix}/")
                    
                    page = 1
                    yr_new = 0
                    yr_upd = 0
                    yr_skip = 0
                    
                    while page <= 10:
                        try:
                            url = base_section_url if page == 1 else urljoin(base_section_url, f"page/{page}/")
                            
                            log_create(cursor, schema, section, 'info', f'🌐 Загружаем страницу {page} из {base_section_url}')
                            conn.commit()
                            
                            time.sleep(0.8)
                            resp = requests.get(url, headers=headers, timeout=15)
                            
                            if resp.status_code != 200:
                                log_create(cursor, schema, section, 'warning', f'⚠️ Сервер вернул код {resp.status_code}, пропускаем остальные страницы года')
                                conn.commit()
                                break
                            
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            items = soup.find_all('div', class_='docs__item')
                            
                            if not items:
                                log_create(cursor, schema, section, 'info', f'✓ Больше документов на странице {page} нет, год завершен')
                                conn.commit()
                                break
                            
                            pg_new = 0
                            pg_upd = 0
                            pg_skip = 0
                            
                            for item in items:
                                try:
                                    res = process_doc(cursor, schema, item, section, names[section], base_url, url, s3, headers)
                                    if res == 'new':
                                        pg_new += 1
                                        yr_new += 1
                                        s_stats['new'] += 1
                                        stats['new_documents'] += 1
                                        stats['total_processed'] += 1
                                    elif res == 'upd':
                                        pg_upd += 1
                                        yr_upd += 1
                                        s_stats['upd'] += 1
                                        stats['updated_documents'] += 1
                                    elif res == 'skip':
                                        pg_skip += 1
                                        yr_skip += 1
                                        s_stats['skip'] += 1
                                except Exception as de:
                                    s_stats['errors'] += 1
                                    stats['errors'] += 1
                                    log_create(cursor, schema, section, 'error', f'❌ Ошибка при обработке документа: {str(de)[:150]}')
                                    conn.commit()
                            
                            s_stats['pages'] += 1
                            log_create(cursor, schema, section, 'info', f'📄 Обработана страница {page}: Добавлено {pg_new} новых, изменено {pg_upd}, без изменений {pg_skip}')
                            conn.commit()
                            
                            pageline = soup.find('div', class_='b-pageline')
                            has_next = False
                            if pageline:
                                nl = pageline.find('a', class_='pageline__next2')
                                if nl and nl.get('href'):
                                    has_next = True
                            
                            if not has_next:
                                log_create(cursor, schema, section, 'success', f'✅ Год {year} завершен: Добавлено {yr_new} новых документов, изменено {yr_upd}, без изменений {yr_skip}')
                                conn.commit()
                                break
                            
                            page += 1
                            
                        except Exception as pe:
                            s_stats['errors'] += 1
                            stats['errors'] += 1
                            log_create(cursor, schema, section, 'error', f'❌ Ошибка при загрузке страницы {page}: {str(pe)[:150]}')
                            conn.commit()
                            break
                    
                except Exception as ye:
                    s_stats['errors'] += 1
                    stats['errors'] += 1
                    log_create(cursor, schema, section, 'error', f'❌ Критическая ошибка при обработке {year} года: {str(ye)[:150]}')
                    conn.commit()
            
            dur = int((time.time() - t1) * 1000)
            msg = f"✅ РАЗДЕЛ ЗАВЕРШЕН\nДобавлено новых: {s_stats['new']}\nИзменено: {s_stats['upd']}\nБез изменений: {s_stats['skip']}\nОшибок: {s_stats['errors']}\nОбработано страниц: {s_stats['pages']}\nВремя: {dur}мс"
            if section_log_id:
                log_update(cursor, schema, section_log_id, 'success', msg, dur)
            conn.commit()
            
        except Exception as se:
            s_stats['errors'] += 1
            stats['errors'] += 1
            dur = int((time.time() - t1) * 1000) if 't1' in locals() else 0
            msg = f"💥 РАЗДЕЛ УПАЛ С ОШИБКОЙ\nОшибка: {str(se)[:200]}\nДобавлено: {s_stats['new']}, Изменено: {s_stats['upd']}, Ошибок: {s_stats['errors']}"
            if section_log_id:
                log_update(cursor, schema, section_log_id, 'error', msg, dur)
            log_create(cursor, schema, section, 'error', f'💥 Полный текст ошибки: {repr(se)[:300]}')
            conn.commit()
    
    total_dur = int((time.time() - t_start) * 1000)
    final_msg = f"🏁 ПАРСИНГ ЗАВЕРШЕН\n\nОбщая статистика:\n✅ Новых документов: {stats['new_documents']}\n🔄 Изменено документов: {stats['updated_documents']}\n❌ Ошибок: {stats['errors']}\n📊 Всего обработано: {stats['total_processed']}\n⏱ Время выполнения: {total_dur}мс"
    
    if main_log_id:
        log_update(cursor, schema, main_log_id, 'success', final_msg, total_dur)
    
    log_create(cursor, schema, 'system', 'success', final_msg)
    conn.commit()
    
    cursor.close()
    return stats


def process_doc(cursor, schema, item, section, section_name, base_url, page_url, s3, headers):
    """Обработка документа"""
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
    
    try:
        fr = requests.get(file_url, headers=headers, timeout=8)
        fc = fr.content
        fsize = len(fc)
        fhash = hashlib.sha256(fc).hexdigest()
        
        if s3 and fsize > 0:
            fext = file_url.split('.')[-1].lower() if '.' in file_url else 'bin'
            fpath = f'docs/{section}/{doc_num or "unk"}_{fhash[:8]}.{fext}'
            s3.put_object(Bucket='files', Key=fpath, Body=fc, ContentType=get_ctype(fext))
    except Exception:
        fhash = hashlib.sha256(file_url.encode()).hexdigest()
    
    cursor.execute(f"SELECT id, content_hash, title, file_size, changes_count FROM {schema}.documents WHERE url = %s", (file_url,))
    ex = cursor.fetchone()
    
    if ex:
        if ex['content_hash'] != fhash or ex['file_size'] != fsize:
            cursor.execute(
                f"UPDATE {schema}.documents SET content_hash = %s, title = %s, file_size = %s, file_path = %s, updated_at = CURRENT_TIMESTAMP, last_checked_at = CURRENT_TIMESTAMP, changes_count = changes_count + 1 WHERE id = %s",
                (fhash, full_title, fsize, fpath, ex['id'])
            )
            cursor.execute(
                f"INSERT INTO {schema}.document_changes (document_id, change_type, old_content_hash, new_content_hash, old_title, new_title, old_file_size, new_file_size) VALUES (%s, 'modified', %s, %s, %s, %s, %s, %s)",
                (ex['id'], ex['content_hash'], fhash, ex['title'], full_title, ex['file_size'], fsize)
            )
            return 'upd'
        else:
            cursor.execute(f"UPDATE {schema}.documents SET last_checked_at = CURRENT_TIMESTAMP WHERE id = %s", (ex['id'],))
            return 'skip'
    else:
        cursor.execute(
            f"INSERT INTO {schema}.documents (title, url, section, published_date, document_number, document_date, content_hash, file_size, file_path, changes_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0) RETURNING id",
            (full_title, file_url, section_name, pub_date, doc_num, doc_date, fhash, fsize, fpath)
        )
        did = cursor.fetchone()['id']
        cursor.execute(
            f"INSERT INTO {schema}.document_changes (document_id, change_type, new_content_hash, new_title, new_file_size) VALUES (%s, 'new', %s, %s, %s)",
            (did, fhash, full_title, fsize)
        )
        return 'new'


def extract_num(title: str) -> str:
    """Номер документа"""
    m = re.search(r'(\d+[-/]\w+)', title)
    return m.group(1) if m else None


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
            return boto3.client('s3', endpoint_url='https://bucket.poehali.dev', aws_access_key_id=ak, aws_secret_access_key=ase)
    except Exception:
        pass
    return None


def get_ctype(ext: str) -> str:
    """MIME"""
    types = {'pdf': 'application/pdf', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    return types.get(ext, 'application/octet-stream')


def monitor(conn, schema: str) -> dict:
    """Мониторинг"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(f"SELECT dc.id, dc.change_type, dc.detected_at, d.title, d.url, d.section FROM {schema}.document_changes dc JOIN {schema}.documents d ON dc.document_id = d.id WHERE dc.notified = false ORDER BY dc.detected_at DESC LIMIT 100")
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
                cursor.execute(f"UPDATE {schema}.document_changes SET notified = true WHERE id = %s", (ch['id'],))
                sent += 1
    
    cursor.close()
    return {'changes_found': len(changes), 'notifications_sent': sent}


def send_tg(token: str, cid: str, change: dict):
    """Telegram"""
    emoji = {'new': '🆕', 'modified': '✏️'}.get(change['change_type'], '📄')
    msg = f"{emoji} *{change['change_type'].upper()}*\n\n*{change['title'][:200]}*\nРаздел: {change['section']}\nДата: {change['detected_at'].strftime('%d.%m.%Y %H:%M')}\n[Открыть]({change['url']})"
    requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': cid, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}, timeout=10)


def log_create(cursor, schema: str, section: str, status: str, message: str) -> int:
    """Лог"""
    cursor.execute(f"INSERT INTO {schema}.parsing_logs (section, status, message) VALUES (%s, %s, %s) RETURNING id", (section, status, message))
    return cursor.fetchone()['id']


def log_update(cursor, schema: str, lid: int, status: str, message: str, dur: int):
    """Обновление лога"""
    cursor.execute(f"UPDATE {schema}.parsing_logs SET status = %s, message = %s, duration_ms = %s, finished_at = CURRENT_TIMESTAMP WHERE id = %s", (status, message, dur, lid))


def cors_response():
    return {'statusCode': 200, 'headers': {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'}, 'body': '', 'isBase64Encoded': False}


def success_response(data: dict) -> dict:
    return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps(data, ensure_ascii=False, default=str), 'isBase64Encoded': False}


def error_response(msg: str, sc: int = 400) -> dict:
    return {'statusCode': sc, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': msg}, ensure_ascii=False), 'isBase64Encoded': False}
