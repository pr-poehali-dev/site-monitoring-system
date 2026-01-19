#!/usr/bin/env python3
"""
Скрипт для анализа паттернов упоминания предыдущих версий документов в базе данных.
Цель: найти все возможные формулировки для улучшения логики парсинга связей между документами.
"""

import os
import re
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict, Counter
from datetime import datetime
import requests
from io import BytesIO

def get_db_connection():
    """Подключение к базе данных через DATABASE_URL"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise Exception('DATABASE_URL не настроен в переменных окружения')
    return psycopg2.connect(db_url)

def get_documents_with_references(cursor, schema='public', limit=30):
    """Получить документы, на которые есть ссылки от более новых версий (related_count > 0)"""
    query = f"""
        SELECT id, title, document_number, document_date, url, 
               related_count, file_cdn_url, section
        FROM {schema}.documents
        WHERE related_count > 0 
          AND (is_phantom IS NULL OR is_phantom = FALSE)
        ORDER BY related_count DESC, document_date DESC
        LIMIT %s
    """
    cursor.execute(query, (limit,))
    return cursor.fetchall()

def get_documents_referencing(cursor, schema, target_doc_id):
    """Получить документы, которые ссылаются на указанный документ"""
    query = f"""
        SELECT id, title, document_number, document_date, url, 
               related_to, file_cdn_url, section
        FROM {schema}.documents
        WHERE related_to = %s
        ORDER BY document_date DESC
    """
    cursor.execute(query, (target_doc_id,))
    return cursor.fetchall()

def download_file(url):
    """Скачать файл по URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Ошибка скачивания {url}: {e}")
        return None

def extract_text_from_docx(file_bytes, max_paragraphs=30):
    """Извлечь текст из DOCX файла"""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= max_paragraphs:
                break
            text += para.text + "\n"
        return text
    except Exception as e:
        print(f"Ошибка чтения DOCX: {e}")
        return ""

