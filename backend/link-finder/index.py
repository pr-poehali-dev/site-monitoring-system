'''
API для автоматического поиска связей между документами через анализ их содержимого.
Извлекает номера и даты документов из первых страниц файлов (docx/pdf/doc).
Различает ВЕРСИИ (изменения/отмена существующего документа) и СВЯЗАННЫЕ документы (упоминания в преамбуле).
Версия: 2.0
'''

import json
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from io import BytesIO
from datetime import datetime

def extract_document_references_from_doc(file_bytes: bytes) -> dict:
    '''Извлекает ссылки из старого .doc файла.
    Возвращает: {'versions': [...], 'related': [...]}
    '''
    try:
        import olefile
        ole = olefile.OleFileIO(file_bytes)
        # Простое извлечение текста из .doc
        text = file_bytes.decode('cp1251', errors='ignore')
        # Убираем бинарный мусор
        text = ''.join(c if c.isprintable() or c in '\n\r\t' else ' ' for c in text)
        return parse_document_references(text)
    except Exception as e:
        return {'versions': [], 'related': []}

def extract_document_references_from_docx(file_bytes: bytes) -> dict:
    '''Извлекает ссылки на документы из DOCX файла.
    Возвращает: {'versions': [...], 'related': [...]}
    '''
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= 25:  # Увеличено с 20 до 25 для лучшего покрытия
                break
            text += para.text + "\n"
        
        return parse_document_references(text)
    except Exception as e:
        return {'versions': [], 'related': []}

