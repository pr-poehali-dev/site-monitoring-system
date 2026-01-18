import json
import os
import hashlib
import time
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor

def handler(event: dict, context) -> dict:
    """API для парсинга документов"""
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return cors_response()
    
    db_url = os.environ.get('DATABASE_URL')
    schema = os.environ.get('MAIN_DB_SCHEMA', 'public')
    
    if not db_url:
        return error_response('DATABASE_URL не настроен', 500)
    
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    
    if method == 'POST':
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', 'parse')
        
        if action == 'parse':
            sections = body.get('sections', ['postanovleniya', 'rasporyazheniya', 'programmy'])
            years = body.get('years', list(range(2009, 2026)))
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


def parse_docs(conn, schema: str, sections: list, years: list) -> dict:
    """Парсинг документов"""
    base_url = 'https://sychevka.admin-smolensk.ru'
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    stats = {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0}
    
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
    
    for section in sections:
        log_id = log_create(cursor, schema, section, 'info', f'🚀 Начало: {names[section]}')
        t1 = time.time()
        s_stats = {'new': 0, 'updated': 0, 'pages': 0}
        
        for year in years:
            year_suffix = f'{year}-god'
            base_url_section = urljoin(base_url, f"{paths[section]}{year_suffix}/")
            log_create(cursor, schema, section, 'info', f'📅 Год {year}')
            
            page = 1
            year_docs = 0
            
            while page <= 20:
                url = base_url_section if page == 1 else urljoin(base_url_section, f"page/{page}/")
                log_create(cursor, schema, section, 'info', f'🌐 Страница {page}')
                
                time.sleep(1.2)
                resp = requests.get(url, headers=headers, timeout=30)
                
                if resp.status_code != 200:
                    log_create(cursor, schema, section, 'warning', f'⚠️ Статус {resp.status_code}')
                    break
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all('div', class_='docs__item')
                
                if not items:
                    log_create(cursor, schema, section, 'info', f'✅ Год {year}: {year_docs} док, {page-1} стр')
                    break
                
                log_create(cursor, schema, section, 'info', f'📄 Найдено {len(items)}')
                
                for item in items:
                    t_elem = item.find('a', class_='docs__title')
                    if not t_elem:
                        continue
                    
                    title = t_elem.get_text(strip=True)
                    inner = item.find('div', class_='docs__inner-title')
                    full_title = f"{title}: {inner.get_text(strip=True)}" if inner else title
                    
                    d_elem = item.find('div', class_='docs__date')
                    pub_date = None
                    if d_elem:
                        d_text = d_elem.get_text(strip=True).split()[0]
                        if d_text and '.' in d_text:
                            p = d_text.split('.')
                            if len(p) == 3:
                                pub_date = f"{p[2]}-{p[1]}-{p[0]}"
                    
                    f_wrap = item.find('div', class_='docs__file-link-wrapper')
                    if f_wrap:
                        f_link = f_wrap.find('a', attrs={'download': True})
                        file_url = urljoin(base_url, f_link.get('href', '')) if f_link else urljoin(url, t_elem.get('href', ''))
                    else:
                        file_url = urljoin(url, t_elem.get('href', ''))
                    
                    c_hash = hashlib.sha256(file_url.encode()).hexdigest()
                    
                    cursor.execute(f"SELECT id, content_hash FROM {schema}.documents WHERE url = %s", (file_url,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        if existing['content_hash'] != c_hash:
                            cursor.execute(f"UPDATE {schema}.documents SET content_hash = %s, title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (c_hash, full_title, existing['id']))
                            cursor.execute(f"INSERT INTO {schema}.document_changes (document_id, change_type, old_content_hash, new_content_hash) VALUES (%s, 'modified', %s, %s)", (existing['id'], existing['content_hash'], c_hash))
                            s_stats['updated'] += 1
                            stats['updated_documents'] += 1
                            log_create(cursor, schema, section, 'info', f'🔄 Обновлен: {full_title[:50]}')
                    else:
                        cursor.execute(f"INSERT INTO {schema}.documents (title, url, section, published_date, content_hash) VALUES (%s, %s, %s, %s, %s) RETURNING id", (full_title, file_url, names[section], pub_date, c_hash))
                        doc_id = cursor.fetchone()['id']
                        cursor.execute(f"INSERT INTO {schema}.document_changes (document_id, change_type, new_content_hash) VALUES (%s, 'new', %s)", (doc_id, c_hash))
                        s_stats['new'] += 1
                        stats['new_documents'] += 1
                        year_docs += 1
                        stats['total_processed'] += 1
                
                s_stats['pages'] += 1
                
                pageline = soup.find('div', class_='b-pageline')
                has_next = False
                if pageline:
                    next_l = pageline.find('a', class_='pageline__next2')
                    if next_l and next_l.get('href'):
                        has_next = True
                
                if not has_next:
                    log_create(cursor, schema, section, 'info', f'✅ Год {year}: {year_docs} док, {page} стр')
                    break
                
                page += 1
        
        dur_ms = int((time.time() - t1) * 1000)
        msg = f"🎉 Завершено! Новых: {s_stats['new']}, изменено: {s_stats['updated']}, страниц: {s_stats['pages']}"
        log_update(cursor, schema, log_id, 'success', msg, dur_ms)
    
    cursor.close()
    return stats


def monitor(conn, schema: str) -> dict:
    """Мониторинг"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(f"SELECT dc.id, dc.change_type, dc.detected_at, d.title, d.url, d.section FROM {schema}.document_changes dc JOIN {schema}.documents d ON dc.document_id = d.id WHERE dc.notified = false ORDER BY dc.detected_at DESC LIMIT 100")
    changes = cursor.fetchall()
    
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = ''
    sent = 0
    
    if changes:
        cursor.execute(f"SELECT value FROM {schema}.monitoring_settings WHERE key = 'telegram_chat_id'")
        r = cursor.fetchone()
        chat_id = r['value'] if r else ''
        
        if token and chat_id:
            for ch in changes:
                send_tg(token, chat_id, ch)
                cursor.execute(f"UPDATE {schema}.document_changes SET notified = true WHERE id = %s", (ch['id'],))
                sent += 1
    
    cursor.close()
    return {'changes_found': len(changes), 'notifications_sent': sent}


def send_tg(token: str, chat_id: str, change: dict):
    """Telegram"""
    emoji = {'new': '🆕', 'modified': '✏️'}.get(change['change_type'], '📄')
    msg = f"{emoji} *{change['change_type'].upper()}*\n\n*{change['title'][:200]}*\nРаздел: {change['section']}\nДата: {change['detected_at'].strftime('%d.%m.%Y %H:%M')}\n[Открыть]({change['url']})"
    requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}, timeout=10)


def log_create(cursor, schema: str, section: str, status: str, message: str) -> int:
    """Лог"""
    cursor.execute(f"INSERT INTO {schema}.parsing_logs (section, status, message) VALUES (%s, %s, %s) RETURNING id", (section, status, message))
    return cursor.fetchone()['id']


def log_update(cursor, schema: str, log_id: int, status: str, message: str, duration_ms: int):
    """Обновление лога"""
    cursor.execute(f"UPDATE {schema}.parsing_logs SET status = %s, message = %s, duration_ms = %s, finished_at = CURRENT_TIMESTAMP WHERE id = %s", (status, message, duration_ms, log_id))


def cors_response():
    return {'statusCode': 200, 'headers': {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'}, 'body': '', 'isBase64Encoded': False}


def success_response(data: dict) -> dict:
    return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps(data, ensure_ascii=False, default=str), 'isBase64Encoded': False}


def error_response(message: str, status_code: int = 400) -> dict:
    return {'statusCode': status_code, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'error': message}, ensure_ascii=False), 'isBase64Encoded': False}
