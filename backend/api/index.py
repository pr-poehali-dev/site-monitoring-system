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
            elif endpoint == 'parsing_progress':
                result = get_parsing_progress(cursor, schema)
            elif endpoint == 'analytics':
                result = get_analytics(cursor, schema)
            elif endpoint == 'file_download_stats':
                result = get_file_download_stats(cursor, schema)
            elif endpoint == 'document_versions':
                document_id = query_params.get('document_id')
                if not document_id:
                    return error_response('document_id обязателен', 400)
                result = get_document_versions(cursor, schema, int(document_id))
            elif endpoint == 'link_finding_logs':
                result = get_link_finding_logs(cursor, schema, query_params)
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
            elif endpoint == 'clean_logs':
                body = json.loads(event.get('body', '{}'))
                days = body.get('days', 7)
                result = clean_old_logs(cursor, schema, days)
                conn.commit()
                cursor.close()
                conn.close()
                return success_response(result)
            elif endpoint == 'retry_failed_downloads':
                result = retry_failed_downloads(cursor, schema)
                conn.commit()
                cursor.close()
                conn.close()
                return success_response(result)
            elif endpoint == 'remove_duplicates':
                result = remove_duplicate_documents(cursor, schema)
                conn.commit()
                cursor.close()
                conn.close()
                return success_response(result)
            elif endpoint == 'full_reset':
                result = full_database_reset(cursor, schema)
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
    only_actual = params.get('only_actual', '')
    only_real = params.get('only_real', '')
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
    
    if only_actual and only_actual.lower() == 'true':
        # Показываем только документы, у которых нет более новых версий
        # (т.е. на них никто не ссылается через related_to)
        # И исключаем фантомные документы (они по определению НЕ актуальные)
        where_clauses.append("related_count = 0 AND (is_phantom IS NULL OR is_phantom = FALSE)")
    
    if only_real and only_real.lower() == 'true':
        # Показываем только реальные документы (не фантомные)
        where_clauses.append("(is_phantom IS NULL OR is_phantom = FALSE)")
    
    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
    
    allowed_sorts = ['created_at', 'document_date', 'published_date', 'title', 'changes_count', 'file_size', 'related_count', 'total_versions']
    if sort_by not in allowed_sorts:
        sort_by = 'created_at'
    if sort_order.upper() not in ['ASC', 'DESC']:
        sort_order = 'DESC'
    
    # Для сортировки по related_count используем total_versions (сумма related_count + prev_versions_count)
    if sort_by == 'related_count':
        order_sql = f"ORDER BY (d.related_count + (SELECT COUNT(*) FROM {schema}.document_relations dr WHERE dr.source_document_id = d.id)) {sort_order} NULLS LAST"
    else:
        order_sql = f"ORDER BY {sort_by} {sort_order} NULLS LAST"
    
    cursor.execute(f"""
        SELECT d.id, d.title, d.url, d.section, d.published_date, d.document_date, d.document_number, 
               d.file_size, d.file_cdn_url, d.changes_count, d.last_checked_at, d.created_at,
               d.related_to, d.is_actual, d.related_count, d.is_phantom, d.phantom_source_id,
               (SELECT COUNT(*) FROM {schema}.document_relations dr WHERE dr.source_document_id = d.id) as prev_versions_count,
               (d.related_count + (SELECT COUNT(*) FROM {schema}.document_relations dr WHERE dr.source_document_id = d.id)) as total_versions
        FROM {schema}.documents d
        WHERE {where_sql}
        {order_sql}
        LIMIT %s OFFSET %s
    """, (*query_params, limit, offset))
    
    documents = cursor.fetchall()
    
    doc_ids = [d['id'] for d in documents]
    if doc_ids:
        placeholders = ','.join(['%s'] * len(doc_ids))
        cursor.execute(f"""
            SELECT document_id, file_url, file_type, file_name, file_size, 
                   file_cdn_url, content_hash
            FROM {schema}.document_files
            WHERE document_id IN ({placeholders})
            ORDER BY document_id, CASE WHEN file_type = 'main' THEN 0 ELSE 1 END
        """, doc_ids)
        
        files_by_doc = {}
        for f in cursor.fetchall():
            did = f['document_id']
            if did not in files_by_doc:
                files_by_doc[did] = []
            files_by_doc[did].append(f)
        
        for doc in documents:
            doc['files'] = files_by_doc.get(doc['id'], [])
    
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
               dc.old_content_hash, dc.new_content_hash,
               d.title, d.url, d.section, d.file_cdn_url, d.document_number
        FROM {schema}.document_changes dc
        JOIN {schema}.documents d ON dc.document_id = d.id
        {where_clause}
        ORDER BY dc.detected_at DESC
        LIMIT %s
    """, (*query_params, limit))
    
    changes = cursor.fetchall()
    
    # Для каждого изменения получаем старые файлы (если есть)
    for change in changes:
        # Текущие файлы документа
        cursor.execute(f"""
            SELECT file_url, file_cdn_url, file_type, file_name 
            FROM {schema}.document_files 
            WHERE document_id = (
                SELECT document_id FROM {schema}.document_changes WHERE id = %s
            )
            ORDER BY CASE WHEN file_type = 'main' THEN 0 ELSE 1 END
        """, (change['id'],))
        change['current_files'] = cursor.fetchall()
    
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


def get_link_finding_logs(cursor, schema: str, params: dict) -> dict:
    """Получение логов поиска связей"""
    limit = int(params.get('limit', '100'))
    
    cursor.execute(f"""
        SELECT 
            lfl.id,
            lfl.document_id,
            lfl.document_number,
            lfl.status,
            lfl.references_found,
            lfl.links_created,
            lfl.not_found_refs,
            lfl.message,
            lfl.created_at,
            d.title as document_title
        FROM {schema}.link_finding_logs lfl
        LEFT JOIN {schema}.documents d ON lfl.document_id = d.id
        ORDER BY lfl.created_at DESC
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
    
    cursor.execute(f"""
        SELECT COUNT(*) as total 
        FROM {schema}.documents
        WHERE related_to IS NULL AND related_count = 0 AND file_cdn_url IS NOT NULL
    """)
    total_without_relations = cursor.fetchone()['total']
    
    cursor.execute(f"""
        SELECT COUNT(*) as total 
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
    """)
    unprocessed_for_links = cursor.fetchone()['total']
    
    return {
        'total_documents': total_docs,
        'changes_this_week': changes_week,
        'active_sections': active_sections,
        'total_without_relations': total_without_relations,
        'unprocessed_for_links': unprocessed_for_links
    }


