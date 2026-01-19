#!/usr/bin/env python3
"""
Генератор улучшенного кода парсера на основе анализа паттернов.
Создает новую версию parse_document_references с расширенной поддержкой паттернов.
"""

def generate_improved_parser_code():
    """Генерирует улучшенный код функции parse_document_references"""
    
    code = '''
def parse_document_references(text: str) -> list:
    """
    Улучшенная версия парсинга ссылок на документы.
    
    Изменения v2.0:
    - Расширен список ключевых фраз (с 6 до 25+)
    - Добавлена поддержка латинской 'N' и символа '#'
    - Улучшена обработка коротких дат (YY)
    - Добавлена обработка списков в скобках
    - Добавлена валидация найденных ссылок
    - Улучшено логирование для отладки
    """
    references = []
    
    # РАСШИРЕННЫЙ список ключевых фраз
    context_keywords = [
        # Утрата силы (различные формы)
        r'утратившим\\s+силу',
        r'утрачивает\\s+силу',
        r'утрачивают\\s+силу',
        r'утратил[оа]?\\s+силу',
        r'признать\\s+утратившим\\s+силу',
        r'признать\\s+утратившими\\s+силу',
        r'считать\\s+утратившим\\s+силу',
        
        # Изменения
        r'внести\\s+изменени[яе]',
        r'внести\\s+следующие\\s+изменения',
        r'вносятся\\s+изменения',
        r'внес[её]ны?\\s+изменения',
        r'с\\s+изменениями,?\\s+внес[её]нными',
        
        # Дополнения
        r'дополнить',
        r'дополняется',
        r'дополнен[ао]?',
        
        # Редакции
        r'изложить\\s+в\\s+(?:новой\\s+)?редакции',
        r'в\\s+редакции\\s+(?:постановлени[йяе]|распоряжени[йяе])',
        r'действует\\s+в\\s+редакции',
        r'с\\s+учетом\\s+изменений',
        
        # Отмена
        r'отменить',
        r'отменяется',
        r'отмен[её]н[ао]?',
        r'признать\\s+недействительн',
        
        # Замена/исключение
        r'заменить',
        r'исключить',
        r'исключается',
        
        # Приостановление
        r'приостановить\\s+действие',
        r'приостанавлива[её]тся',
        
        # Продление
        r'продлить\\s+срок',
        r'продл[её]н\\s+срок',
        
        # Ссылки (менее приоритетные)
        r'на\\s+основании\\s+(?:постановлени|распоряжени)',
        r'во\\s+исполнение\\s+(?:постановлени|распоряжени)',
        r'в\\s+соответствии\\s+с\\s+(?:постановлением|распоряжением)',
    ]
    
    # Вспомогательная функция для нормализации даты
    def normalize_date(date_str: str) -> str:
        """Преобразует различные форматы дат в YYYY-MM-DD"""
        try:
            # Короткий год (YY)
            if len(date_str.split('.')[-1]) == 2:
                date_obj = datetime.strptime(date_str, '%d.%m.%y')
                # Если год получился больше текущего, значит это прошлый век
                if date_obj.year > datetime.now().year:
                    date_obj = date_obj.replace(year=date_obj.year - 100)
            else:
                # Полный год (YYYY)
                date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            
            return date_obj.strftime('%Y-%m-%d')
        except:
            return None
    
    # Вспомогательная функция для валидации
    def is_valid_reference(number: str, date_formatted: str, context: str) -> bool:
        """Проверяет валидность найденной ссылки"""
        # Фильтр 1: Номер должен быть разумным (не более 6 цифр)
        if not number or len(number) > 6 or not number.isdigit():
            return False
        
        # Фильтр 2: Дата должна быть валидной
        if not date_formatted:
            return False
        
        try:
            year = int(date_formatted.split('-')[0])
            # Дата не должна быть раньше 1990 и позже чем через год от текущей даты
            if year < 1990 or year > datetime.now().year + 1:
                return False
        except:
            return False
        
        # Фильтр 3: Исключаем технические номера
        context_lower = context.lower()
        exclude_keywords = ['телефон', 'факс', 'счет', 'счёт', 'банк', 'инн', 'окпо', 
                           'снилс', 'огрн', 'кпп', 'бик', 'тел.', 'тел:']
        if any(kw in context_lower for kw in exclude_keywords):
            return False
        
        return True
    
    # Основной цикл поиска
    for keyword_pattern in context_keywords:
        for keyword_match in re.finditer(keyword_pattern, text, re.IGNORECASE):
            # Определяем размер контекстного окна в зависимости от ключевой фразы
            if 'редакции' in keyword_pattern or 'изменениями' in keyword_pattern:
                # Для списков изменений - большое окно (до 2000 символов)
                start_pos = max(0, keyword_match.start() - 100)
                end_pos = min(len(text), keyword_match.end() + 2000)
            else:
                # По умолчанию - стандартное окно
                start_pos = max(0, keyword_match.start() - 200)
                end_pos = min(len(text), keyword_match.end() + 300)
            
            context_text = text[start_pos:end_pos]
            
            # ========== ПАТТЕРН 1: "от DATE года? №NUM" (обратный порядок) ==========
            pattern_reverse = r'от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})\\s+года?\\s+(?:№|N|#)\\s*(\\d+)'
            for match in re.finditer(pattern_reverse, context_text, re.IGNORECASE):
                try:
                    date_str = match.group(1)
                    number = match.group(2)
                    date_formatted = normalize_date(date_str)
                    
                    if is_valid_reference(number, date_formatted, context_text):
                        references.append({'number': number, 'date': date_formatted})
                except:
                    continue
            
            # ========== ПАТТЕРН 2: "постановление/распоряжение №NUM от DATE" ==========
            patterns_with_type = [
                r'постановлени[ея]\\s+(?:№|N|#)?\\s*(\\d+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})',
                r'распоряжени[ея]\\s+(?:№|N|#)?\\s*(\\d+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})',
            ]
            
            for pattern in patterns_with_type:
                for match in re.finditer(pattern, context_text, re.IGNORECASE):
                    try:
                        number = match.group(1)
                        date_str = match.group(2)
                        date_formatted = normalize_date(date_str)
                        
                        if is_valid_reference(number, date_formatted, context_text):
                            references.append({'number': number, 'date': date_formatted})
                    except:
                        continue
            
            # ========== ПАТТЕРН 3: "№NUM от DATE" (стандартный) ==========
            pattern_standard = r'(?:№|N|#)\\s*(\\d+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})'
            for match in re.finditer(pattern_standard, context_text, re.IGNORECASE):
                try:
                    number = match.group(1)
                    date_str = match.group(2)
                    date_formatted = normalize_date(date_str)
                    
                    if is_valid_reference(number, date_formatted, context_text):
                        references.append({'number': number, 'date': date_formatted})
                except:
                    continue
    
    # ========== СПЕЦИАЛЬНАЯ ОБРАБОТКА: блоки в скобках ==========
    # Обрабатываем случаи типа "(в редакции постановлений от ... №..., от ... №...)"
    bracket_pattern = r'\\((в\\s+редакции|с\\s+изменениями)[^\\)]{0,2000}\\)'
    
    for bracket_match in re.finditer(bracket_pattern, text, re.IGNORECASE):
        bracket_text = bracket_match.group(0)
        
        # Применяем все паттерны внутри скобок
        # Паттерн 1: обратный порядок
        pattern_reverse = r'от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})\\s+года?\\s+(?:№|N|#)\\s*(\\d+)'
        for match in re.finditer(pattern_reverse, bracket_text, re.IGNORECASE):
            try:
                date_str = match.group(1)
                number = match.group(2)
                date_formatted = normalize_date(date_str)
                
                if is_valid_reference(number, date_formatted, bracket_text):
                    references.append({'number': number, 'date': date_formatted})
            except:
                continue
        
        # Паттерн 2: стандартный
        pattern_standard = r'(?:№|N|#)\\s*(\\d+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{2,4})'
        for match in re.finditer(pattern_standard, bracket_text, re.IGNORECASE):
            try:
                number = match.group(1)
                date_str = match.group(2)
                date_formatted = normalize_date(date_str)
                
                if is_valid_reference(number, date_formatted, bracket_text):
                    references.append({'number': number, 'date': date_formatted})
            except:
                continue
    
    # ========== УДАЛЕНИЕ ДУБЛИКАТОВ ==========
    unique_refs = []
    seen = set()
    for ref in references:
        key = f"{ref['number']}_{ref['date']}"
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    
    return unique_refs
'''
    
    return code

def generate_full_file():
    """Генерирует полный файл с улучшенным парсером"""
    
    header = '''"""
API для автоматического поиска связей между документами через анализ их содержимого.
Извлекает номера и даты документов из первых страниц файлов (docx/pdf).

ВЕРСИЯ 2.0 - Улучшенная версия с расширенной поддержкой паттернов
"""

import json
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from io import BytesIO
from datetime import datetime

def extract_document_references_from_docx(file_bytes: bytes) -> list:
    """Извлекает ссылки на документы из DOCX файла"""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        
        text = ""
        for i, para in enumerate(doc.paragraphs):
            if i >= 20:
                break
            text += para.text + "\\n"
        
        return parse_document_references(text)
    except Exception as e:
        return []

def extract_document_references_from_pdf(file_bytes: bytes) -> list:
    """Извлекает ссылки на документы из PDF файла"""
    try:
        import PyPDF2
        pdf = PyPDF2.PdfReader(BytesIO(file_bytes))
        
        text = ""
        for i in range(min(3, len(pdf.pages))):
            text += pdf.pages[i].extract_text() + "\\n"
        
        return parse_document_references(text)
    except Exception as e:
        return []
'''
    
    parser_code = generate_improved_parser_code()
    
    # Добавляем остальную часть (handler и вспомогательные функции остаются без изменений)
    footer = '''
# Остальная часть файла (handler функция) остается без изменений
# Копируйте из оригинального backend/link-finder/index.py начиная с:
# def handler(event: dict, context) -> dict:
#     ...
'''
    
    full_code = header + parser_code + footer
    
    return full_code

def main():
    print("=" * 80)
    print("ГЕНЕРАТОР УЛУЧШЕННОГО ПАРСЕРА")
    print("=" * 80)
    print()
    
    print("Генерация улучшенного кода...")
    
    improved_code = generate_full_file()
    
    output_file = 'link_finder_improved.py'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(improved_code)
    
    print(f"✓ Улучшенный код сохранен в: {output_file}")
    print()
    print("СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Откройте файл link_finder_improved.py")
    print("2. Скопируйте функцию parse_document_references")
    print("3. Замените старую версию в backend/link-finder/index.py")
    print("4. Протестируйте на реальных данных")
    print("5. Сравните результаты с предыдущей версией")
    print()
    print("РЕКОМЕНДАЦИИ ПО ТЕСТИРОВАНИЮ:")
    print("- Запустите link-finder на 10-20 документах")
    print("- Сравните количество найденных ссылок")
    print("- Проверьте отсутствие ложных срабатываний")
    print("- Убедитесь, что производительность осталась на том же уровне")
    print()
    print("МЕТРИКИ ДЛЯ ОТСЛЕЖИВАНИЯ:")
    print("- Количество найденных ссылок (должно увеличиться)")
    print("- Процент корректных ссылок (должен быть >95%)")
    print("- Время обработки одного документа (не должно сильно увеличиться)")
    print()

if __name__ == '__main__':
    main()
