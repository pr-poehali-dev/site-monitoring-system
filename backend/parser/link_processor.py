"""Обработка одного документа для поиска связей"""
import time
from typing import Dict
from link_parser import download_file, parse_docx, parse_pdf
from link_patterns import extract_mentions, classify_mention, is_external_document
from link_db import (log_step, find_document_in_db, create_phantom_document,
                     check_existing_link, create_link, delete_link, get_existing_links)


def process_single_document(cursor, conn, schema: str, session_id: str, doc: dict) -> dict:
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
    
    # Скачивание файла
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
    
    # Парсинг файла
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
    
    # Извлечение упоминаний
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
    
    # Обработка найденных упоминаний
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
    
    # Удаление устаревших связей
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