def get_analytics(cursor, schema: str) -> dict:
    """Получение аналитики по документам"""
    
    # Статистика по разделам
    cursor.execute(f"""
        SELECT section, COUNT(*) as count
        FROM {schema}.documents
        GROUP BY section
        ORDER BY count DESC
    """)
    by_section = cursor.fetchall()
    
    # Статистика по годам (берем год из document_date или published_date)
    # Фильтруем аномальные года (только 2009-2026)
    cursor.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM COALESCE(document_date, published_date, created_at))::integer as year,
            section,
            COUNT(*) as count
        FROM {schema}.documents
        WHERE COALESCE(document_date, published_date, created_at) IS NOT NULL
            AND EXTRACT(YEAR FROM COALESCE(document_date, published_date, created_at))::integer BETWEEN 2009 AND 2026
        GROUP BY year, section
        ORDER BY year DESC, section
    """)
    by_year_section = cursor.fetchall()
    
    # Общая статистика по годам
    cursor.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM COALESCE(document_date, published_date, created_at))::integer as year,
            COUNT(*) as count
        FROM {schema}.documents
        WHERE COALESCE(document_date, published_date, created_at) IS NOT NULL
            AND EXTRACT(YEAR FROM COALESCE(document_date, published_date, created_at))::integer BETWEEN 2009 AND 2026
        GROUP BY year
        ORDER BY year DESC
    """)
    by_year = cursor.fetchall()
    
    # Динамика публикаций (последние 5 лет = 1825 дней)
    # Генерируем все даты, даже с 0 документов
    cursor.execute(f"""
        WITH date_series AS (
            SELECT generate_series(
                CURRENT_DATE - INTERVAL '5 years',
                CURRENT_DATE,
                '1 day'::interval
            )::date as date
        )
        SELECT 
            TO_CHAR(ds.date, 'DD.MM.YYYY') as date,
            COALESCE(COUNT(d.id), 0) as count
        FROM date_series ds
        LEFT JOIN {schema}.documents d ON DATE(COALESCE(d.published_date, d.created_at)) = ds.date
        GROUP BY ds.date
        ORDER BY ds.date ASC
    """)
    by_publication_date = cursor.fetchall()
    
    # Общая статистика
    cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.documents")
    total_documents = cursor.fetchone()['total']
    
    cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.document_files")
    total_files = cursor.fetchone()['total']
    
    # Документы без файлов (учитываем новую структуру с download_status)
    cursor.execute(f"""
        SELECT COUNT(*) as total 
        FROM {schema}.documents d 
        WHERE NOT EXISTS (
            SELECT 1 FROM {schema}.document_files f 
            WHERE f.document_id = d.id AND f.download_status = 'downloaded'
        )
    """)
    documents_without_files = cursor.fetchone()['total']
    
    # Документы с несколькими файлами (приложения)
    cursor.execute(f"""
        SELECT COUNT(*) as total 
        FROM (
            SELECT document_id 
            FROM {schema}.document_files 
            GROUP BY document_id 
            HAVING COUNT(*) > 1
        ) sub
    """)
    documents_with_multiple_files = cursor.fetchone()['total']
    
    cursor.execute(f"SELECT COALESCE(SUM(file_size), 0) as total_size FROM {schema}.documents")
    total_size_bytes = cursor.fetchone()['total_size']
    total_size_mb = round(total_size_bytes / (1024 * 1024), 2) if total_size_bytes else 0
    
    return {
        'by_section': by_section,
        'by_year': by_year,
        'by_year_section': by_year_section,
        'by_publication_date': by_publication_date,
        'total_documents': total_documents,
        'total_files': total_files,
        'documents_without_files': documents_without_files,
        'documents_with_multiple_files': documents_with_multiple_files,
        'total_size_mb': total_size_mb
    }


