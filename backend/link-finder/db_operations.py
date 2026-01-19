'''
Операции с базой данных для работы с документами и связями.
'''

from models import DocumentReference, ProcessingResult

def get_or_create_phantom(cursor, schema: str, ref: DocumentReference, source_doc: dict) -> int:
    '''Получает существующий фантомный документ или создает новый.
    Возвращает ID фантома.
    '''
    # Проверяем существует ли фантом
    cursor.execute(f"""
        SELECT id FROM {schema}.documents
        WHERE document_number = %s
          AND document_date = %s
          AND is_phantom = TRUE
        LIMIT 1
    """, (ref.number, ref.date))
    
    existing = cursor.fetchone()
    if existing:
        return existing['id']
    
    # Создаем новый фантом
    phantom_title = f"Постановление {ref.number} от {ref.date}: [Файл не найден на сайте]"
    phantom_url = f"phantom://{ref.number}/{ref.date}/source-{source_doc['id']}"
    
    cursor.execute(f"""
        INSERT INTO {schema}.documents 
        (document_number, document_date, title, section, is_phantom, phantom_source_id, url)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        ref.number,
        ref.date,
        phantom_title,
        source_doc.get('section', 'Постановления'),
        True,
        source_doc['id'],
        phantom_url
    ))
    
    return cursor.fetchone()['id']

def create_version_relation(cursor, schema: str, source_id: int, target_id: int) -> bool:
    '''Создает связь версии между документами.
    Возвращает True если связь была создана (новая).
    '''
    cursor.execute(f"""
        INSERT INTO {schema}.document_relations 
        (source_document_id, target_document_id, relation_type)
        VALUES (%s, %s, 'previous_version')
        ON CONFLICT (source_document_id, target_document_id) DO NOTHING
    """, (source_id, target_id))
    
    return cursor.rowcount > 0

def create_related_relation(cursor, schema: str, source_id: int, related_id: int, context: str) -> bool:
    '''Создает связь со связанным документом.
    Возвращает True если связь была создана (новая).
    '''
    cursor.execute(f"""
        INSERT INTO {schema}.related_documents 
        (source_document_id, related_document_id, relation_type, context)
        VALUES (%s, %s, 'reference', %s)
        ON CONFLICT (source_document_id, related_document_id) DO NOTHING
    """, (source_id, related_id, context[:200]))
    
    return cursor.rowcount > 0

def update_version_counters(cursor, schema: str, old_doc_id: int, new_doc_id: int):
    '''Обновляет счетчики версий для документов'''
    # related_to у старого документа указывает на новый
    cursor.execute(f"""
        UPDATE {schema}.documents
        SET related_to = %s
        WHERE id = %s AND related_to IS NULL
    """, (new_doc_id, old_doc_id))
    
    # Увеличиваем счетчик новых версий у старого
    cursor.execute(f"""
        UPDATE {schema}.documents
        SET related_count = related_count + 1
        WHERE id = %s
    """, (old_doc_id,))

def update_related_counter(cursor, schema: str, doc_id: int):
    '''Увеличивает счетчик связанных документов'''
    cursor.execute(f"""
        UPDATE {schema}.documents
        SET related_docs_count = related_docs_count + 1
        WHERE id = %s
    """, (doc_id,))

def update_prev_versions_count(cursor, schema: str, doc_id: int):
    '''Пересчитывает количество предыдущих версий'''
    cursor.execute(f"""
        UPDATE {schema}.documents
        SET prev_versions_count = (
            SELECT COUNT(*)
            FROM {schema}.document_relations
            WHERE source_document_id = %s AND relation_type = 'previous_version'
        )
        WHERE id = %s
    """, (doc_id, doc_id))

def find_document(cursor, schema: str, number: str, date: str, exclude_id: int) -> dict:
    '''Ищет документ по номеру и дате'''
    cursor.execute(f"""
        SELECT id, document_number, document_date, title
        FROM {schema}.documents
        WHERE document_number = %s
          AND document_date = %s
          AND id != %s
        LIMIT 1
    """, (number, date, exclude_id))
    
    return cursor.fetchone()

def log_processing_result(
    cursor,
    schema: str,
    result: ProcessingResult,
    total_refs: int
):
    '''Сохраняет лог обработки документа'''
    message = f"Версий: {result.versions_created}, Связанных: {result.related_created}, Фантомов: {result.phantoms_created}"
    if result.error:
        message = result.error
    
    cursor.execute(f"""
        INSERT INTO {schema}.link_finding_logs 
        (document_id, document_number, status, references_found, links_created, phantoms_created, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        result.document_id,
        result.document_number,
        result.status,
        total_refs,
        result.versions_created + result.related_created,
        result.phantoms_created,
        message
    ))