#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для анализа DOCX файла и поиска упоминаний документов
"""

import re
import sys
import requests
from docx import Document
from io import BytesIO

def download_docx(url):
    """Скачивает DOCX файл по URL"""
    print(f"Скачиваю файл: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)

def extract_paragraphs(docx_file, limit=20):
    """Извлекает первые N параграфов из DOCX файла"""
    doc = Document(docx_file)
    paragraphs = []
    
    for i, para in enumerate(doc.paragraphs):
        if i >= limit:
            break
        # Пропускаем пустые параграфы
        if para.text.strip():
            paragraphs.append({
                'index': i,
                'text': para.text.strip()
            })
    
    return paragraphs

def find_document_mentions(text):
    """Ищет упоминания документов по трем паттернам"""
    mentions = []
    
    # Паттерн 1: обратный порядок (от даты № номер)
    pattern1 = r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+(?:№|N|#)\s*(\d+)'
    matches1 = re.finditer(pattern1, text, re.IGNORECASE | re.UNICODE)
    for match in matches1:
        mentions.append({
            'pattern': 'Паттерн 1 (обратный)',
            'date': match.group(1),
            'number': match.group(2),
            'full_match': match.group(0),
            'position': match.span()
        })
    
    # Паттерн 2: прямой порядок (постановление № номер от даты)
    pattern2 = r'постановлени[ея]\s+(?:№|N|#)?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})'
    matches2 = re.finditer(pattern2, text, re.IGNORECASE | re.UNICODE)
    for match in matches2:
        mentions.append({
            'pattern': 'Паттерн 2 (прямой)',
            'number': match.group(1),
            'date': match.group(2),
            'full_match': match.group(0),
            'position': match.span()
        })
    
    # Паттерн 3: упрощенный (№ номер от даты)
    pattern3 = r'(?:№|N|#)\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})'
    matches3 = re.finditer(pattern3, text, re.IGNORECASE | re.UNICODE)
    for match in matches3:
        mentions.append({
            'pattern': 'Паттерн 3 (упрощенный)',
            'number': match.group(1),
            'date': match.group(2),
            'full_match': match.group(0),
            'position': match.span()
        })
    
    return mentions

def analyze_text_format(paragraphs):
    """Анализирует формат текста для поиска альтернативных паттернов"""
    full_text = '\n'.join([p['text'] for p in paragraphs])
    
    analysis = {
        'has_numbers': bool(re.search(r'\d+', full_text)),
        'has_dates': bool(re.search(r'\d{2}\.\d{2}\.\d{4}', full_text)),
        'has_number_signs': bool(re.search(r'[№N#]', full_text)),
        'has_postanovlenie': bool(re.search(r'постановлени[ея]', full_text, re.IGNORECASE)),
        'has_ot': bool(re.search(r'\bот\b', full_text, re.IGNORECASE)),
        'date_formats': []
    }
    
    # Ищем различные форматы дат
    date_patterns = [
        (r'\d{2}\.\d{2}\.\d{4}', 'DD.MM.YYYY'),
        (r'\d{1,2}\s+[а-яА-Я]+\s+\d{4}', 'DD месяц YYYY'),
        (r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD'),
        (r'\d{2}/\d{2}/\d{4}', 'DD/MM/YYYY')
    ]
    
    for pattern, format_name in date_patterns:
        if re.search(pattern, full_text, re.UNICODE):
            analysis['date_formats'].append(format_name)
    
    return analysis

def main():
    url = "https://cdn.poehali.dev/projects/43869288-534e-4e87-af2a-4115997b9a30/bucket/docs/Постановления/926_main_4ae01c6e.docx"
    
    try:
        # Скачиваем файл
        docx_file = download_docx(url)
        
        # Извлекаем первые 20 параграфов
        paragraphs = extract_paragraphs(docx_file, limit=20)
        
        print("\n" + "="*80)
        print("ПЕРВЫЕ 20 ПАРАГРАФОВ ИЗ DOCX ФАЙЛА")
        print("="*80 + "\n")
        
        for para in paragraphs:
            print(f"[Параграф {para['index']}]")
            print(para['text'])
            print("-" * 80)
        
        # Объединяем весь текст для поиска
        full_text = '\n'.join([p['text'] for p in paragraphs])
        
        # Ищем упоминания документов
        mentions = find_document_mentions(full_text)
        
        print("\n" + "="*80)
        print("НАЙДЕННЫЕ УПОМИНАНИЯ ДОКУМЕНТОВ")
        print("="*80 + "\n")
        
        if mentions:
            for i, mention in enumerate(mentions, 1):
                print(f"Упоминание #{i}:")
                print(f"  Паттерн: {mention['pattern']}")
                print(f"  Номер: {mention['number']}")
                print(f"  Дата: {mention['date']}")
                print(f"  Полное совпадение: '{mention['full_match']}'")
                print(f"  Позиция в тексте: {mention['position']}")
                print("-" * 80)
        else:
            print("НЕТ УПОМИНАНИЙ, найденных по указанным паттернам!")
            print("\n" + "="*80)
            print("АНАЛИЗ ФОРМАТА ТЕКСТА")
            print("="*80 + "\n")
            
            analysis = analyze_text_format(paragraphs)
            
            print(f"Содержит числа: {'ДА' if analysis['has_numbers'] else 'НЕТ'}")
            print(f"Содержит даты (DD.MM.YYYY): {'ДА' if analysis['has_dates'] else 'НЕТ'}")
            print(f"Содержит знаки номера (№, N, #): {'ДА' if analysis['has_number_signs'] else 'НЕТ'}")
            print(f"Содержит слово 'постановление': {'ДА' if analysis['has_postanovlenie'] else 'НЕТ'}")
            print(f"Содержит предлог 'от': {'ДА' if analysis['has_ot'] else 'НЕТ'}")
            
            if analysis['date_formats']:
                print(f"\nОбнаруженные форматы дат: {', '.join(analysis['date_formats'])}")
            
            print("\n" + "="*80)
            print("ВОЗМОЖНЫЕ ПРИЧИНЫ")
            print("="*80 + "\n")
            
            reasons = []
            
            if not analysis['has_dates']:
                reasons.append("- В тексте нет дат в формате DD.MM.YYYY")
            
            if not analysis['has_number_signs']:
                reasons.append("- В тексте нет знаков номера (№, N, #)")
            
            if not analysis['has_postanovlenie']:
                reasons.append("- В тексте нет слова 'постановление'")
            
            if not analysis['has_ot']:
                reasons.append("- В тексте нет предлога 'от'")
            
            if not analysis['has_numbers']:
                reasons.append("- В тексте вообще нет чисел")
            
            if analysis['date_formats'] and 'DD.MM.YYYY' not in analysis['date_formats']:
                reasons.append(f"- Даты в другом формате: {', '.join(analysis['date_formats'])}")
            
            if not reasons:
                reasons.append("- Возможно, упоминания есть, но в другом формате")
                reasons.append("- Проверьте следующие варианты:")
                reasons.append("  * Разрывы строк между элементами (№ 123\\nот 01.01.2024)")
                reasons.append("  * Другие разделители (тире, слеш, пробелы)")
                reasons.append("  * Написание слов с ошибками или сокращениями")
                reasons.append("  * Использование других терминов (приказ, распоряжение и т.д.)")
            
            for reason in reasons:
                print(reason)
        
        print("\n" + "="*80)
        print("ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ")
        print("="*80 + "\n")
        print(f"Всего извлечено параграфов (непустых): {len(paragraphs)}")
        print(f"Общая длина текста: {len(full_text)} символов")
        
    except Exception as e:
        print(f"\nОШИБКА: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
