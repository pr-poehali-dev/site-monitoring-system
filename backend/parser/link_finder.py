"""
🔗 МОДУЛЬ ПОИСКА СВЯЗЕЙ МЕЖДУ ДОКУМЕНТАМИ

Детальный анализ содержимого документов для поиска упоминаний других постановлений.
Полное логирование каждого шага в таблицу link_finding_logs.
"""

import re
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import requests
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from io import BytesIO


VERSION_KEYWORDS = [
    r'утратившим\s+силу', r'утрачива[ею]т\s+силу', r'считать\s+утратившим',
    r'признать\s+утратившим', r'внести\s+изменени[яе]', r'внесены\s+изменения',
    r'вносятся\s+изменения', r'с\s+изменениями,\s+внесенными',
    r'дополнить', r'дополняется', r'дополнен',
    r'изложить\s+в\s+новой\s+редакции', r'в\s+редакции\s+постановлени',
    r'действует\s+в\s+редакции', r'отменить', r'отменяется', r'отменен',
    r'заменить', r'исключить'
]

RELATED_KEYWORDS = [
    r'в\s+соответствии\s+с', r'на\s+основании', r'руководствуясь',
    r'в\s+целях', r'согласно', r'во\s+исполнение'
]

DOCUMENT_PATTERNS = [
    (r'от\s+(\d{2}\.\d{2}\.\d{4})\s*г(?:ода)?\.?\s+№\s*(\d+)', 'date_first'),
    (r'от\s+(\d{2}\.\d{2}\.\d{4})\s*г(?:ода)?\.?\s+N\s*(\d+)', 'date_first'),
    (r'постановлени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'постановлени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
]

EXCLUSION_PHRASES = [
    'правительства смоленской области',
    'администрации смоленской области',
    'правительства российской федерации',
    'правительства рф'
]


def log_step(cursor, schema: str, session_id: str, doc_id: Optional[int], 
             doc_number: Optional[str], doc_date: Optional[str],
             step: str, status: str, details: dict):
    """Записать шаг обработки в link_finding_logs"""
    import json
    cursor.execute(f"""
        INSERT INTO {schema}.link_finding_logs 
        (session_id, document_id, document_number, document_date, step, status, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (session_id, doc_id, doc_number, doc_date, step, status, json.dumps(details, ensure_ascii=False)))


def download_file(url: str, timeout: int = 30) -> Tuple[Optional[bytes], str]:
    """Скачать файл по URL"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content, ''
    except Exception as e:
        return None, str(e)


def parse_docx(content: bytes) -> Tuple[Optional[str], Optional[dict], str]:
    """Парсинг DOCX файла"""
    try:
        doc = DocxDocument(BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = '\n'.join(paragraphs)
        stats = {
            'format': 'docx',
            'paragraphs': len(paragraphs),
            'text_length': len(text)
        }
        return text, stats, ''
    except Exception as e:
        return None, None, str(e)


def parse_pdf(content: bytes) -> Tuple[Optional[str], Optional[dict], str]:
    """Парсинг PDF файла"""
    try:
        reader = PdfReader(BytesIO(content))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text())
        text = '\n'.join(pages_text)
        stats = {
            'format': 'pdf',
            'pages': len(reader.pages),
            'text_length': len(text)
        }
        return text, stats, ''
    except Exception as e:
        return None, None, str(e)


def extract_mentions(text: str) -> List[Dict]:
    """Извлечь упоминания документов из текста"""
    mentions = []
    
    for pattern, order_type in DOCUMENT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if order_type == 'date_first':
                date_str = match.group(1)
                number_str = match.group(2)
            else:
                number_str = match.group(1)
                date_str = match.group(2)
            
            context_start = max(0, match.start() - 100)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end].replace('\n', ' ')
            
            pattern_name = f"{pattern[:50]}... ({order_type})"
            
            mentions.append({
                'number': number_str,
                'date': date_str,
                'context': context,
                'pattern': pattern_name,
                'position': match.start()
            })
    
    return mentions


def classify_mention(context: str) -> Tuple[str, List[str]]:
    """Классифицировать упоминание: VERSION или RELATED"""
    context_lower = context.lower()
    
    found_version = []
    for keyword in VERSION_KEYWORDS:
        if re.search(keyword, context_lower):
            found_version.append(keyword)
    
    found_related = []
    for keyword in RELATED_KEYWORDS:
        if re.search(keyword, context_lower):
            found_related.append(keyword)
    
    if found_version:
        return 'VERSION', found_version
    elif found_related:
        return 'RELATED', found_related
    else:
        return 'UNKNOWN', []


def is_external_document(context: str) -> Tuple[bool, Optional[str]]:
    """Проверить, является ли документ внешним (не нашей юрисдикции)"""
    context_lower = context.lower()
    for phrase in EXCLUSION_PHRASES:
        if phrase in context_lower:
            return True, phrase
    return False, None


def find_document_in_db(cursor, schema: str, number: str, date_str: str) -> Optional[int]:
    """Найти документ в БД по номеру и дате"""
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
        cursor.execute(f"""
            SELECT id FROM {schema}.documents 
            WHERE document_number = %s AND document_date = %s
        """, (number, date_obj))
        result = cursor.fetchone()
        return result['id'] if result else None
    except:
        return None


def create_phantom_document(cursor, schema: str, number: str, date_str: str) -> int:
    """Создать фантомный документ"""
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
        cursor.execute(f"""
            INSERT INTO {schema}.documents 
            (title, document_number, document_date, url, section, is_phantom)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            f'Постановление №{number} от {date_str}',
            number,
            date_obj,
            '',
            'external',
            True
        ))
        return cursor.fetchone()['id']
    except Exception as e:
        raise Exception(f'Не удалось создать фантом: {str(e)}')


def check_existing_link(cursor, schema: str, source_id: int, target_id: int, 
                       link_type: str) -> Optional[dict]:
    """Проверить существование связи"""
    if link_type == 'VERSION':
        cursor.execute(f"""
            SELECT id, created_at FROM {schema}.document_relations
            WHERE document_id = %s AND previous_version_id = %s
        """, (source_id, target_id))
    else:
        cursor.execute(f"""
            SELECT id, created_at FROM {schema}.related_documents
            WHERE document_id = %s AND related_document_id = %s AND relation_type = 'reference'
        """, (source_id, target_id))
    
    result = cursor.fetchone()
    return dict(result) if result else None


def create_link(cursor, schema: str, source_id: int, target_id: int, 
                link_type: str, context: str) -> int:
    """Создать связь между документами"""
    if link_type == 'VERSION':
        cursor.execute(f"""
            INSERT INTO {schema}.document_relations 
            (document_id, previous_version_id, relation_type, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (source_id, target_id, 'previous_version', context[:500]))
    else:
        cursor.execute(f"""
            INSERT INTO {schema}.related_documents
            (document_id, related_document_id, relation_type, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (source_id, target_id, 'reference', context[:500]))
    
    return cursor.fetchone()['id']


def delete_link(cursor, schema: str, link_id: int, link_type: str):
    """Удалить связь"""
    if link_type == 'VERSION':
        cursor.execute(f"DELETE FROM {schema}.document_relations WHERE id = %s", (link_id,))
    else:
        cursor.execute(f"DELETE FROM {schema}.related_documents WHERE id = %s", (link_id,))


def get_existing_links(cursor, schema: str, source_id: int) -> Dict[str, List[dict]]:
    """Получить все существующие связи документа"""
    cursor.execute(f"""
        SELECT dr.id, dr.previous_version_id as target_id, 
               d.document_number as number, d.document_date as date, 
               dr.created_at, dr.description,
               'VERSION' as link_type
        FROM {schema}.document_relations dr
        JOIN {schema}.documents d ON dr.previous_version_id = d.id
        WHERE dr.document_id = %s
    """, (source_id,))
    version_links = cursor.fetchall()
    
    cursor.execute(f"""
        SELECT rd.id, rd.related_document_id as target_id,
               d.document_number as number, d.document_date as date, 
               rd.created_at, rd.description,
               'RELATED' as link_type
        FROM {schema}.related_documents rd
        JOIN {schema}.documents d ON rd.related_document_id = d.id
        WHERE rd.document_id = %s AND rd.relation_type = 'reference'
    """, (source_id,))
    related_links = cursor.fetchall()
    
    return {
        'VERSION': [dict(link) for link in version_links],
        'RELATED': [dict(link) for link in related_links]
    }


def process_single_document(cursor, conn, schema: str, session_id: str, 
                            doc: dict) -> dict:
    """Обработать один документ: скачать файл, найти упоминания, создать связи"""
    doc_id = doc['id']
    doc_number = doc['number']
    doc_date = doc['date']
    file_url = doc['file_url']
    file_format = doc['format']
    
    start_time = time.time()
    stats = {
        'version_mentions': 0,
        'related_mentions': 0,
        'links_created': 0,
        'links_skipped': 0,
        'links_deleted': 0,
        'phantoms_created': 0,
        'errors': 0
    }
    
    t1 = time.time()
    content, error = download_file(file_url)
    download_duration = int((time.time() - t1) * 1000)
    
    if error:
        log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                'file_download', 'error', {
                    'url': file_url,
                    'error': error,
                    'duration_ms': download_duration
                })
        conn.commit()
        stats['errors'] += 1
        return stats
    
    file_size_kb = len(content) / 1024
    log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
            'file_download', 'success', {
                'url': file_url,
                'size_kb': round(file_size_kb, 1),
                'duration_ms': download_duration
            })
    conn.commit()
    
    t2 = time.time()
    if file_format == 'docx':
        text, parse_stats, error = parse_docx(content)
    else:
        text, parse_stats, error = parse_pdf(content)
    
    parse_duration = int((time.time() - t2) * 1000)
    
    if error:
        log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                'file_parse', 'error', {
                    'format': file_format,
                    'error': error,
                    'duration_ms': parse_duration
                })
        conn.commit()
        stats['errors'] += 1
        return stats
    
    parse_stats['duration_ms'] = parse_duration
    log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
            'file_parse', 'success', parse_stats)
    conn.commit()
    
    mentions = extract_mentions(text)
    
    version_keywords_found = []
    related_keywords_found = []
    classified_mentions = []
    
    for mention in mentions:
        mention_type, keywords = classify_mention(mention['context'])
        if mention_type == 'VERSION':
            version_keywords_found.extend(keywords)
            stats['version_mentions'] += 1
        elif mention_type == 'RELATED':
            related_keywords_found.extend(keywords)
            stats['related_mentions'] += 1
        
        mention['type'] = mention_type
        mention['keywords'] = keywords
        classified_mentions.append(mention)
    
    log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
            'pattern_search', 'info', {
                'version_keywords_found': list(set(version_keywords_found)),
                'related_keywords_found': list(set(related_keywords_found)),
                'total_mentions': len(classified_mentions),
                'mentions': classified_mentions
            })
    conn.commit()
    
    existing_links = get_existing_links(cursor, schema, doc_id)
    found_targets = {'VERSION': set(), 'RELATED': set()}
    
    for mention in classified_mentions:
        if mention['type'] == 'UNKNOWN':
            continue
        
        is_external, exclusion_phrase = is_external_document(mention['context'])
        
        if is_external:
            log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                    'link_skip', 'info', {
                        'target_number': mention['number'],
                        'target_date': mention['date'],
                        'reason': 'external_document',
                        'exclusion_phrase': exclusion_phrase,
                        'context': mention['context'][:200]
                    })
            conn.commit()
            continue
        
        target_id = find_document_in_db(cursor, schema, mention['number'], mention['date'])
        
        if not target_id:
            try:
                target_id = create_phantom_document(cursor, schema, mention['number'], mention['date'])
                log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                        'phantom_create', 'success', {
                            'phantom_id': target_id,
                            'phantom_number': mention['number'],
                            'phantom_date': mention['date'],
                            'reason': 'mentioned_in_text',
                            'context': mention['context'][:200]
                        })
                conn.commit()
                stats['phantoms_created'] += 1
            except Exception as e:
                log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                        'phantom_create', 'error', {
                            'target_number': mention['number'],
                            'target_date': mention['date'],
                            'error': str(e)
                        })
                conn.commit()
                stats['errors'] += 1
                continue
        
        found_targets[mention['type']].add(target_id)
        
        existing_link = check_existing_link(cursor, schema, doc_id, target_id, mention['type'])
        
        if existing_link:
            log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                    'link_skip', 'warning', {
                        'target_document_id': target_id,
                        'target_number': mention['number'],
                        'target_date': mention['date'],
                        'link_type': mention['type'],
                        'reason': 'already_exists',
                        'existing_link_id': existing_link['id'],
                        'created_at': str(existing_link['created_at']),
                        'pattern': mention['pattern'],
                        'keywords': mention['keywords']
                    })
            conn.commit()
            stats['links_skipped'] += 1
        else:
            try:
                link_id = create_link(cursor, schema, doc_id, target_id, 
                                     mention['type'], mention['context'])
                log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                        'link_create', 'success', {
                            'link_id': link_id,
                            'target_document_id': target_id,
                            'target_number': mention['number'],
                            'target_date': mention['date'],
                            'link_type': mention['type'],
                            'pattern': mention['pattern'],
                            'keywords': mention['keywords'],
                            'context': mention['context'][:200]
                        })
                conn.commit()
                stats['links_created'] += 1
            except Exception as e:
                log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                        'link_create', 'error', {
                            'target_number': mention['number'],
                            'target_date': mention['date'],
                            'link_type': mention['type'],
                            'error': str(e)
                        })
                conn.commit()
                stats['errors'] += 1
    
    for link_type in ['VERSION', 'RELATED']:
        for old_link in existing_links[link_type]:
            if old_link['target_id'] not in found_targets[link_type]:
                delete_link(cursor, schema, old_link['id'], link_type)
                log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                        'link_delete', 'warning', {
                            'deleted_link_id': old_link['id'],
                            'target_id': old_link['target_id'],
                            'target_number': old_link['number'],
                            'target_date': str(old_link['date']),
                            'link_type': link_type,
                            'reason': 'not_found_in_new_scan',
                            'original_context': old_link['description'][:200],
                            'original_created_at': str(old_link['created_at'])
                        })
                conn.commit()
                stats['links_deleted'] += 1
    
    total_duration = int((time.time() - start_time) * 1000)
    log_step(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
            'document_completed', 'success', {
                'total_duration_ms': total_duration,
                'stats': stats
            })
    conn.commit()
    
    return stats


def find_all_relations(cursor, conn, schema: str) -> dict:
    """Главная функция: найти связи для ВСЕХ документов с файлами"""
    session_id = str(uuid.uuid4())
    
    cursor.execute(f"""
        SELECT COUNT(*) as total
        FROM {schema}.documents d
        INNER JOIN {schema}.document_files df ON d.id = df.document_id
        WHERE df.status = 'completed'
    """)
    total_documents = cursor.fetchone()['total']
    
    log_step(cursor, schema, session_id, None, None, None,
            'session_start', 'info', {
                'total_documents': total_documents,
                'started_at': datetime.now().isoformat()
            })
    conn.commit()
    
    cursor.execute(f"""
        SELECT d.id, d.document_number as number, d.document_date as date, 
               df.url as file_url, df.format
        FROM {schema}.documents d
        INNER JOIN {schema}.document_files df ON d.id = df.document_id
        WHERE df.status = 'completed'
        ORDER BY d.document_date DESC, d.document_number DESC
    """)
    documents = cursor.fetchall()
    
    total_stats = {
        'total_processed': 0,
        'version_mentions': 0,
        'related_mentions': 0,
        'links_created': 0,
        'links_skipped': 0,
        'links_deleted': 0,
        'phantoms_created': 0,
        'errors': 0
    }
    
    for doc in documents:
        doc_stats = process_single_document(cursor, conn, schema, session_id, doc)
        total_stats['total_processed'] += 1
        for key in doc_stats:
            total_stats[key] += doc_stats[key]
    
    log_step(cursor, schema, session_id, None, None, None,
            'session_completed', 'success', {
                'finished_at': datetime.now().isoformat(),
                'final_stats': total_stats
            })
    conn.commit()
    
    return {
        'status': 'completed',
        'session_id': session_id,
        'total_documents': total_documents,
        **total_stats
    }