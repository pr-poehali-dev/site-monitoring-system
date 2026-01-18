import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def handler(event: dict, context) -> dict:
    """
    API для получения данных системы мониторинга:
    - GET /documents - список документов
    - GET /changes - история изменений
    - GET /logs - логи парсинга
    - GET /settings - настройки
    - POST /settings - обновление настроек
    """
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query_params = event.get('queryStringParameters') or {}
        endpoint = query_params.get('endpoint', 'documents')
        
        if method == 'GET':
            if endpoint == 'documents':
                result = get_documents(cursor, schema, query_params)
            elif endpoint == 'changes':
                result = get_changes(cursor, schema, query_params)
            elif endpoint == 'logs':
                result = get_logs(cursor, schema, query_params)
            elif endpoint == 'settings':
                result = get_settings(cursor, schema)
            elif endpoint == 'stats':
                result = get_stats(cursor, schema)
            else:
                cursor.close()
                conn.close()
                return error_response('Неизвестный endpoint', 400)
            
            cursor.close()
            conn.close()
            return success_response(result)
        
        elif method == 'POST':
            if endpoint == 'settings':
                body = json.loads(event.get('body', '{}'))
                result = update_settings(cursor, schema, body)
                conn.commit()
                cursor.close()
                conn.close()
                return success_response(result)
        
        cursor.close()
        conn.close()
        return error_response('Неподдерживаемый метод', 400)
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return error_response(f'Ошибка: {str(e)}', 500)


def get_documents(cursor, schema: str, params: dict) -> dict:
    """Получение списка документов с фильтрацией и сортировкой"""
    search = params.get('search', '')
    section = params.get('section', '')
    year = params.get('year', '')
    sort_by = params.get('sort_by', 'created_at')
    sort_order = params.get('sort_order', 'DESC')
    limit = int(params.get('limit', '100'))
    offset = int(params.get('offset', '0'))
    
    where_clauses = []
    query_params = []
    
    if search:
        where_clauses.append("title ILIKE %s")
        query_params.append(f'%{search}%')
    
    if section and section != 'all':
        where_clauses.append("section = %s")
        query_params.append(section)
    
    if year:
        where_clauses.append("EXTRACT(YEAR FROM COALESCE(document_date, published_date, created_at)) = %s")
        query_params.append(int(year))
    
    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
    
    allowed_sorts = ['created_at', 'document_date', 'published_date', 'title', 'changes_count', 'file_size']
    if sort_by not in allowed_sorts:
        sort_by = 'created_at'
    if sort_order.upper() not in ['ASC', 'DESC']:
        sort_order = 'DESC'
    
    order_sql = f"ORDER BY {sort_by} {sort_order} NULLS LAST"
    
    cursor.execute(f"""
        SELECT id, title, url, section, published_date, document_date, document_number, 
               file_size, file_cdn_url, changes_count, last_checked_at, created_at
        FROM {schema}.documents
        WHERE {where_sql}
        {order_sql}
        LIMIT %s OFFSET %s
    """, (*query_params, limit, offset))
    
    documents = cursor.fetchall()
    
    cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.documents WHERE {where_sql}", query_params)
    total = cursor.fetchone()['total']
    
    return {
        'documents': documents,
        'total': total,
        'limit': limit,
        'offset': offset
    }


def get_changes(cursor, schema: str, params: dict) -> dict:
    """Получение истории изменений с фильтрацией по документу"""
    limit = int(params.get('limit', '50'))
    doc_id = params.get('document_id', '')
    
    where_clause = ""
    query_params = []
    
    if doc_id:
        where_clause = "WHERE dc.document_id = %s"
        query_params.append(int(doc_id))
    
    cursor.execute(f"""
        SELECT dc.id, dc.change_type, dc.detected_at, dc.notified,
               dc.old_title, dc.new_title, dc.old_file_size, dc.new_file_size,
               d.title, d.url, d.section, d.file_cdn_url
        FROM {schema}.document_changes dc
        JOIN {schema}.documents d ON dc.document_id = d.id
        {where_clause}
        ORDER BY dc.detected_at DESC
        LIMIT %s
    """, (*query_params, limit))
    
    changes = cursor.fetchall()
    
    return {'changes': changes}


def get_logs(cursor, schema: str, params: dict) -> dict:
    """Получение логов парсинга"""
    limit = int(params.get('limit', '50'))
    
    cursor.execute(f"""
        SELECT id, section, status, message, duration_ms, started_at, finished_at
        FROM {schema}.parsing_logs
        ORDER BY started_at DESC
        LIMIT %s
    """, (limit,))
    
    logs = cursor.fetchall()
    
    return {'logs': logs}


def get_settings(cursor, schema: str) -> dict:
    """Получение настроек"""
    cursor.execute(f"SELECT key, value FROM {schema}.monitoring_settings")
    settings_rows = cursor.fetchall()
    
    settings = {row['key']: row['value'] for row in settings_rows}
    
    return {'settings': settings}


def get_stats(cursor, schema: str) -> dict:
    """Получение статистики"""
    cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.documents")
    total_docs = cursor.fetchone()['total']
    
    cursor.execute(f"""
        SELECT COUNT(*) as total 
        FROM {schema}.document_changes 
        WHERE detected_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
    """)
    changes_week = cursor.fetchone()['total']
    
    cursor.execute(f"SELECT COUNT(DISTINCT section) as total FROM {schema}.documents")
    active_sections = cursor.fetchone()['total']
    
    return {
        'total_documents': total_docs,
        'changes_this_week': changes_week,
        'active_sections': active_sections
    }


def update_settings(cursor, schema: str, body: dict) -> dict:
    """Обновление настроек"""
    updated = []
    
    for key, value in body.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        
        cursor.execute(f"""
            INSERT INTO {schema}.monitoring_settings (key, value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        updated.append(key)
    
    return {'updated': updated}


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