def extract_text_from_pdf(file_bytes, max_pages=3):
    """Извлечь текст из PDF файла"""
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        text = ""
        for i in range(min(max_pages, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Ошибка чтения PDF: {e}")
        return ""

def extract_text_from_file(file_url):
    """Извлечь текст из файла (DOCX или PDF)"""
    if not file_url:
        return ""
    
    file_bytes = download_file(file_url)
    if not file_bytes:
        return ""
    
    if file_url.lower().endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    elif file_url.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    else:
        return ""

def find_context_phrases(text, target_number, target_date):
    """
    Найти все фразы/контексты, в которых упоминается целевой документ.
    Возвращает список контекстов (по 200 символов до и после упоминания).
    """
    contexts = []
    
    # Форматируем дату в разных вариантах
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            date_formats = [
                date_obj.strftime('%d.%m.%Y'),  # 01.12.2023
                date_obj.strftime('%d.%m.%y'),  # 01.12.23
            ]
        except:
            date_formats = []
    else:
        date_formats = []
    
    # Паттерны для поиска упоминания документа
    patterns = []
    
    if target_number:
        # №NUM от DATE
        for date_fmt in date_formats:
            patterns.append(rf'(?:№|N|#)\s*{re.escape(target_number)}\s+от\s+{re.escape(date_fmt)}')
            patterns.append(rf'от\s+{re.escape(date_fmt)}\s+года?\s+(?:№|N|#)\s*{re.escape(target_number)}')
        
        # Постановление/распоряжение №NUM от DATE
        for date_fmt in date_formats:
            patterns.append(rf'(?:постановлени[еяй]|распоряжени[еяй])\s+(?:№|N|#)?\s*{re.escape(target_number)}\s+от\s+{re.escape(date_fmt)}')
    
    # Ищем все совпадения и берем контекст
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            
            # Очищаем от лишних переносов
            context = ' '.join(context.split())
            
            contexts.append({
                'matched_text': match.group(0),
                'context': context,
                'position': match.start()
            })
    
    return contexts

def extract_all_patterns(text):
    """
    Извлечь ВСЕ паттерны/фразы, которые могут указывать на связь с предыдущими версиями.
    Возвращает словарь: {фраза: [список контекстов]}
    """
    pattern_contexts = defaultdict(list)
    
    # Расширенный список ключевых фраз
    key_phrases = [
        # Утрата силы
        r'утратившим\s+силу',
        r'признать\s+утратившим\s+силу',
        r'признать\s+утратившими\s+силу',
        r'утрачива[ею]т\s+силу',
        r'утратил[ао]?\s+силу',
        r'признан[ыо]?\s+утратившим',
        
        # Изменения
        r'внести\s+изменени[яе]',
        r'внести\s+следующие\s+изменения',
        r'вносятся\s+изменения',
        r'внесены\s+изменения',
        r'внес[ёе]н\s+изменения',
        
        # Дополнения
        r'дополнить',
        r'дополняется',
        
        # Редакции
        r'изложить\s+в\s+(?:новой\s+)?редакции',
        r'в\s+редакции\s+(?:постановлени[йяе]|распоряжени[йяе])',
        r'(?:с\s+)?изменениями,?\s+внес[её]нными',
        r'с\s+учетом\s+изменений',
        
        # Отмена
        r'отменить',
        r'отменяется',
        r'признать\s+недействительн',
        
        # Замена
        r'заменить',
        r'исключить',
        r'считать',
        
        # Приостановление
        r'приостановить\s+действие',
        r'приостанавлива[её]тся',
        
        # Продление
        r'продлить\s+срок',
        r'продл[её]н',
        
        # Прочее
        r'на\s+основании',
        r'во\s+исполнение',
        r'в\s+соответствии\s+с',
        r'руководствуясь',
    ]
    
    for phrase_pattern in key_phrases:
        for match in re.finditer(phrase_pattern, text, re.IGNORECASE):
            # Берем расширенный контекст для анализа
            start = max(0, match.start() - 300)
            end = min(len(text), match.end() + 500)
            context = text[start:end]
            context = ' '.join(context.split())  # Нормализуем пробелы
            
            matched_phrase = match.group(0).lower()
            pattern_contexts[matched_phrase].append(context)
    
    return pattern_contexts

def analyze_document_number_patterns(text):
    """
    Анализировать различные паттерны упоминания номеров и дат документов.
    Возвращает словарь с примерами различных форматов.
    """
    patterns = {
        'standard': [],      # №NUM от DATE
        'reverse': [],       # от DATE №NUM
        'with_word': [],     # постановление №NUM от DATE
        'year_word': [],     # от DATE года №NUM
        'short_date': [],    # DD.MM.YY
        'full_date': [],     # DD.MM.YYYY
        'no_symbol': [],     # NUM от DATE (без №)
        'slash_n': [],       # N NUM вместо №NUM
    }
    
    # Стандартный: №NUM от DATE
    for match in re.finditer(r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2,4})', text, re.IGNORECASE):
        patterns['standard'].append(match.group(0))
    
    # Обратный порядок: от DATE №NUM
    for match in re.finditer(r'от\s+(\d{2}\.\d{2}\.\d{2,4})\s+(?:года?)?\s*№\s*(\d+)', text, re.IGNORECASE):
        patterns['reverse'].append(match.group(0))
    
    # С указанием типа: постановление/распоряжение
    for match in re.finditer(r'(?:постановлени[еяй]|распоряжени[еяй])\s+№?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2,4})', text, re.IGNORECASE):
        patterns['with_word'].append(match.group(0))
    
    # Со словом "года"
    for match in re.finditer(r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года\s+№\s*(\d+)', text, re.IGNORECASE):
        patterns['year_word'].append(match.group(0))
    
    # Короткая дата (YY)
    for match in re.finditer(r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2})\b', text, re.IGNORECASE):
        patterns['short_date'].append(match.group(0))
    
    # Полная дата (YYYY)
    for match in re.finditer(r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', text, re.IGNORECASE):
        patterns['full_date'].append(match.group(0))
    
    # N вместо №
    for match in re.finditer(r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2,4})', text, re.IGNORECASE):
        patterns['slash_n'].append(match.group(0))
    
    return patterns

def main():
    print("=" * 80)
    print("АНАЛИЗ ПАТТЕРНОВ УПОМИНАНИЯ ПРЕДЫДУЩИХ ВЕРСИЙ ДОКУМЕНТОВ")
    print("=" * 80)
    print()
    
    # Подключение к БД
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Получаем схему
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()['current_schema']
        print(f"✓ Подключено к базе данных (схема: {schema})")
        print()
        
    except Exception as e:
        print(f"✗ Ошибка подключения к базе данных: {e}")
        return
    
    # Получаем статистику
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE related_count > 0) as with_references,
            COUNT(*) FILTER (WHERE related_to IS NOT NULL) as referencing_others
        FROM {schema}.documents
        WHERE (is_phantom IS NULL OR is_phantom = FALSE)
    """)
    stats = cursor.fetchone()
    print(f"Статистика документов:")
    print(f"  - Всего документов: {stats['total']}")
    print(f"  - Документов с входящими ссылками (related_count > 0): {stats['with_references']}")
    print(f"  - Документов, ссылающихся на другие: {stats['referencing_others']}")
    print()
    
    # Получаем документы с наибольшим количеством ссылок
    print("Получение документов для анализа (топ-30 по количеству ссылок)...")
    target_docs = get_documents_with_references(cursor, schema, limit=30)
    print(f"✓ Найдено {len(target_docs)} документов для анализа")
    print()
    
    # Хранилища для анализа
    all_patterns = defaultdict(list)
    all_contexts = []
    number_format_examples = defaultdict(list)
    
    analyzed_count = 0
    
    for i, target_doc in enumerate(target_docs, 1):
        print(f"\n[{i}/{len(target_docs)}] Анализ документа ID={target_doc['id']}")
        print(f"  Заголовок: {target_doc['title'][:80]}...")
        print(f"  Номер: {target_doc['document_number']}, Дата: {target_doc['document_date']}")
        print(f"  Количество ссылающихся документов: {target_doc['related_count']}")
        
        # Получаем документы, которые ссылаются на этот
        referencing_docs = get_documents_referencing(cursor, schema, target_doc['id'])
        print(f"  Найдено ссылающихся документов: {len(referencing_docs)}")
        
        for j, ref_doc in enumerate(referencing_docs, 1):
            if not ref_doc['file_cdn_url']:
                continue
            
            print(f"    [{j}/{len(referencing_docs)}] Анализ ссылающегося документа ID={ref_doc['id']}")
            
            # Скачиваем и анализируем файл
            text = extract_text_from_file(ref_doc['file_cdn_url'])
            
            if not text:
                print(f"      ⚠ Не удалось извлечь текст")
                continue
            
            print(f"      ✓ Извлечено {len(text)} символов текста")
            
            # Ищем контексты упоминания целевого документа
            contexts = find_context_phrases(
                text, 
                target_doc['document_number'], 
                target_doc['document_date']
            )
            
            if contexts:
                print(f"      ✓ Найдено {len(contexts)} упоминаний целевого документа")
                for ctx in contexts:
                    all_contexts.append({
                        'target_doc_id': target_doc['id'],
                        'target_title': target_doc['title'],
                        'ref_doc_id': ref_doc['id'],
                        'ref_title': ref_doc['title'],
                        'matched_text': ctx['matched_text'],
                        'context': ctx['context']
                    })
            
            # Извлекаем все паттерны ключевых фраз
            patterns = extract_all_patterns(text)
            for phrase, phrase_contexts in patterns.items():
                all_patterns[phrase].extend(phrase_contexts[:3])  # Берем до 3 примеров
            
            # Анализируем форматы номеров документов
            number_formats = analyze_document_number_patterns(text)
            for format_type, examples in number_formats.items():
                number_format_examples[format_type].extend(examples[:5])
            
            analyzed_count += 1
    
    print("\n" + "=" * 80)
    print(f"✓ АНАЛИЗ ЗАВЕРШЕН. Проанализировано {analyzed_count} документов")
    print("=" * 80)
    print()
    
    # Выводим результаты
    print("\n" + "=" * 80)
    print("1. НАЙДЕННЫЕ КЛЮЧЕВЫЕ ФРАЗЫ И ПАТТЕРНЫ")
    print("=" * 80)
    
    # Сортируем по частоте встречаемости
    sorted_patterns = sorted(all_patterns.items(), key=lambda x: len(x[1]), reverse=True)
    
    for phrase, contexts in sorted_patterns:
        print(f"\nФраза: '{phrase}'")
        print(f"Встречаемость: {len(contexts)} раз(а)")
        print("Примеры контекстов:")
        for ctx in contexts[:3]:  # Показываем до 3 примеров
            print(f"  - ...{ctx[:150]}...")
    
    print("\n" + "=" * 80)
    print("2. ФОРМАТЫ УПОМИНАНИЯ НОМЕРОВ И ДАТ ДОКУМЕНТОВ")
    print("=" * 80)
    
    for format_type, examples in number_format_examples.items():
        if examples:
            unique_examples = list(set(examples))[:5]
            print(f"\n{format_type.upper()}:")
            for ex in unique_examples:
                print(f"  - {ex}")
    
    print("\n" + "=" * 80)
    print("3. ПРИМЕРЫ КОНТЕКСТОВ УПОМИНАНИЯ ДОКУМЕНТОВ")
    print("=" * 80)
    
    for i, ctx in enumerate(all_contexts[:15], 1):  # Показываем первые 15
        print(f"\n[{i}] Целевой документ: {ctx['target_title'][:60]}...")
        print(f"    Ссылается из: {ctx['ref_title'][:60]}...")
        print(f"    Найдено: '{ctx['matched_text']}'")
        print(f"    Контекст: ...{ctx['context'][:200]}...")
    
    # Статистика
    print("\n" + "=" * 80)
    print("4. СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего найдено уникальных ключевых фраз: {len(all_patterns)}")
    print(f"Всего найдено контекстов упоминаний: {len(all_contexts)}")
    print()
    
    # Рекомендации
    print("\n" + "=" * 80)
    print("5. РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ REGEX-ПАТТЕРНОВ")
    print("=" * 80)
    print()
    
    print("На основе анализа рекомендуется добавить/улучшить следующие паттерны:")
    print()
    
    print("А) Ключевые фразы для контекстного поиска:")
    print("   Текущие паттерны в link-finder/index.py охватывают основные случаи,")
    print("   но стоит добавить:")
    recommended_phrases = [
        'утрачивает силу',
        'признан утратившим',
        'внесены изменения',
        'с изменениями, внесенными',
        'считать утратившим силу',
        'приостановить действие',
        'продлить срок',
        'отменить',
        'признать недействительным',
    ]
    for phrase in recommended_phrases:
        if phrase not in [p.replace(r'\s+', ' ') for p in all_patterns.keys()]:
            print(f"   - r'{phrase.replace(' ', r'\s+')}'")
    
    print()
    print("Б) Форматы упоминания номеров и дат:")
    print("   Рекомендуется поддержать все найденные форматы:")
    print("   1. Стандартный: №NUM от DD.MM.YYYY")
    print("   2. Обратный: от DD.MM.YYYY (года) №NUM")
    print("   3. С типом документа: постановление/распоряжение №NUM от DATE")
    print("   4. С 'N' вместо '№': N NUM от DATE")
    print("   5. Короткая дата: №NUM от DD.MM.YY")
    print()
    
    print("В) Особые случаи:")
    print("   - Множественные ссылки в одном предложении")
    print("   - Списки документов через запятую: '№1 от 01.01.2023, №2 от 02.02.2023'")
    print("   - Ссылки в скобках: '(в редакции постановлений от ... №...)'")
    print("   - Диапазоны дат и номеров")
    print()
    
    # Сохраняем подробный отчет в JSON
    report = {
        'analyzed_at': datetime.now().isoformat(),
        'stats': {
            'total_documents': stats['total'],
            'with_references': stats['with_references'],
            'analyzed_count': analyzed_count,
            'unique_phrases': len(all_patterns),
            'total_contexts': len(all_contexts)
        },
        'patterns': {phrase: len(contexts) for phrase, contexts in all_patterns.items()},
        'number_formats': {k: list(set(v))[:10] for k, v in number_format_examples.items()},
        'sample_contexts': all_contexts[:30]
    }
    
    with open('document_patterns_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Подробный отчет сохранен в: document_patterns_report.json")
    print()
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
