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
    """
    API для парсинга документов с сайта Сычевской администрации.
    Поддерживает разовый и регулярный мониторинг документов.
    """
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
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
    
    db_url = os.environ.get('DATABASE_URL')
    schema = os.environ.get('MAIN_DB_SCHEMA', 'public')
    
    if not db_url:
        return error_response('DATABASE_URL не настроен', 500)
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        
        if method == 'POST':
            body = json.loads(event.get('body', '{}'))
            action = body.get('action', 'parse')
            
            if action == 'parse':
                sections = body.get('sections', ['postanovleniya', 'rasporyazheniya', 'programmy'])
                years = body.get('years', list(range(2009, 2026)))
                result = parse_documents(conn, schema, sections, years)
                conn.commit()
                conn.close()
                return success_response(result)
            
            elif action == 'monitor':
                result = monitor_changes(conn, schema)
                conn.commit()
                conn.close()
                return success_response(result)
        
        conn.close()
        return error_response('Неподдерживаемый метод или action', 400)
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return error_response(f'Ошибка: {str(e)}', 500)


def parse_documents(conn, schema: str, sections: list, years: list) -> dict:
    """Парсинг документов с сайта и сохранение в БД"""
    base_url = 'https://sychevka.admin-smolensk.ru'
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    stats = {
        'total_processed': 0,
        'new_documents': 0,
        'updated_documents': 0,
        'sections': {}
    }
    
    section_paths = {
        'postanovleniya': '/docs/smolensk/postanovleniya/',
        'rasporyazheniya': '/docs/smolensk/rasporyazheniya/',
        'programmy': '/docs/municipalnye-programmy/'
    }
    
    section_names = {
        'postanovleniya': 'Постановления',
        'rasporyazheniya': 'Распоряжения',
        'programmy': 'Муниципальные программы'
    }
    
    for section in sections:
        log_id = create_log(cursor, schema, section, 'info', 'Начало парсинга раздела')
        start_time = time.time()
        section_stats = {'new': 0, 'updated': 0, 'errors': 0}
        
        try:
            for year in years:
                year_suffix = f'{year}-god' if year >= 2009 else str(year)
                base_section_url = urljoin(base_url, f"{section_paths[section]}{year_suffix}/")
                
                page = 1
                while True:
                    if page == 1:
                        section_url = base_section_url
                    else:
                        section_url = urljoin(base_section_url, f"page/{page}/")
                    
                    try:
                        response = requests.get(section_url, timeout=30)
                        if response.status_code != 200:
                            break
                        
                        soup = BeautifulSoup(response.text, 'html.parser')
                        doc_items = soup.find_all('div', class_='docs__item')
                        
                        if not doc_items:
                            break
                        
                        has_next_page = False
                        pageline = soup.find('div', class_='b-pageline')
                        if pageline:
                            next_link = pageline.find('a', class_='pageline__next2')
                            if next_link and next_link.get('href'):
                                has_next_page = True
                        
                        for item in doc_items:
                            try:
                                title_elem = item.find('a', class_='docs__title')
                                if not title_elem:
                                    continue
                                
                                title = title_elem.get_text(strip=True)
                                doc_page_url = urljoin(section_url, title_elem.get('href', ''))
                                
                                inner_title_elem = item.find('div', class_='docs__inner-title')
                                if inner_title_elem:
                                    full_title = f"{title}: {inner_title_elem.get_text(strip=True)}"
                                else:
                                    full_title = title
                                
                                date_elem = item.find('div', class_='docs__date')
                                pub_date = None
                                if date_elem:
                                    date_text = date_elem.get_text(strip=True)
                                    try:
                                        pub_date = datetime.strptime(date_text.split()[0], '%d.%m.%Y').date()
                                    except:
                                        pub_date = None
                                
                                file_link_elem = item.find('a', class_='docs__file-link')
                                if file_link_elem:
                                    file_url = urljoin(base_url, file_link_elem.get('href', ''))
                                else:
                                    file_url = doc_page_url
                                
                                try:
                                    doc_response = requests.get(file_url, timeout=15)
                                    content_hash = hashlib.sha256(doc_response.content).hexdigest()
                                except:
                                    content_hash = hashlib.sha256(file_url.encode()).hexdigest()
                                
                                cursor.execute(
                                    f"SELECT id, content_hash FROM {schema}.documents WHERE url = %s",
                                    (file_url,)
                                )
                                existing = cursor.fetchone()
                                
                                if existing:
                                    if existing['content_hash'] != content_hash:
                                        cursor.execute(
                                            f"""UPDATE {schema}.documents 
                                               SET content_hash = %s, title = %s, updated_at = CURRENT_TIMESTAMP, 
                                                   last_checked_at = CURRENT_TIMESTAMP
                                               WHERE id = %s""",
                                            (content_hash, full_title, existing['id'])
                                        )
                                        
                                        cursor.execute(
                                            f"""INSERT INTO {schema}.document_changes 
                                               (document_id, change_type, old_content_hash, new_content_hash)
                                               VALUES (%s, 'modified', %s, %s)""",
                                            (existing['id'], existing['content_hash'], content_hash)
                                        )
                                        section_stats['updated'] += 1
                                    else:
                                        cursor.execute(
                                            f"UPDATE {schema}.documents SET last_checked_at = CURRENT_TIMESTAMP WHERE id = %s",
                                            (existing['id'],)
                                        )
                                else:
                                    cursor.execute(
                                        f"""INSERT INTO {schema}.documents 
                                           (title, url, section, published_date, content_hash)
                                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                                        (full_title, file_url, section_names[section], pub_date, content_hash)
                                    )
                                    doc_id = cursor.fetchone()['id']
                                    
                                    cursor.execute(
                                        f"""INSERT INTO {schema}.document_changes 
                                           (document_id, change_type, new_content_hash)
                                           VALUES (%s, 'new', %s)""",
                                        (doc_id, content_hash)
                                    )
                                    section_stats['new'] += 1
                                
                                stats['total_processed'] += 1
                                
                            except Exception as e:
                                section_stats['errors'] += 1
                                continue
                        
                        if not has_next_page:
                            break
                        
                        page += 1
                
                    except Exception as e:
                        break
            
            duration_ms = int((time.time() - start_time) * 1000)
            message = f"Парсинг завершён. Новых: {section_stats['new']}, изменённых: {section_stats['updated']}, ошибок: {section_stats['errors']}"
            update_log(cursor, schema, log_id, 'success', message, duration_ms)
            
            stats['new_documents'] += section_stats['new']
            stats['updated_documents'] += section_stats['updated']
            stats['sections'][section] = section_stats
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            update_log(cursor, schema, log_id, 'error', f"Ошибка: {str(e)}", duration_ms)
    
    cursor.close()
    return stats


def monitor_changes(conn, schema: str) -> dict:
    """Мониторинг изменений и отправка уведомлений"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute(f"""
        SELECT dc.id, dc.change_type, dc.detected_at, d.title, d.url, d.section
        FROM {schema}.document_changes dc
        JOIN {schema}.documents d ON dc.document_id = d.id
        WHERE dc.notified = false
        ORDER BY dc.detected_at DESC
    """)
    
    changes = cursor.fetchall()
    
    telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = ''
    notifications_sent = 0
    
    if changes:
        cursor.execute(f"SELECT value FROM {schema}.monitoring_settings WHERE key = 'telegram_chat_id'")
        result = cursor.fetchone()
        chat_id = result['value'] if result else ''
        
        if telegram_token and chat_id:
            for change in changes:
                send_telegram_notification(telegram_token, chat_id, change)
                cursor.execute(
                    f"UPDATE {schema}.document_changes SET notified = true WHERE id = %s",
                    (change['id'],)
                )
                notifications_sent += 1
    
    cursor.close()
    return {
        'changes_found': len(changes),
        'notifications_sent': notifications_sent
    }


def send_telegram_notification(token: str, chat_id: str, change: dict):
    """Отправка уведомления в Telegram"""
    change_emoji = {'new': '🆕', 'modified': '✏️', 'deleted': '❌'}
    emoji = change_emoji.get(change['change_type'], '📄')
    
    message = f"{emoji} *{change['change_type'].upper()}*\n\n"
    message += f"*{change['title']}*\n"
    message += f"Раздел: {change['section']}\n"
    message += f"Дата: {change['detected_at'].strftime('%d.%m.%Y %H:%M')}\n"
    message += f"[Открыть документ]({change['url']})"
    
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            },
            timeout=10
        )
    except:
        pass


def create_log(cursor, schema: str, section: str, status: str, message: str) -> int:
    """Создание записи в логах"""
    cursor.execute(
        f"""INSERT INTO {schema}.parsing_logs (section, status, message)
           VALUES (%s, %s, %s) RETURNING id""",
        (section, status, message)
    )
    return cursor.fetchone()['id']


def update_log(cursor, schema: str, log_id: int, status: str, message: str, duration_ms: int):
    """Обновление записи в логах"""
    cursor.execute(
        f"""UPDATE {schema}.parsing_logs 
           SET status = %s, message = %s, duration_ms = %s, finished_at = CURRENT_TIMESTAMP
           WHERE id = %s""",
        (status, message, duration_ms, log_id)
    )


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


def error_response(message: str, status_code: int = 400) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message}, ensure_ascii=False),
        'isBase64Encoded': False
    }