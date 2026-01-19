'''
Модели данных для работы с документами.
'''

from dataclasses import dataclass
from typing import Optional

@dataclass
class DocumentReference:
    '''Ссылка на документ найденная в тексте'''
    number: str
    date: str  # YYYY-MM-DD
    context: str = ''  # Контекст упоминания

@dataclass
class ParseResult:
    '''Результат парсинга документа'''
    versions: list[DocumentReference]  # Ссылки на предыдущие версии
    related: list[DocumentReference]   # Связанные документы

@dataclass
class ProcessingResult:
    '''Результат обработки одного документа'''
    document_id: int
    document_number: str
    status: str  # 'success', 'no_references', 'error', 'skipped'
    versions_created: int = 0
    related_created: int = 0
    phantoms_created: int = 0
    found_versions: list = None
    found_related: list = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.found_versions is None:
            self.found_versions = []
        if self.found_related is None:
            self.found_related = []
