"""Работа с БД для поиска связей"""
import json
from datetime import datetime
from typing import Optional, Dict, List


def log_step(cursor, schema: str, session_id: str, doc_id: Optional[int], 
             doc_number: Optional[str], doc_date: Optional[str],
             step: str, status: str, details: dict):
    """Записать шаг обработки в link_finding_logs"""
    cursor.execute(f"""
        INSERT INTO {schema}.link_finding_logs 
        (session_id, document_id, document_number, document_date, step, status, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (session_id, doc_id, doc_number, doc_date, step, status, json.dumps(details, ensure_ascii=False)))


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