def get_parsing_progress(cursor, schema: str) -> dict:
    """Получение прогресса парсинга"""
    cursor.execute(f"""
        SELECT section, year, page, status, retry_count, last_error, updated_at
        FROM {schema}.parsing_state
        ORDER BY 
            CASE section 
                WHEN 'programmy' THEN 1 
                WHEN 'rasporyazheniya' THEN 2 
                WHEN 'postanovleniya' THEN 3 
                ELSE 4 
            END,
            year DESC
    """)
    states = cursor.fetchall()
    
    total = len(states)
    completed = sum(1 for s in states if s['status'] == 'completed')
    running = [s for s in states if s['status'] in ('running', 'retry', 'pending')]
    failed = [s for s in states if s['status'] == 'failed']
    
    section_names = {
        'programmy': 'Муниципальные программы',
        'rasporyazheniya': 'Распоряжения',
        'postanovleniya': 'Постановления'
    }
    
    current_task = None
    if running:
        task = running[0]
        current_task = {
            'section': section_names.get(task['section'], task['section']),
            'year': task['year'],
            'page': task['page'],
            'status': task['status']
        }
    
    return {
        'total_tasks': total,
        'completed_tasks': completed,
        'progress_percent': round((completed / total * 100) if total > 0 else 0, 1),
        'current_task': current_task,
        'running_count': len(running),
        'failed_count': len(failed),
        'all_states': states
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


def clean_old_logs(cursor, schema: str, days: int = 7) -> dict:
    """Очистка старых логов парсинга"""
    cursor.execute(f"""
        DELETE FROM {schema}.parsing_logs
        WHERE started_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
    """, (days,))
    
    deleted_count = cursor.rowcount
    
    return {
        'deleted': deleted_count,
        'days': days,
        'message': f'Удалено {deleted_count} старых логов (старше {days} дней)'
    }


def get_file_download_stats(cursor, schema: str) -> dict:
    """Получение статистики по загрузке файлов"""
    # Автоисправление: помечаем файлы с CDN URL как downloaded
    cursor.execute(f"""
        UPDATE {schema}.document_files
        SET download_status = 'downloaded'
        WHERE download_status = 'pending' 
            AND file_cdn_url IS NOT NULL 
            AND file_cdn_url != ''
    """)
    
    # Всего файлов по статусам
    cursor.execute(f"""
        SELECT download_status, COUNT(*) as count
        FROM {schema}.document_files
        GROUP BY download_status
    """)
    status_counts = {row['download_status']: row['count'] for row in cursor.fetchall()}
    
    total_files = sum(status_counts.values())
    downloaded = status_counts.get('downloaded', 0)
    pending = status_counts.get('pending', 0)
    failed = status_counts.get('failed', 0)
    
    return {
        'total_files': total_files,
        'downloaded': downloaded,
        'pending': pending,
        'failed': failed,
        'status_counts': status_counts
    }


def retry_failed_downloads(cursor, schema: str) -> dict:
    """Сброс статуса для повторной попытки загрузки файлов"""
    # Обновляем статус pending -> можно будет загрузить через parser
    cursor.execute(f"""
        UPDATE {schema}.document_files
        SET download_status = 'pending'
        WHERE download_status IN ('pending', 'failed')
            OR (download_status = 'downloaded' AND (file_cdn_url IS NULL OR file_cdn_url = ''))
    """)
    
    updated_count = cursor.rowcount
    
    return {
        'updated': updated_count,
        'message': f'Помечено {updated_count} файлов для повторной загрузки'
    }


def remove_duplicate_documents(cursor, schema: str) -> dict:
    """Удаление дублирующихся документов из базы данных"""
    
    # Шаг 1: Подсчет дублей перед удалением
    cursor.execute(f"""
        SELECT COUNT(*) as duplicate_groups
        FROM (
            SELECT document_number, document_date, title, COUNT(*) as cnt
            FROM {schema}.documents
            WHERE document_number IS NOT NULL
            GROUP BY document_number, document_date, title
            HAVING COUNT(*) > 1
        ) dups
    """)
    duplicate_groups = cursor.fetchone()['duplicate_groups']
    
    # Шаг 2: Найти ID дублей для удаления (оставляем самую новую запись)
    cursor.execute(f"""
        SELECT id
        FROM (
            SELECT 
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY document_number, document_date, title 
                    ORDER BY created_at DESC, id DESC
                ) as rn
            FROM {schema}.documents
            WHERE document_number IS NOT NULL
        ) ranked
        WHERE rn > 1
    """)
    
    ids_to_delete = [row['id'] for row in cursor.fetchall()]
    count_to_delete = len(ids_to_delete)
    
    if count_to_delete == 0:
        return {
            'deleted_documents': 0,
            'deleted_changes': 0,
            'deleted_files': 0,
            'duplicate_groups': 0,
            'message': 'Дубликаты не найдены'
        }
    
    # Шаг 3: Удаление связанных записей из document_changes
    placeholders = ','.join(['%s'] * len(ids_to_delete))
    cursor.execute(f"""
        DELETE FROM {schema}.document_changes
        WHERE document_id IN ({placeholders})
    """, ids_to_delete)
    deleted_changes = cursor.rowcount
    
    # Шаг 4: Удаление связанных записей из document_files
    cursor.execute(f"""
        DELETE FROM {schema}.document_files
        WHERE document_id IN ({placeholders})
    """, ids_to_delete)
    deleted_files = cursor.rowcount
    
    # Шаг 5: Удаление самих дублей
    cursor.execute(f"""
        DELETE FROM {schema}.documents
        WHERE id IN ({placeholders})
    """, ids_to_delete)
    deleted_documents = cursor.rowcount
    
    return {
        'deleted_documents': deleted_documents,
        'deleted_changes': deleted_changes,
        'deleted_files': deleted_files,
        'duplicate_groups': duplicate_groups,
        'message': f'Удалено {deleted_documents} дубликатов из {duplicate_groups} групп'
    }


def full_database_reset(cursor, schema: str) -> dict:
    """Полная очистка базы данных - удаление всех документов, изменений, файлов и логов"""
    
    # Подсчитываем что будет удалено
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.documents")
    docs_count = cursor.fetchone()['cnt']
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.document_changes")
    changes_count = cursor.fetchone()['cnt']
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.document_files")
    files_count = cursor.fetchone()['cnt']
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.parsing_logs")
    logs_count = cursor.fetchone()['cnt']
    
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {schema}.parsing_state")
    state_count = cursor.fetchone()['cnt']
    
    # Удаляем все данные (кроме настроек)
    cursor.execute(f"DELETE FROM {schema}.document_changes")
    cursor.execute(f"DELETE FROM {schema}.document_files")
    cursor.execute(f"DELETE FROM {schema}.documents")
    cursor.execute(f"DELETE FROM {schema}.parsing_logs")
    cursor.execute(f"DELETE FROM {schema}.parsing_state")
    
    # Сбрасываем sequences для автоинкрементов
    cursor.execute(f"ALTER SEQUENCE {schema}.documents_id_seq RESTART WITH 1")
    cursor.execute(f"ALTER SEQUENCE {schema}.document_changes_id_seq RESTART WITH 1")
    cursor.execute(f"ALTER SEQUENCE {schema}.document_files_id_seq RESTART WITH 1")
    cursor.execute(f"ALTER SEQUENCE {schema}.parsing_logs_id_seq RESTART WITH 1")
    cursor.execute(f"ALTER SEQUENCE {schema}.parsing_state_id_seq RESTART WITH 1")
    
    return {
        'deleted_documents': docs_count,
        'deleted_changes': changes_count,
        'deleted_files': files_count,
        'deleted_logs': logs_count,
        'deleted_state': state_count,
        'message': f'База данных полностью очищена. Удалено: {docs_count} документов, {changes_count} изменений, {files_count} файлов, {logs_count} логов'
    }


def get_document_versions(cursor, schema: str, document_id: int) -> dict:
    """Получение всех версий документа (актуальный + предыдущие версии)
    Использует таблицу document_relations для получения ВСЕХ связей (many-to-many)"""
    
    # Получаем сам документ
    cursor.execute(f"""
        SELECT id, title, url, section, published_date, document_date, document_number,
               file_size, file_cdn_url, created_at, related_to, is_actual, related_count, is_phantom, phantom_source_id
        FROM {schema}.documents
        WHERE id = %s
    """, (document_id,))
    current_doc = cursor.fetchone()
    
    if not current_doc:
        return {'error': 'Документ не найден', 'versions': []}
    
    # Получаем все документы, которые ссылаются на текущий (это новые версии)
    cursor.execute(f"""
        SELECT d.id, d.title, d.url, d.section, d.published_date, d.document_date, d.document_number,
               d.file_size, d.file_cdn_url, d.created_at, d.related_to, d.is_actual, d.related_count, d.is_phantom, d.phantom_source_id
        FROM {schema}.documents d
        INNER JOIN {schema}.document_relations dr ON dr.source_document_id = d.id
        WHERE dr.target_document_id = %s
    """, (document_id,))
    newer_versions = cursor.fetchall()
    
    # Получаем все документы, на которые ссылается текущий (это старые версии)
    cursor.execute(f"""
        SELECT d.id, d.title, d.url, d.section, d.published_date, d.document_date, d.document_number,
               d.file_size, d.file_cdn_url, d.created_at, d.related_to, d.is_actual, d.related_count, d.is_phantom, d.phantom_source_id
        FROM {schema}.documents d
        INNER JOIN {schema}.document_relations dr ON dr.target_document_id = d.id
        WHERE dr.source_document_id = %s
    """, (document_id,))
    older_versions = cursor.fetchall()
    
    # Определяем актуальную версию (самая новая из всех)
    all_docs = [current_doc] + newer_versions + older_versions
    # Сортируем все документы по дате (самый новый = актуальный)
    from datetime import datetime
    min_date = datetime(1900, 1, 1)
    all_docs_sorted = sorted(all_docs, key=lambda x: (
        x['document_date'] or x['published_date'] or x['created_at'] or min_date,
        x['created_at'] or min_date
    ), reverse=True)
    
    # Удаляем дубликаты по ID
    seen_ids = set()
    unique_docs = []
    for doc in all_docs_sorted:
        if doc['id'] not in seen_ids:
            seen_ids.add(doc['id'])
            unique_docs.append(doc)
    
    if not unique_docs:
        return {'error': 'Документы не найдены', 'versions': []}
    
    # Первый документ в отсортированном списке - актуальная версия
    latest = unique_docs[0]
    # Остальные - предыдущие версии
    previous_versions = unique_docs[1:]
    
    # Получаем файлы для всех документов
    all_ids = [d['id'] for d in unique_docs]
    if all_ids:
        placeholders = ','.join(['%s'] * len(all_ids))
        cursor.execute(f"""
            SELECT document_id, file_url, file_type, file_name, file_size, file_cdn_url
            FROM {schema}.document_files
            WHERE document_id IN ({placeholders})
            ORDER BY document_id, CASE WHEN file_type = 'main' THEN 0 ELSE 1 END
        """, all_ids)
        
        files_by_doc = {}
        for f in cursor.fetchall():
            did = f['document_id']
            if did not in files_by_doc:
                files_by_doc[did] = []
            files_by_doc[did].append(f)
        
        # Добавляем файлы к документам
        latest['files'] = files_by_doc.get(latest['id'], [])
        for v in previous_versions:
            v['files'] = files_by_doc.get(v['id'], [])
    else:
        latest['files'] = []
        for v in previous_versions:
            v['files'] = []
    
    return {
        'latest': latest,
        'versions': previous_versions,
        'total_versions': len(unique_docs)
    }


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