def extract_document_references_from_pdf(file_bytes: bytes) -> dict:
    '''Извлекает ссылки на документы из PDF файла.
    Возвращает: {'versions': [...], 'related': [...]}
    '''
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        
        text = ""
        for i in range(min(3, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\n"
        
        return parse_document_references(text)
    except Exception as e:
        return {'versions': [], 'related': []}

def parse_document_references(text: str) -> dict:
    '''Парсит текст и находит документы, различая ВЕРСИИ и СВЯЗАННЫЕ документы.
    
    ВЕРСИИ - документы которые:
    - Упоминаются в контексте изменения/отмены ("утратившим силу", "внести изменения")
    - Упоминаются В ЗАГОЛОВКЕ документа (первые 3 абзаца)
    
    СВЯЗАННЫЕ - документы которые:
    - Упоминаются в преамбуле ("в соответствии с", "на основании")
    - Просто упоминаются в тексте без контекста изменения
    
    Возвращает: {'versions': [...], 'related': [...]}
    '''
    versions = []
    related = []
    
    # Список фраз-исключений (другие уровни власти)
    exclusion_phrases = [
        r'правительств[ао]\s+смоленской\s+области',
        r'администраци[ия]\s+смоленской\s+области',
        r'правительств[ао]\s+российской\s+федерации',
        r'правительств[ао]\s+рф',
    ]
    
    # ВЕРСИИ: Ключевые фразы изменения/отмены документа
    version_keywords = [
        r'утратившим\s+силу',
        r'утрачива[ею]т\s+силу',
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
        r'в\s+редакции\s+постановлени',
        r'действует\s+в\s+редакции',
        r'отменить',
        r'отменяется',
        r'отменен',
        r'заменить',
        r'исключить',
    ]
    
    # СВЯЗАННЫЕ: Фразы для преамбулы (основание для издания документа)
    related_keywords = [
        r'в\s+соответствии\s+с',
        r'на\s+основании',
        r'руководствуясь',
        r'в\s+целях',
        r'согласно',
        r'во\s+исполнение',
    ]
    
    # Первые 3 абзаца - это ЗАГОЛОВОК (часто там название документа с упоминанием изменяемого)
    paragraphs = text.split('\n')
    title_text = '\n'.join(paragraphs[:3])
    
    # 1. Ищем ВЕРСИИ в заголовке (первые 3 строки)
    title_versions = extract_references_from_context(title_text, None, exclusion_phrases, is_title=True)
    versions.extend(title_versions)
    
    # 2. Ищем ВЕРСИИ в тексте с ключевыми фразами изменения
    for keyword_pattern in version_keywords:
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            # Для "в редакции" берем больший контекст (длинные списки)
            if 'редакции' in keyword_pattern:
                start_pos = max(0, keyword_match.start() - 100)
                end_pos = min(len(text), keyword_match.end() + 2000)
            else:
                start_pos = max(0, keyword_match.start() - 200)
                end_pos = min(len(text), keyword_match.end() + 300)
            
            context_text = text[start_pos:end_pos]
            found_refs = extract_references_from_context(context_text, keyword_pattern, exclusion_phrases)
            versions.extend(found_refs)
    
    # 3. Ищем СВЯЗАННЫЕ документы в преамбуле
    for keyword_pattern in related_keywords:
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            start_pos = max(0, keyword_match.start() - 50)
            end_pos = min(len(text), keyword_match.end() + 500)
            context_text = text[start_pos:end_pos]
            
            found_refs = extract_references_from_context(context_text, keyword_pattern, exclusion_phrases)
            related.extend(found_refs)
    
    # Убираем дубликаты
    versions = deduplicate_references(versions)
    related = deduplicate_references(related)
    
    # Исключаем из related те, что уже есть в versions
    version_keys = {f"{v['number']}_{v['date']}" for v in versions}
    related = [r for r in related if f"{r['number']}_{r['date']}" not in version_keys]
    
    return {'versions': versions, 'related': related}

def extract_references_from_context(context_text: str, keyword_pattern: str, exclusion_phrases: list, is_title: bool = False) -> list:
    '''Извлекает ссылки на документы из контекста.
    
    is_title=True означает что это заголовок документа - там высокая вероятность что упоминается изменяемый документ
    '''
    references = []
    
    # Паттерны для поиска документов
    patterns = [
        # "от DATE года №NUM"
        (r'от\s+(\d{2}\.\d{2}\.\d{4})\s+г(?:ода)?\.?\s+№\s*(\d+)', 'date_first'),
        (r'от\s+(\d{2}\.\d{2}\.\d{4})\s+г(?:ода)?\.?\s+N\s*(\d+)', 'date_first'),
        # "постановление №NUM от DATE"
        (r'постановлени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        (r'постановлени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        # "№NUM от DATE"
        (r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
        (r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    ]
    
    for pattern, order in patterns:
        for match in re.finditer(pattern, context_text, re.IGNORECASE):
            try:
                if order == 'date_first':
                    date_str = match.group(1)
                    number = match.group(2)
                else:  # number_first
                    number = match.group(1)
                    date_str = match.group(2)
                
                # Фильтр: номер не более 5 цифр
                if len(number) > 5:
                    continue
                
                # Проверяем предложение вокруг (±80 символов)
                match_start = match.start()
                sentence_start = max(0, match_start - 80)
                sentence_end = min(len(context_text), match.end() + 80)
                sentence = context_text[sentence_start:sentence_end]
                
                # Пропускаем если другой уровень власти
                skip = False
                for exclusion in exclusion_phrases:
                    if re.search(exclusion, sentence, re.IGNORECASE):
                        skip = True
                        break
                if skip:
                    continue
                
                # Проверяем год
                date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                current_year = datetime.now().year
                if not (1990 <= date_obj.year <= current_year + 1):
                    continue
                
                date_formatted = date_obj.strftime('%Y-%m-%d')
                
                # Сохраняем контекст для определения типа связи
                references.append({
                    'number': number,
                    'date': date_formatted,
                    'context': sentence[:200]  # Первые 200 символов контекста
                })
            except:
                continue
    
    return references

def deduplicate_references(references: list) -> list:
    '''Убирает дубликаты из списка ссылок'''
    unique_refs = []
    seen = set()
    for ref in references:
        key = f"{ref['number']}_{ref['date']}"
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    return unique_refs

def handler(event: dict, context) -> dict:
    '''API для поиска связей между документами через анализ содержимого файлов.
    
    Различает:
    - ВЕРСИИ (document_relations): изменения/отмена существующих документов
    - СВЯЗАННЫЕ (related_documents): упоминания в преамбуле, основания для издания
    '''
    
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
            if not doc['file_cdn_url']:
                results.append({
                    'document_id': doc['id'],
                    'status': 'skipped',
                    'reason': 'No file URL'
                })
                continue
            
            try:
                # Скачиваем файл
                response = requests.get(doc['file_cdn_url'], timeout=30)
                response.raise_for_status()
                
                file_extension = doc['file_cdn_url'].split('.')[-1].lower()
                
                # Парсим документ
                if file_extension == 'docx':
                    refs_data = extract_document_references_from_docx(response.content)
                elif file_extension == 'doc':
                    refs_data = extract_document_references_from_doc(response.content)
                elif file_extension == 'pdf':
                    refs_data = extract_document_references_from_pdf(response.content)
                else:
                    results.append({
                        'document_id': doc['id'],
                        'status': 'skipped',
                        'reason': f'Unsupported format: {file_extension}'
                    })
                    continue
                
                version_refs = refs_data.get('versions', [])
                related_refs = refs_data.get('related', [])
                
                # Если ничего не найдено
                if not version_refs and not related_refs:
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
                        'versions_created': 0,
                        'related_created': 0
                    })
                    continue
                
                versions_created = 0
                related_created = 0
                found_versions = []
                found_related = []
                phantom_created = 0
                
                # Обрабатываем ВЕРСИИ
                for ref in version_refs:
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
                        # Создаем связь версии
                        cursor.execute(f"""
                            INSERT INTO {schema}.document_relations 
                            (source_document_id, target_document_id, relation_type)
                            VALUES (%s, %s, 'previous_version')
                            ON CONFLICT (source_document_id, target_document_id) DO NOTHING
                        """, (doc['id'], target_doc['id']))
                        
                        if cursor.rowcount > 0:
                            versions_created += 1
                            
                            # Устанавливаем related_to у старого документа
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_to = %s
                                WHERE id = %s AND related_to IS NULL
                            """, (doc['id'], target_doc['id']))
                            
                            # Увеличиваем счетчик новых версий
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_count = related_count + 1
                                WHERE id = %s
                            """, (target_doc['id'],))
                            
                            found_versions.append({
                                'id': target_doc['id'],
                                'number': target_doc['document_number'],
                                'date': str(target_doc['document_date']),
                                'title': target_doc['title']
                            })
                    else:
                        # Создаем фантом для версии
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
                            
                            cursor.execute(f"""
                                INSERT INTO {schema}.document_relations 
                                (source_document_id, target_document_id, relation_type)
                                VALUES (%s, %s, 'previous_version')
                            """, (doc['id'], phantom_id))
                            
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_to = %s
                                WHERE id = %s
                            """, (doc['id'], phantom_id))
                            
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_count = related_count + 1
                                WHERE id = %s
                            """, (phantom_id,))
                        else:
                            # Фантом существует, добавляем связь
                            cursor.execute(f"""
                                INSERT INTO {schema}.document_relations 
                                (source_document_id, target_document_id, relation_type)
                                VALUES (%s, %s, 'previous_version')
                                ON CONFLICT (source_document_id, target_document_id) DO NOTHING
                            """, (doc['id'], existing_phantom['id']))
                            
                            if cursor.rowcount > 0:
                                cursor.execute(f"""
                                    UPDATE {schema}.documents
                                    SET related_count = related_count + 1
                                    WHERE id = %s
                                """, (existing_phantom['id'],))
                
                # Обрабатываем СВЯЗАННЫЕ документы
                for ref in related_refs:
                    cursor.execute(f"""
                        SELECT id, document_number, document_date, title
                        FROM {schema}.documents
                        WHERE document_number = %s
                          AND document_date = %s
                          AND id != %s
                        LIMIT 1
                    """, (ref['number'], ref['date'], doc['id']))
                    
                    related_doc = cursor.fetchone()
                    
                    if related_doc:
                        # Создаем связь связанного документа
                        cursor.execute(f"""
                            INSERT INTO {schema}.related_documents 
                            (source_document_id, related_document_id, relation_type, context)
                            VALUES (%s, %s, 'reference', %s)
                            ON CONFLICT (source_document_id, related_document_id) DO NOTHING
                        """, (doc['id'], related_doc['id'], ref.get('context', '')[:200]))
                        
                        if cursor.rowcount > 0:
                            related_created += 1
                            
                            # Увеличиваем счетчик связанных документов
                            cursor.execute(f"""
                                UPDATE {schema}.documents
                                SET related_docs_count = related_docs_count + 1
                                WHERE id = %s
                            """, (doc['id'],))
                            
                            found_related.append({
                                'id': related_doc['id'],
                                'number': related_doc['document_number'],
                                'date': str(related_doc['document_date']),
                                'title': related_doc['title']
                            })
                
                # Обновляем счетчики prev_versions_count
                cursor.execute(f"""
                    UPDATE {schema}.documents
                    SET prev_versions_count = (
                        SELECT COUNT(*)
                        FROM {schema}.document_relations
                        WHERE source_document_id = {doc['id']} AND relation_type = 'previous_version'
                    )
                    WHERE id = %s
                """, (doc['id'],))
                
                # Логируем результат
                cursor.execute(f"""
                    INSERT INTO {schema}.link_finding_logs 
                    (document_id, document_number, status, references_found, links_created, phantoms_created, message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    doc['id'],
                    doc['document_number'],
                    'success',
                    len(version_refs) + len(related_refs),
                    versions_created + related_created,
                    phantom_created,
                    f"Версий: {versions_created}, Связанных: {related_created}, Фантомов: {phantom_created}"
                ))
                
                conn.commit()
                
                results.append({
                    'document_id': doc['id'],
                    'document_number': doc['document_number'],
                    'status': 'success',
                    'versions_created': versions_created,
                    'related_created': related_created,
                    'phantoms_created': phantom_created,
                    'found_versions': found_versions,
                    'found_related': found_related
                })
                
            except Exception as e:
                conn.rollback()
                results.append({
                    'document_id': doc['id'],
                    'document_number': doc.get('document_number'),
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
            }, ensure_ascii=False, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }