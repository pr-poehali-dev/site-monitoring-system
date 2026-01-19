"""Обработка одного документа для поиска связей"""
import time
import sys
import os
from typing import Dict
import json

# Добавляем текущую директорию в путь для импорта локальных модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import link_parser
import link_patterns
import link_db

download_file = link_parser.download_file
parse_docx = link_parser.parse_docx
parse_pdf = link_parser.parse_pdf
extract_mentions = link_patterns.extract_mentions
classify_mention = link_patterns.classify_mention
find_document_in_db = link_db.find_document_in_db
create_phantom_document = link_db.create_phantom_document
check_existing_link = link_db.check_existing_link
create_link = link_db.create_link
delete_link = link_db.delete_link
get_existing_links = link_db.get_existing_links


def log_file_processing(cursor, schema: str, session_id: str, doc_id: int, 
                        doc_number: str, doc_date: str, status: str, details: dict):
    """Записать один общий лог по файлу со всеми этапами"""
    cursor.execute(f"""
        INSERT INTO {schema}.link_finding_logs 
        (session_id, document_id, document_number, document_date, step, status, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (session_id, doc_id, doc_number, doc_date, 'file_processing', status, 
         json.dumps(details, ensure_ascii=False)))


def process_single_document(cursor, conn, schema: str, session_id: str, doc: dict) -> dict:
    """Обработать один документ: скачать файл, найти упоминания, создать связи"""
    doc_id = doc['id']
    doc_number = doc['number']
    doc_date = doc['date']
    file_url = doc['file_url']
    file_format = doc['format']
    
    file_start = time.time()
    
    # Общий результат обработки файла
    file_result = {
        'document_id': doc_id,
        'document_number': doc_number,
        'document_date': str(doc_date),
        'file_url': file_url,
        'file_format': file_format,
        'stages': {},
        'stats': {
            'version_mentions': 0,
            'related_mentions': 0,
            'links_created': 0,
            'links_skipped': 0,
            'links_deleted': 0,
            'phantoms_created': 0,
            'errors': 0
        }
    }
    
    stats = file_result['stats']
    
    # ЭТАП 1: Скачивание файла
    t1 = time.time()
    content, error = download_file(file_url)
    download_duration = int((time.time() - t1) * 1000)
    
    if error:
        file_result['stages']['download'] = {
            'status': 'error',
            'error': error,
            'duration_ms': download_duration
        }
        stats['errors'] += 1
        file_duration = int((time.time() - file_start) * 1000)
        file_result['total_duration_ms'] = file_duration
        log_file_processing(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                           'error', file_result)
        conn.commit()
        return stats
    
    file_size_kb = round(len(content) / 1024, 1)
    file_result['stages']['download'] = {
        'status': 'success',
        'size_kb': file_size_kb,
        'duration_ms': download_duration
    }
    
    # ЭТАП 2: Парсинг файла
    t2 = time.time()
    if file_format == 'docx':
        text, parse_stats, error = parse_docx(content)
    else:
        text, parse_stats, error = parse_pdf(content)
    
    parse_duration = int((time.time() - t2) * 1000)
    
    if error:
        file_result['stages']['parse'] = {
            'status': 'error',
            'error': error,
            'duration_ms': parse_duration
        }
        stats['errors'] += 1
        file_duration = int((time.time() - file_start) * 1000)
        file_result['total_duration_ms'] = file_duration
        log_file_processing(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                           'error', file_result)
        conn.commit()
        return stats
    
    file_result['stages']['parse'] = {
        'status': 'success',
        'format': file_format,
        'text_length': len(text),
        'paragraphs': parse_stats.get('paragraphs', parse_stats.get('pages', 0)),
        'duration_ms': parse_duration
    }
    
    # ЭТАП 3: Извлечение упоминаний
    mentions = extract_mentions(text)
    
    version_keywords = set()
    related_keywords = set()
    classified_mentions = []
    
    for mention in mentions:
        mention_type, keywords = classify_mention(mention['context'])
        
        mention['type'] = mention_type
        mention['keywords'] = keywords
        classified_mentions.append(mention)
        
        # Считаем только не-внешние упоминания
        if mention_type == 'VERSION':
            version_keywords.update(keywords)
            stats['version_mentions'] += 1
        elif mention_type == 'RELATED':
            related_keywords.update(keywords)
            stats['related_mentions'] += 1
    
    file_result['stages']['mentions'] = {
        'status': 'success',
        'total': len(classified_mentions),
        'version_count': stats['version_mentions'],
        'related_count': stats['related_mentions'],
        'version_keywords': list(version_keywords),
        'related_keywords': list(related_keywords)
    }
    
    # ЭТАП 4: Создание связей
    existing_links = get_existing_links(cursor, schema, doc_id)
    found_targets = {'VERSION': set(), 'RELATED': set()}
    
    links_actions = []
    
    for mention in classified_mentions:
        # Пропускаем только внешние документы
        if mention['type'] == 'EXTERNAL':
            links_actions.append({
                'action': 'skipped',
                'reason': 'external_document',
                'target_number': mention['number'],
                'target_date': mention['date'],
                'exclusion_phrase': mention['keywords'][0] if mention['keywords'] else ''
            })
            continue
        
        target_id = find_document_in_db(cursor, schema, mention['number'], mention['date'])
        
        if not target_id:
            try:
                target_id = create_phantom_document(cursor, schema, mention['number'], mention['date'])
                links_actions.append({
                    'action': 'phantom_created',
                    'phantom_id': target_id,
                    'phantom_number': mention['number'],
                    'phantom_date': mention['date']
                })
                stats['phantoms_created'] += 1
            except Exception as e:
                links_actions.append({
                    'action': 'phantom_error',
                    'target_number': mention['number'],
                    'target_date': mention['date'],
                    'error': str(e)[:200]
                })
                stats['errors'] += 1
                continue
        
        found_targets[mention['type']].add(target_id)
        
        existing_link = check_existing_link(cursor, schema, doc_id, target_id, mention['type'])
        
        if existing_link:
            links_actions.append({
                'action': 'skipped',
                'reason': 'already_exists',
                'link_type': mention['type'],
                'target_number': mention['number'],
                'target_date': mention['date'],
                'existing_link_id': existing_link['id']
            })
            stats['links_skipped'] += 1
        else:
            try:
                link_id = create_link(cursor, schema, doc_id, target_id, 
                                     mention['type'], mention['context'])
                links_actions.append({
                    'action': 'created',
                    'link_id': link_id,
                    'link_type': mention['type'],
                    'target_number': mention['number'],
                    'target_date': mention['date'],
                    'pattern': mention['pattern'],
                    'keywords': mention['keywords']
                })
                stats['links_created'] += 1
            except Exception as e:
                links_actions.append({
                    'action': 'create_error',
                    'target_number': mention['number'],
                    'target_date': mention['date'],
                    'error': str(e)[:200]
                })
                stats['errors'] += 1
    
    # ЭТАП 5: Удаление устаревших связей
    deleted_links = []
    for link_type in ['VERSION', 'RELATED']:
        for old_link in existing_links[link_type]:
            if old_link['target_id'] not in found_targets[link_type]:
                try:
                    delete_link(cursor, schema, old_link['id'], link_type)
                    deleted_links.append({
                        'link_id': old_link['id'],
                        'link_type': link_type,
                        'target_number': old_link['number'],
                        'target_date': str(old_link['date'])
                    })
                    stats['links_deleted'] += 1
                except Exception as e:
                    links_actions.append({
                        'action': 'delete_error',
                        'link_id': old_link['id'],
                        'error': str(e)[:200]
                    })
    
    file_result['stages']['links'] = {
        'status': 'success',
        'actions': links_actions,
        'deleted': deleted_links,
        'created': stats['links_created'],
        'skipped': stats['links_skipped'],
        'phantoms': stats['phantoms_created']
    }
    
    # Финальная запись лога
    file_duration = int((time.time() - file_start) * 1000)
    file_result['total_duration_ms'] = file_duration
    
    final_status = 'success' if stats['errors'] == 0 else 'warning'
    log_file_processing(cursor, schema, session_id, doc_id, doc_number, str(doc_date),
                       final_status, file_result)
    conn.commit()
    
    return stats