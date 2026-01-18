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
    """API для парсинга документов с сайта Сычевской администрации"""
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
    
    conn = None
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    
    if method == 'POST':
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', 'parse')
        
        if action == 'parse':
            sections = body.get('sections', ['postanovleniya'])
            years = body.get('years', list(range(2024, 2026)))
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


def parse_documents(conn, schema: str, sections: list, years: list) -> dict:
    """Парсинг документов с сайта"""
    base_url = 'https://sychevka.admin-smolensk.ru'
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    stats = {'total_processed': 0, 'new_documents': 0, 'updated_documents': 0}
    
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
        log_id = create_log(cursor, schema, section, 'info', f'Начало парсинга')
        
        for year in years:
            year_suffix = f'{year}-god'
            base_section_url = urljoin(base_url, f"{section_paths[section]}{year_suffix}/")
            
            create_log(cursor, schema, section, 'info', f'Год {year}: {base_section_url}')
            
            page = 1
            response = requests.get(base_section_url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            doc_items = soup.find_all('div', class_='docs__item')
            
            create_log(cursor, schema, section, 'info', f'Найдено {len(doc_items)} документов')
            
            for item in doc_items:
                title_elem = item.find('a', class_='docs__title')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                file_url = urljoin(base_section_url, title_elem.get('href', ''))
                content_hash = hashlib.sha256(file_url.encode()).hexdigest()
                
                cursor.execute(f"SELECT id FROM {schema}.documents WHERE url = %s", (file_url,))
                existing = cursor.fetchone()
                
                if not existing:
                    cursor.execute(
                        f"INSERT INTO {schema}.documents (title, url, section, content_hash) VALUES (%s, %s, %s, %s) RETURNING id",
                        (title, file_url, section_names[section], content_hash)
                    )
                    doc_id = cursor.fetchone()['id']
                    cursor.execute(
                        f"INSERT INTO {schema}.document_changes (document_id, change_type, new_content_hash) VALUES (%s, 'new', %s)",
                        (doc_id, content_hash)
                    )
                    stats['new_documents'] += 1
                    stats['total_processed'] += 1
        
        update_log(cursor, schema, log_id, 'success', f'Завершено: {stats["new_documents"]} новых', 0)
    
    cursor.close()
    return stats


def monitor_changes(conn, schema: str) -> dict:
    """Мониторинг изменений"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute(f"""
        SELECT COUNT(*) as cnt
        FROM {schema}.document_changes
        WHERE notified = false
    """)
    
    changes_count = cursor.fetchone()['cnt']
    cursor.close()
    return {'changes_found': changes_count, 'notifications_sent': 0}


def create_log(cursor, schema: str, section: str, status: str, message: str) -> int:
    """Создание лога"""
    cursor.execute(
        f"INSERT INTO {schema}.parsing_logs (section, status, message) VALUES (%s, %s, %s) RETURNING id",
        (section, status, message)
    )
    return cursor.fetchone()['id']


def update_log(cursor, schema: str, log_id: int, status: str, message: str, duration_ms: int):
    """Обновление лога"""
    cursor.execute(
        f"UPDATE {schema}.parsing_logs SET status = %s, message = %s, duration_ms = %s, finished_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, message, duration_ms, log_id)
    )


def success_response(data: dict) -> dict:
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(data, ensure_ascii=False, default=str),
        'isBase64Encoded': False
    }


def error_response(message: str, status_code: int = 400) -> dict:
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': message}, ensure_ascii=False),
        'isBase64Encoded': False
    }
