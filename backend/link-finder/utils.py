'''
Вспомогательные функции общего назначения.
'''

import re
from datetime import datetime
from constants import MAX_DOC_NUMBER_LENGTH, MIN_YEAR

def validate_document_number(number: str) -> bool:
    '''Проверяет корректность номера документа'''
    return len(number) <= MAX_DOC_NUMBER_LENGTH

def validate_document_date(date_str: str) -> bool:
    '''Проверяет корректность даты документа'''
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        current_year = datetime.now().year
        return MIN_YEAR <= date_obj.year <= current_year + 1
    except:
        return False

def format_date(date_str: str) -> str:
    '''Преобразует дату из формата DD.MM.YYYY в YYYY-MM-DD'''
    date_obj = datetime.strptime(date_str, '%d.%m.%Y')
    return date_obj.strftime('%Y-%m-%d')

def is_excluded_context(text: str, exclusion_phrases: list) -> bool:
    '''Проверяет содержит ли текст фразы-исключения'''
    for exclusion in exclusion_phrases:
        if re.search(exclusion, text, re.IGNORECASE):
            return True
    return False

def deduplicate_references(references: list) -> list:
    '''Убирает дубликаты из списка ссылок'''
    unique_refs = []
    seen = set()
    for ref in references:
        key = f"{ref.number}_{ref.date}"
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    return unique_refs