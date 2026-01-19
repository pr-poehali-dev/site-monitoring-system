'''
API для автоматического поиска связей между документами через анализ их содержимого.
Извлекает номера и даты документов из первых страниц файлов (docx/pdf/doc).
Различает ВЕРСИИ (изменения/отмена существующего документа) и СВЯЗАННЫЕ документы (упоминания в преамбуле).
Версия: 2.0 (рефакторенная)
'''

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

from models import ProcessingResult, ParseResult
from parsers import extract_from_docx, extract_from_doc, extract_from_pdf
from db_operations import (
    find_document, get_or_create_phantom,
    create_version_relation, create_related_relation,
    update_version_counters, update_related_counter,
    update_prev_versions_count, log_processing_result
)

def process_document(doc: dict, cursor, schema: str) -> ProcessingResult:
    '''Обрабатывает один документ: скачивает файл, парсит, создает связи'''
    
    if not doc['file_cdn_url']:
        return ProcessingResult(
            document_id=doc['id'],
            document_number=doc['document_number'],
            status='skipped',
            error='No file URL'
        )
    
    try:
        # Скачиваем файл
        response = requests.get(doc['file_cdn_url'], timeout=30)
        response.raise_for_status()
        
        file_extension = doc['file_cdn_url'].split('.')[-1].lower()
        
        # Парсим документ
        if file_extension == 'docx':
            refs_data = extract_from_docx(response.content)
        elif file_extension == 'doc':
            refs_data = extract_from_doc(response.content)
        elif file_extension == 'pdf':
            refs_data = extract_from_pdf(response.content)
        else:
            return ProcessingResult(
                document_id=doc['id'],
                document_number=doc['document_number'],
                status='skipped',
                error=f'Unsupported format: {file_extension}'
            )
        
        version_refs = refs_data.versions
        related_refs = refs_data.related
        
        # Если ничего не найдено
        if not version_refs and not related_refs:
            return ProcessingResult(
                document_id=doc['id'],
                document_number=doc['document_number'],
                status='no_references'
            )
        
        result = ProcessingResult(
            document_id=doc['id'],
            document_number=doc['document_number'],
            status='success'
        )
        
        # Обрабатываем ВЕРСИИ
        for ref in version_refs:
            target_doc = find_document(cursor, schema, ref.number, ref.date, doc['id'])
            
            if target_doc:
                # Документ найден - создаем связь версии
                if create_version_relation(cursor, schema, doc['id'], target_doc['id']):
                    result.versions_created += 1
                    update_version_counters(cursor, schema, target_doc['id'], doc['id'])
                    result.found_versions.append({
                        'id': target_doc['id'],
                        'number': target_doc['document_number'],
                        'date': str(target_doc['document_date']),
                        'title': target_doc['title']
                    })
            else:
                # Создаем фантом
                phantom_id = get_or_create_phantom(cursor, schema, ref, doc)
                if create_version_relation(cursor, schema, doc['id'], phantom_id):
                    result.phantoms_created += 1
                    update_version_counters(cursor, schema, phantom_id, doc['id'])
        
        # Обрабатываем СВЯЗАННЫЕ документы
        for ref in related_refs:
            related_doc = find_document(cursor, schema, ref.number, ref.date, doc['id'])
            
            if related_doc:
                if create_related_relation(cursor, schema, doc['id'], related_doc['id'], ref.context):
                    result.related_created += 1
                    update_related_counter(cursor, schema, doc['id'])
                    result.found_related.append({
                        'id': related_doc['id'],
                        'number': related_doc['document_number'],
                        'date': str(related_doc['document_date']),
                        'title': related_doc['title']
                    })
        
        # Обновляем счетчик предыдущих версий
        update_prev_versions_count(cursor, schema, doc['id'])
        
        return result
        
    except Exception as e:
        return ProcessingResult(
            document_id=doc['id'],
            document_number=doc.get('document_number'),
            status='error',
            error=str(e)
        )

def handler(event: dict, context) -> dict:
    '''API для поиска связей между документами через анализ содержимого файлов'''
    
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
        body = json.loads(event.get('body', '{}'))
        document_id = body.get('document_id')
        batch_mode = body.get('batch_mode', False)
        limit = body.get('limit', 10)
        
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
        schema_result = cursor.fetchone()
        schema = schema_result['current_schema'] if schema_result else 'public'
        
        # Получаем документы для обработки
        if batch_mode:
            query = f"""
                SELECT id, document_number, document_date, file_cdn_url, title, section, 
                       published_date, created_at
                FROM {schema}.documents d
                WHERE file_cdn_url IS NOT NULL
                  AND related_to IS NULL
                  AND related_count = 0
                  AND (is_phantom IS NULL OR is_phantom = FALSE)
                  AND (file_cdn_url LIKE '%.docx' OR file_cdn_url LIKE '%.pdf' OR file_cdn_url LIKE '%.doc')
                  AND NOT EXISTS (
                      SELECT 1 FROM {schema}.link_finding_logs lfl 
                      WHERE lfl.document_id = d.id
                  )
                ORDER BY 
                    COALESCE(d.document_date, d.published_date, d.created_at) DESC,
                    d.id DESC
                LIMIT {limit}
            """
            cursor.execute(query)
        else:
            if not document_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'document_id required'})
                }
            
            cursor.execute(f"""
                SELECT id, document_number, document_date, file_cdn_url, title, section
                FROM {schema}.documents
                WHERE id = %s
            """, (document_id,))
        
        documents = cursor.fetchall()
        
        if not documents:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'processed': 0, 'results': []})
            }
        
        results = []
        
        for doc in documents:
            result = process_document(doc, cursor, schema)
            
            # Логируем результат
            total_refs = len(result.found_versions) + len(result.found_related)
            if result.status != 'skipped':
                log_processing_result(cursor, schema, result, total_refs)
            
            conn.commit()
            
            results.append({
                'document_id': result.document_id,
                'document_number': result.document_number,
                'status': result.status,
                'versions_created': result.versions_created,
                'related_created': result.related_created,
                'phantoms_created': result.phantoms_created,
                'found_versions': result.found_versions,
                'found_related': result.found_related,
                **({'error': result.error} if result.error else {})
            })
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'processed': len(results),
                'results': results
            }, ensure_ascii=False, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
