#!/usr/bin/env python3
"""
Анализ реальных документов из БД для поиска ВСЕХ паттернов упоминания старых версий
"""
import json
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from io import BytesIO
from collections import defaultdict

def download_file(url: str) -> bytes:
    """Скачивает файл по URL"""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

def extract_text_from_pdf(file_bytes: bytes, max_pages=3) -> str:
    """Извлекает текст из первых страниц PDF"""
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        text = ""
        for i in range(min(max_pages, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\n"
        return text
    except:
        return ""

def extract_text_from_docx(file_bytes: bytes, max_paragraphs=20) -> str:
    """Извлекает текст из первых абзацев DOCX"""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= max_paragraphs:
                break
            text += para.text + "\n"
        return text
    except:
        return ""

def analyze_documents():
    """Основная функция анализа"""
    
    # Подключение к БД
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        return {"error": "DATABASE_URL not set"}
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Получаем схему
    cursor.execute("SELECT current_schema()")
    schema = cursor.fetchone()['current_schema']
    print(f"Schema: {schema}")
    
    # Находим документы с related_count > 0
    cursor.execute("""
        SELECT DISTINCT d.id, d.file_cdn_url, d.related_count
        FROM documents d
        WHERE d.related_count > 0 AND d.file_cdn_url IS NOT NULL
        ORDER BY d.related_count DESC
        LIMIT 150
    """)
    
    documents = cursor.fetchall()
    print(f"Found {len(documents)} documents")
    
    # Результаты анализа
    all_context_phrases = set()
    all_patterns_found = set()
    examples = []
    analyzed_count = 0
    
    # Контекстные фразы для поиска
    context_keywords = [
        'утратившим силу', 'утрачивает силу', 'утрачивают силу',
        'считать утратившим', 'признать утратившим',
        'внести изменения', 'внесены изменения', 'вносятся изменения',
        'с изменениями, внесенными', 'дополнить', 'дополняется', 'дополнен',
        'изложить в новой редакции', 'в редакции постановлений',
        'в редакции постановления', 'действует в редакции',
        'отменить', 'отменяется', 'отменен', 'заменить', 'исключить'
    ]
    
    for doc in documents:
        if analyzed_count >= 150:
            break
            
        doc_id = doc['id']
        url = doc['file_cdn_url']
        
        print(f"Analyzing document {doc_id} ({analyzed_count + 1}/150)...")
        
        # Скачиваем файл
        file_bytes = download_file(url)
        if not file_bytes:
            continue
        
        # Извлекаем текст
        text = ""
        if url.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_bytes)
        elif url.lower().endswith('.docx'):
            text = extract_text_from_docx(file_bytes)
        
        if not text or len(text) < 100:
            continue
        
        analyzed_count += 1
        
        # Ищем все контекстные фразы
        for keyword in context_keywords:
            pattern = re.escape(keyword)
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Берем контекст вокруг фразы
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 400)
                context = text[start:end].strip()
                
                # Сохраняем контекстную фразу
                all_context_phrases.add(keyword)
                
                # Ищем все форматы дат и номеров в контексте
                # Паттерн 1: от DD.MM.YYYY года №NUM
                for m in re.finditer(r'от\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+года?\s+№\s*(\d+[\w\-]*)', context, re.IGNORECASE):
                    all_patterns_found.add('от DD.MM.YYYY года №NUM')
                    if len(examples) < 50:
                        examples.append({
                            "phrase": keyword,
                            "pattern": "от DD.MM.YYYY года №NUM",
                            "document_id": doc_id,
                            "full_text": context[:200]
                        })
                
                # Паттерн 2: №NUM от DD.MM.YYYY
                for m in re.finditer(r'№\s*(\d+[\w\-]*)\s+от\s+(\d{1,2}\.\d{1,2}\.\d{4})', context, re.IGNORECASE):
                    all_patterns_found.add('№NUM от DD.MM.YYYY')
                    if len(examples) < 50:
                        examples.append({
                            "phrase": keyword,
                            "pattern": "№NUM от DD.MM.YYYY",
                            "document_id": doc_id,
                            "full_text": context[:200]
                        })
                
                # Паттерн 3: постановление №NUM от DD.MM.YYYY
                for m in re.finditer(r'постановлени[ея]\s+№\s*(\d+[\w\-]*)\s+от\s+(\d{1,2}\.\d{1,2}\.\d{4})', context, re.IGNORECASE):
                    all_patterns_found.add('постановление №NUM от DD.MM.YYYY')
                    if len(examples) < 50:
                        examples.append({
                            "phrase": keyword,
                            "pattern": "постановление №NUM от DD.MM.YYYY",
                            "document_id": doc_id,
                            "full_text": context[:200]
                        })
                
                # Паттерн 4: от DD.MM.YYYY N NUM (с буквой N)
                for m in re.finditer(r'от\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+года?\s+N\s*(\d+[\w\-]*)', context, re.IGNORECASE):
                    all_patterns_found.add('от DD.MM.YYYY года N NUM')
                    if len(examples) < 50:
                        examples.append({
                            "phrase": keyword,
                            "pattern": "от DD.MM.YYYY года N NUM",
                            "document_id": doc_id,
                            "full_text": context[:200]
                        })
    
    cursor.close()
    conn.close()
    
    # Текущие паттерны в парсере
    current_patterns = [
        'от DD.MM.YYYY года №NUM',
        'от DD.MM.YYYY года N NUM',
        'от DD.MM.YYYY года #NUM',
        'постановление №NUM от DD.MM.YYYY',
        'постановление N NUM от DD.MM.YYYY',
        '№NUM от DD.MM.YYYY',
        'N NUM от DD.MM.YYYY'
    ]
    
    missing = [p for p in all_patterns_found if p not in current_patterns]
    
    return {
        "total_documents_analyzed": analyzed_count,
        "unique_context_phrases": sorted(list(all_context_phrases)),
        "unique_date_number_patterns": sorted(list(all_patterns_found)),
        "examples": examples[:30],
        "missing_in_current_parser": missing
    }

if __name__ == '__main__':
    result = analyze_documents()
    print("\n" + "="*80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
