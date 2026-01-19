'''
API для удаления всех фантомных документов и очистки логов для перезапуска с улучшенной логикой
'''

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def handler(event: dict, context) -> dict:
    '''Удаление всех фантомных документов и сброс логов поиска связей'''
    
    method = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }
    
    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    try:
        dsn = os.environ.get('DATABASE_URL')
        if not dsn:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'DATABASE_URL not configured'})
            }
        
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()['current_schema']
        
        # 1. Подсчитываем что будем удалять
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.documents WHERE is_phantom = TRUE")
        phantom_count = cursor.fetchone()['cnt']
        
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.link_finding_logs")
        logs_count = cursor.fetchone()['cnt']
        
        # 2. Удаляем логи для фантомных документов
        cursor.execute(f"""
            DELETE FROM {schema}.link_finding_logs
            WHERE document_id IN (
                SELECT id FROM {schema}.documents WHERE is_phantom = TRUE
            )
        """)
        
        # 3. Сбрасываем related_to для документов, которые ссылались на фантомы
        cursor.execute(f"""
            UPDATE {schema}.documents
            SET related_to = NULL
            WHERE related_to IN (
                SELECT id FROM {schema}.documents WHERE is_phantom = TRUE
            )
        """)
        related_reset = cursor.rowcount
        
        # 4. Удаляем сами фантомные документы
        cursor.execute(f"DELETE FROM {schema}.documents WHERE is_phantom = TRUE")
        
        # 5. Очищаем все логи поиска связей
        cursor.execute(f"DELETE FROM {schema}.link_finding_logs")
        
        # 6. Сбрасываем счетчики related_count для всех документов
        cursor.execute(f"UPDATE {schema}.documents SET related_count = 0")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'phantom_documents_deleted': phantom_count,
                'logs_deleted': logs_count,
                'related_links_reset': related_reset,
                'message': f'Удалено {phantom_count} фантомных документов, {logs_count} логов. Система готова к перезапуску поиска связей.'
            })
        }
        
    except Exception as e:
        import traceback
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        }
