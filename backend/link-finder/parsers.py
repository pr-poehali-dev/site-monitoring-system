'''
Парсеры для извлечения ссылок из документов разных форматов.
'''

import re
from io import BytesIO
from models import DocumentReference, ParseResult
from constants import (
    EXCLUSION_PHRASES, VERSION_KEYWORDS, RELATED_KEYWORDS, DOCUMENT_PATTERNS
)
from utils import (
    validate_document_number, validate_document_date, format_date,
    is_excluded_context, deduplicate_references
)

def extract_from_docx(file_bytes: bytes) -> ParseResult:
    '''Извлекает ссылки из DOCX файла'''
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= 25:
                break
            text += para.text + "\n"
        
        return parse_text(text)
    except Exception as e:
        return ParseResult(versions=[], related=[])

def extract_from_doc(file_bytes: bytes) -> ParseResult:
    '''Извлекает ссылки из старого .doc файла'''
    try:
        import olefile
        ole = olefile.OleFileIO(file_bytes)
        # Простое извлечение текста
        text = file_bytes.decode('cp1251', errors='ignore')
        # Убираем бинарный мусор
        text = ''.join(c if c.isprintable() or c in '\n\r\t' else ' ' for c in text)
        return parse_text(text)
    except Exception as e:
        return ParseResult(versions=[], related=[])

def extract_from_pdf(file_bytes: bytes) -> ParseResult:
    '''Извлекает ссылки из PDF файла'''
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        
        text = ""
        for i in range(min(3, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\n"
        
        return parse_text(text)
    except Exception as e:
        return ParseResult(versions=[], related=[])

def parse_text(text: str) -> ParseResult:
    '''Парсит текст и находит ВЕРСИИ и СВЯЗАННЫЕ документы'''
    
    versions = []
    related = []
    
    # Первые 3 абзаца - ЗАГОЛОВОК (часто упоминается изменяемый документ)
    paragraphs = text.split('\n')
    title_text = '\n'.join(paragraphs[:3])
    
    # 1. Ищем ВЕРСИИ в заголовке
    title_versions = extract_references_from_context(
        title_text, None, EXCLUSION_PHRASES, is_title=True
    )
    versions.extend(title_versions)
    
    # 2. Ищем ВЕРСИИ в тексте с ключевыми фразами
    for keyword_pattern in VERSION_KEYWORDS:
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            # Для "в редакции" - больший контекст
            if 'редакции' in keyword_pattern:
                start_pos = max(0, keyword_match.start() - 100)
                end_pos = min(len(text), keyword_match.end() + 2000)
            else:
                start_pos = max(0, keyword_match.start() - 200)
                end_pos = min(len(text), keyword_match.end() + 300)
            
            context_text = text[start_pos:end_pos]
            found_refs = extract_references_from_context(
                context_text, keyword_pattern, EXCLUSION_PHRASES
            )
            versions.extend(found_refs)
    
    # 3. Ищем СВЯЗАННЫЕ документы в преамбуле
    for keyword_pattern in RELATED_KEYWORDS:
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            start_pos = max(0, keyword_match.start() - 50)
            end_pos = min(len(text), keyword_match.end() + 500)
            context_text = text[start_pos:end_pos]
            
            found_refs = extract_references_from_context(
                context_text, keyword_pattern, EXCLUSION_PHRASES
            )
            related.extend(found_refs)
    
    # Убираем дубликаты
    versions = deduplicate_references(versions)
    related = deduplicate_references(related)
    
    # Исключаем из related те что уже в versions
    version_keys = {f"{v.number}_{v.date}" for v in versions}
    related = [r for r in related if f"{r.number}_{r.date}" not in version_keys]
    
    return ParseResult(versions=versions, related=related)

def extract_references_from_context(
    context_text: str,
    keyword_pattern: str,
    exclusion_phrases: list,
    is_title: bool = False
) -> list[DocumentReference]:
    '''Извлекает ссылки на документы из контекста'''
    
    references = []
    
    for pattern, order in DOCUMENT_PATTERNS:
        for match in re.finditer(pattern, context_text, re.IGNORECASE):
            try:
                if order == 'date_first':
                    date_str = match.group(1)
                    number = match.group(2)
                else:  # number_first
                    number = match.group(1)
                    date_str = match.group(2)
                
                # Валидация
                if not validate_document_number(number):
                    continue
                if not validate_document_date(date_str):
                    continue
                
                # Проверяем контекст вокруг (±80 символов)
                match_start = match.start()
                sentence_start = max(0, match_start - 80)
                sentence_end = min(len(context_text), match.end() + 80)
                sentence = context_text[sentence_start:sentence_end]
                
                # Пропускаем если другой уровень власти
                if is_excluded_context(sentence, exclusion_phrases):
                    continue
                
                date_formatted = format_date(date_str)
                
                references.append(DocumentReference(
                    number=number,
                    date=date_formatted,
                    context=sentence[:200]
                ))
            except:
                continue
    
    return references