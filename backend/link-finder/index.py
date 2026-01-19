'''
API для автоматического поиска связей между документами через анализ их содержимого.
Извлекает номера и даты документов из первых страниц файлов (docx/pdf).
'''

import json
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from io import BytesIO
from datetime import datetime

def extract_document_references_from_docx(file_bytes: bytes) -> list:
    '''Извлекает ссылки на документы из DOCX файла'''
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= 20:
                break
            text += para.text + "\n"
        
        return parse_document_references(text)
    except Exception as e:
        return []

def extract_document_references_from_pdf(file_bytes: bytes) -> list:
    '''Извлекает ссылки на документы из PDF файла'''
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        
        text = ""
        for i in range(min(3, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\n"
        
        return parse_document_references(text)
    except Exception as e:
        return []

def parse_document_references(text: str) -> list:
    '''Парсит текст и находит упоминания документов вида "постановление №123 от 01.02.2023"
    Поддерживает как одиночные упоминания, так и списки в формате "от DATE года №NUM, от DATE года №NUM"
    '''
    references = []
    
    # Паттерн 1: Обратный порядок - "от DATE года №NUM" (в списках изменений)
    pattern_reverse = r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+(?:№|N|#)\s*(\d+)'
    matches = re.finditer(pattern_reverse, text, re.IGNORECASE)
    for match in matches:
        date_str = match.group(1)
        number = match.group(2)
        
        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            date_formatted = date_obj.strftime('%Y-%m-%d')
            references.append({'number': number, 'date': date_formatted})
        except:
            continue
    
    # Паттерн 2: Прямой порядок - "постановление №NUM от DATE" (в обычном тексте)
    patterns_direct = [
        r'постановлени[ея]\s+(?:№|N|#)?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
        r'постановлени[ея]\s+(?:№|N|#)?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2,4})',
        r'распоряжени[ея]\s+(?:№|N|#)?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
    ]
    
    for pattern in patterns_direct:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            number = match.group(1)
            date_str = match.group(2)
            
            try:
                if len(date_str.split('.')[-1]) == 2:
                    date_obj = datetime.strptime(date_str, '%d.%m.%y')
                else:
                    date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                
                date_formatted = date_obj.strftime('%Y-%m-%d')
                references.append({'number': number, 'date': date_formatted})
            except:
                continue
    
    # Паттерн 3: Упрощенный - просто "№NUM от DATE" (без слова "постановление")
    pattern_simple = r'(?:№|N|#)\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})'
    matches = re.finditer(pattern_simple, text, re.IGNORECASE)
    for match in matches:
        number = match.group(1)
        date_str = match.group(2)
        
        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            date_formatted = date_obj.strftime('%Y-%m-%d')
            references.append({'number': number, 'date': date_formatted})
        except:
            continue
    
    # Убираем дубликаты
    unique_refs = []
    seen = set()
    for ref in references:
        key = f"{ref['number']}_{ref['date']}"
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    
    return unique_refs

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
        schema = cursor.fetchone()['current_schema']
        
        if batch_mode:
            cursor.execute(f"""
                SELECT id, document_number, document_date, file_cdn_url, title
                FROM {schema}.documents
                WHERE file_cdn_url IS NOT NULL
                  AND related_to IS NULL
                  AND related_count = 0
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
        else:
            if not document_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'document_id required'})
                }
            
            cursor.execute(f"""
                SELECT id, document_number, document_date, file_cdn_url, title
                FROM {schema}.documents
                WHERE id = %s
            """, (document_id,))
        
        documents = cursor.fetchall()
        
        if not documents:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Documents not found'})
            }
        
        results = []
        
        for doc in documents:
            if not doc['file_cdn_url']:
                results.append({
                    'document_id': doc['id'],
                    'status': 'skipped',
                    'reason': 'No file URL'
                })
                continue
            
            try:
                response = requests.get(doc['file_cdn_url'], timeout=30)
                response.raise_for_status()
                
                file_extension = doc['file_cdn_url'].split('.')[-1].lower()
                
                if file_extension == 'docx':
                    references = extract_document_references_from_docx(response.content)
                elif file_extension == 'pdf':
                    references = extract_document_references_from_pdf(response.content)
                else:
                    results.append({
                        'document_id': doc['id'],
                        'status': 'skipped',
                        'reason': f'Unsupported format: {file_extension}'
                    })
                    continue
                
                if not references:
                    results.append({
                        'document_id': doc['id'],
                        'document_number': doc['document_number'],
                        'status': 'no_references',
                        'links_found': 0
                    })
                    continue
                
                links_created = 0
                found_documents = []
                
                for ref in references:
                    cursor.execute(f"""
                        SELECT id, document_number, document_date, title
                        FROM {schema}.documents
                        WHERE document_number = %s
                          AND document_date = %s
                          AND id != %s
                        LIMIT 1
                    """, (ref['number'], ref['date'], doc['id']))
                    
                    target_doc = cursor.fetchone()
                    
                    if target_doc:
                        cursor.execute(f"""
                            UPDATE {schema}.documents
                            SET related_to = %s
                            WHERE id = %s AND related_to IS NULL
                        """, (target_doc['id'], doc['id']))
                        
                        if cursor.rowcount > 0:
                            links_created += 1
                            
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_count = related_count + 1
                                WHERE id = %s
                            """, (target_doc['id'],))
                            
                            found_documents.append({
                                'id': target_doc['id'],
                                'number': target_doc['document_number'],
                                'date': str(target_doc['document_date']),
                                'title': target_doc['title']
                            })
                
                conn.commit()
                
                results.append({
                    'document_id': doc['id'],
                    'document_number': doc['document_number'],
                    'status': 'success',
                    'references_found': len(references),
                    'links_created': links_created,
                    'found_documents': found_documents
                })
                
            except Exception as e:
                results.append({
                    'document_id': doc['id'],
                    'status': 'error',
                    'error': str(e)
                })
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'processed': len(results),
                'results': results
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }