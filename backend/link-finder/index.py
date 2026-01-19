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
    '''Парсит текст и находит ТОЛЬКО упоминания предыдущих версий документов.
    Ищет контекстные фразы: "утратившим силу", "признать утратившим", "внести изменения" и т.п.
    Возвращает ВСЕ найденные документы в контексте изменения/отмены.
    '''
    references = []
    
    # Ключевые фразы, указывающие на связь с предыдущей версией
    context_keywords = [
        r'утратившим\s+силу',
        r'утрачива[ею]т\s+силу',  # утрачивает, утрачивают
        r'считать\s+утратившим',
        r'признать\s+утратившим',
        r'внести\s+изменени[яе]',
        r'внесены\s+изменения',
        r'вносятся\s+изменения',
        r'с\s+изменениями,\s+внесенными',
        r'дополнить',
        r'дополняется',
        r'дополнен',
        r'изложить\s+в\s+новой\s+редакции',
        r'в\s+редакции\s+постановлени',  # Для списков вида "(в редакции постановлений ... от DATE №NUM, от DATE №NUM)"
        r'действует\s+в\s+редакции',
        r'отменить',
        r'отменяется',
        r'отменен',
        r'заменить',
        r'исключить',
    ]
    
    # Ищем абзацы/предложения с ключевыми фразами
    for keyword_pattern in context_keywords:
        # Находим все куски текста где встречается ключевая фраза
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            # Для фразы "в редакции" берем больший контекст (до 2000 символов) для захвата длинных списков
            if 'редакции' in keyword_pattern:
                start_pos = max(0, keyword_match.start() - 100)
                end_pos = min(len(text), keyword_match.end() + 2000)
            else:
                start_pos = max(0, keyword_match.start() - 200)
                end_pos = min(len(text), keyword_match.end() + 300)
            context_text = text[start_pos:end_pos]
            
            # В этом контексте ищем все упоминания документов
            
            # Паттерн 1: "от DATE года №NUM" (включая варианты с N, #, без символа)
            patterns_reverse = [
                r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+№\s*(\d+)',
                r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+N\s*(\d+)',
                r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+#\s*(\d+)',
            ]
            
            for pattern_reverse in patterns_reverse:
                for match in re.finditer(pattern_reverse, context_text, re.IGNORECASE):
                    try:
                        date_str = match.group(1)
                        number = match.group(2)
                        
                        # Фильтр: номер не должен быть слишком длинным (не больше 5 цифр)
                        if len(number) > 5:
                            continue
                        
                        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                        # Фильтр: год должен быть в разумных пределах (1990 - текущий год + 1)
                        current_year = datetime.now().year
                        if not (1990 <= date_obj.year <= current_year + 1):
                            continue
                        
                        date_formatted = date_obj.strftime('%Y-%m-%d')
                        references.append({'number': number, 'date': date_formatted})
                    except:
                        continue
            
            # Паттерн 2: "постановление №NUM от DATE"
            patterns_direct = [
                r'постановлени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
                r'постановлени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
                r'постановлени[ея]\s+#\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
                r'распоряжени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.d{4})',
                r'распоряжени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
            ]
            
            for pattern in patterns_direct:
                for match in re.finditer(pattern, context_text, re.IGNORECASE):
                    try:
                        number = match.group(1)
                        date_str = match.group(2)
                        
                        # Фильтр: номер не должен быть слишком длинным
                        if len(number) > 5:
                            continue
                        
                        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                        current_year = datetime.now().year
                        if not (1990 <= date_obj.year <= current_year + 1):
                            continue
                        
                        date_formatted = date_obj.strftime('%Y-%m-%d')
                        references.append({'number': number, 'date': date_formatted})
                    except:
                        continue
            
            # Паттерн 3: "№NUM от DATE" (простой формат)
            patterns_simple = [
                r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
                r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
                r'#\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})',
            ]
            
            for pattern_simple in patterns_simple:
                for match in re.finditer(pattern_simple, context_text, re.IGNORECASE):
                    try:
                        number = match.group(1)
                        date_str = match.group(2)
                        
                        # Фильтр: номер не должен быть слишком длинным
                        if len(number) > 5:
                            continue
                        
                        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                        current_year = datetime.now().year
                        if not (1990 <= date_obj.year <= current_year + 1):
                            continue
                        
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
        schema_result = cursor.fetchone()
        if not schema_result:
            schema = 'public'
        else:
            schema = schema_result['current_schema']
        
        if batch_mode:
            query = f"""
                SELECT id, document_number, document_date, file_cdn_url, title, section, 
                       published_date, created_at
                FROM {schema}.documents d
                WHERE file_cdn_url IS NOT NULL
                  AND related_to IS NULL
                  AND related_count = 0
                  AND (is_phantom IS NULL OR is_phantom = FALSE)
                  AND (file_cdn_url LIKE '%.docx' OR file_cdn_url LIKE '%.pdf')
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
                SELECT id, document_number, document_date, file_cdn_url, title
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
                    cursor.execute(f"""
                        INSERT INTO {schema}.link_finding_logs 
                        (document_id, document_number, status, references_found, message)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (doc['id'], doc['document_number'], 'no_references', 0, 'Упоминаний не найдено'))
                    conn.commit()
                    
                    results.append({
                        'document_id': doc['id'],
                        'document_number': doc['document_number'],
                        'status': 'no_references',
                        'links_created': 0
                    })
                    continue
                
                links_created = 0
                found_documents = []
                not_found_refs = []
                phantom_created = 0
                
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
                        # Используем новую таблицу document_relations вместо related_to
                        cursor.execute(f"""
                            INSERT INTO {schema}.document_relations 
                            (source_document_id, target_document_id, relation_type)
                            VALUES (%s, %s, 'previous_version')
                            ON CONFLICT (source_document_id, target_document_id) DO NOTHING
                        """, (doc['id'], target_doc['id']))
                        
                        if cursor.rowcount > 0:
                            links_created += 1
                            
                            # Обновляем related_to для обратной совместимости (первая найденная связь)
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_to = %s
                                WHERE id = %s AND related_to IS NULL
                            """, (target_doc['id'], doc['id']))
                            
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
                    else:
                        not_found_refs.append(f"№{ref['number']} от {ref['date']}")
                        
                        cursor.execute(f"""
                            SELECT id FROM {schema}.documents
                            WHERE document_number = %s
                              AND document_date = %s
                              AND is_phantom = TRUE
                            LIMIT 1
                        """, (ref['number'], ref['date']))
                        
                        existing_phantom = cursor.fetchone()
                        
                        if not existing_phantom:
                            phantom_title = f"Постановление {ref['number']} от {ref['date']}: [Файл не найден на сайте]"
                            phantom_url = f"phantom://{ref['number']}/{ref['date']}/source-{doc['id']}"
                            
                            cursor.execute(f"""
                                INSERT INTO {schema}.documents 
                                (document_number, document_date, title, section, is_phantom, phantom_source_id, url)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (ref['number'], ref['date'], phantom_title, doc.get('section', 'Постановления'), True, doc['id'], phantom_url))
                            
                            phantom_id = cursor.fetchone()['id']
                            phantom_created += 1
                            
                            # Добавляем в document_relations
                            cursor.execute(f"""
                                INSERT INTO {schema}.document_relations 
                                (source_document_id, target_document_id, relation_type)
                                VALUES (%s, %s, 'previous_version')
                            """, (doc['id'], phantom_id))
                            
                            # Обновляем related_to для обратной совместимости
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_to = %s
                                WHERE id = %s AND related_to IS NULL
                            """, (phantom_id, doc['id']))
                            
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_count = related_count + 1
                                WHERE id = %s
                            """, (phantom_id,))
                        else:
                            # Фантом уже существует, добавляем связь
                            cursor.execute(f"""
                                INSERT INTO {schema}.document_relations 
                                (source_document_id, target_document_id, relation_type)
                                VALUES (%s, %s, 'previous_version')
                                ON CONFLICT (source_document_id, target_document_id) DO NOTHING
                            """, (doc['id'], existing_phantom['id']))
                            
                            if cursor.rowcount > 0:
                                links_created += 1
                                cursor.execute(f"""
                                    UPDATE {schema}.documents
                                    SET related_count = related_count + 1
                                    WHERE id = %s
                                """, (existing_phantom['id'],))
                
                conn.commit()
                
                not_found_str = ', '.join(not_found_refs[:10]) if not_found_refs else None
                log_message = f"Найдено {len(references)} упоминаний, создано {links_created} связей"
                if phantom_created > 0:
                    log_message += f", создано {phantom_created} фиктивных версий"
                
                cursor.execute(f"""
                    INSERT INTO {schema}.link_finding_logs 
                    (document_id, document_number, status, references_found, links_created, not_found_refs, message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (doc['id'], doc['document_number'], 'success', len(references), links_created, not_found_str, log_message))
                conn.commit()
                
                result_item = {
                    'document_id': doc['id'],
                    'document_number': doc['document_number'],
                    'status': 'success',
                    'references_found': len(references),
                    'links_created': links_created,
                    'phantom_created': phantom_created,
                    'found_documents': found_documents
                }
                
                if not_found_refs:
                    result_item['not_found'] = not_found_refs[:5]
                
                results.append(result_item)
                
            except Exception as e:
                import traceback
                error_details = f"{str(e)}\n{traceback.format_exc()}"
                
                cursor.execute(f"""
                    INSERT INTO {schema}.link_finding_logs 
                    (document_id, document_number, status, message)
                    VALUES (%s, %s, %s, %s)
                """, (doc['id'], doc['document_number'], 'error', f"Ошибка: {error_details[:500]}"))
                conn.commit()
                
                results.append({
                    'document_id': doc['id'],
                    'status': 'error',
                    'error': error_details[:200]
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
        import traceback
        error_trace = traceback.format_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e), 'trace': error_trace})
        }