#!/usr/bin/env python3
"""
Интерактивный тестировщик паттернов для проверки regex на примерах текста.
Позволяет быстро проверить, как работают различные паттерны без запуска полного анализа.
"""

import re
from datetime import datetime
from typing import List, Dict, Tuple

# Цветной вывод в консоли
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Тестовые примеры текстов из реальных документов
TEST_TEXTS = [
    # Пример 1: Простая отмена
    """
    1. Признать утратившим силу постановление Правительства №123 от 01.12.2023.
    """,
    
    # Пример 2: Обратный порядок
    """
    Постановлением от 15.05.2024 года №456 внесены изменения в постановление 
    от 01.01.2020 года №100.
    """,
    
    # Пример 3: Множественные ссылки
    """
    Настоящее постановление действует в редакции постановлений от 10.01.2020 №5,
    от 15.03.2021 №12, от 20.06.2022 №25 и от 01.12.2023 №40.
    """,
    
    # Пример 4: В скобках
    """
    О внесении изменений в постановление №100 от 01.01.2020 (в редакции 
    постановлений от 05.05.2021 №15, от 10.10.2022 №30).
    """,
    
    # Пример 5: Со словом "года"
    """
    Признать утратившими силу от 25.12.2019 года №999 и от 30.06.2020 года №888.
    """,
    
    # Пример 6: С типом документа
    """
    Внести следующие изменения в распоряжение Правительства №777 от 01.01.2019
    и постановление №666 от 15.02.2020.
    """,
    
    # Пример 7: Диапазон (сложный случай)
    """
    Признать утратившими силу постановления №10, №11, №12, №13, №14, №15 
    от 01.01.2018.
    """,
    
    # Пример 8: N вместо №
    """
    Во исполнение постановления N 555 от 20.08.2023 и распоряжения N 444 
    от 10.07.2023.
    """,
    
    # Пример 9: Частичная отмена
    """
    Признать утратившим силу пункт 2.1 постановления №200 от 01.03.2022.
    """,
    
    # Пример 10: Короткий год
    """
    Изменения в постановление №300 от 15.05.23 и №301 от 20.05.23.
    """,
]

# Ключевые фразы (расширенный список)
CONTEXT_KEYWORDS = [
    r'утратившим\s+силу',
    r'утрачивает\s+силу',
    r'утрачивают\s+силу',
    r'признать\s+утратившим',
    r'признать\s+утратившими',
    r'внести\s+изменени[яе]',
    r'внести\s+следующие\s+изменения',
    r'вносятся\s+изменения',
    r'дополнить',
    r'изложить\s+в\s+(?:новой\s+)?редакции',
    r'в\s+редакции\s+(?:постановлени[йяе]|распоряжени[йяе])',
    r'отменить',
    r'признать\s+недействительн',
    r'во\s+исполнение',
]

def test_pattern(pattern: str, text: str, description: str = "") -> List[Dict]:
    """Протестировать один паттерн на тексте"""
    matches = []
    
    for match in re.finditer(pattern, text, re.IGNORECASE):
        matches.append({
            'match': match.group(0),
            'groups': match.groups(),
            'start': match.start(),
            'end': match.end(),
        })
    
    return matches

def extract_number_date_pairs(text: str) -> List[Tuple[str, str]]:
    """Извлечь все пары (номер, дата) используя различные паттерны"""
    pairs = []
    
    patterns = [
        # Паттерн 1: от DATE года? №NUM
        (r'от\s+(\d{2}\.\d{2}\.\d{4})\s+года?\s+(?:№|N|#)\s*(\d+)', 
         lambda m: (m.group(2), m.group(1))),
        
        # Паттерн 2: №NUM от DATE
        (r'(?:№|N|#)\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 
         lambda m: (m.group(1), m.group(2))),
        
        # Паттерн 3: постановление/распоряжение №NUM от DATE
        (r'(?:постановлени[ея]|распоряжени[ея])\s+(?:№|N|#)?\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 
         lambda m: (m.group(1), m.group(2))),
        
        # Паттерн 4: короткий год (YY)
        (r'(?:№|N|#)\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{2})\b', 
         lambda m: (m.group(1), m.group(2))),
    ]
    
    for pattern, extractor in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                number, date_str = extractor(match)
                
                # Нормализуем дату
                if len(date_str.split('.')[-1]) == 2:
                    date_obj = datetime.strptime(date_str, '%d.%m.%y')
                    if date_obj.year > datetime.now().year:
                        date_obj = date_obj.replace(year=date_obj.year - 100)
                    date_formatted = date_obj.strftime('%Y-%m-%d')
                else:
                    date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                    date_formatted = date_obj.strftime('%Y-%m-%d')
                
                pairs.append({
                    'number': number,
                    'date': date_formatted,
                    'original_date': date_str,
                    'matched_text': match.group(0),
                    'pattern': pattern,
                })
            except Exception as e:
                continue
    
    # Удаляем дубликаты
    seen = set()
    unique_pairs = []
    for pair in pairs:
        key = f"{pair['number']}_{pair['date']}"
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)
    
    return unique_pairs

def find_context_phrases(text: str) -> List[Dict]:
    """Найти все ключевые фразы в тексте"""
    contexts = []
    
    for pattern in CONTEXT_KEYWORDS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            
            contexts.append({
                'phrase': match.group(0),
                'pattern': pattern,
                'context': context,
                'position': match.start(),
            })
    
    return contexts

def test_all_examples():
    """Протестировать все примеры"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}ТЕСТИРОВАНИЕ ПАТТЕРНОВ НА ПРИМЕРАХ{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
    
    for i, text in enumerate(TEST_TEXTS, 1):
        print(f"\n{Colors.OKBLUE}{Colors.BOLD}[ПРИМЕР {i}]{Colors.ENDC}")
        print(f"{Colors.OKCYAN}Текст:{Colors.ENDC}")
        print(text.strip())
        print()
        
        # Найти ключевые фразы
        phrases = find_context_phrases(text)
        if phrases:
            print(f"{Colors.OKGREEN}✓ Найдены ключевые фразы:{Colors.ENDC}")
            for phrase in phrases:
                print(f"  • '{phrase['phrase']}' в контексте: ...{phrase['context']}...")
        else:
            print(f"{Colors.WARNING}⚠ Ключевые фразы не найдены{Colors.ENDC}")
        print()
        
        # Извлечь номера и даты
        pairs = extract_number_date_pairs(text)
        if pairs:
            print(f"{Colors.OKGREEN}✓ Извлечены документы:{Colors.ENDC}")
            for pair in pairs:
                print(f"  • №{pair['number']} от {pair['date']} (оригинал: {pair['original_date']})")
                print(f"    Найдено: '{pair['matched_text']}'")
                print(f"    Паттерн: {pair['pattern'][:60]}...")
        else:
            print(f"{Colors.WARNING}⚠ Документы не извлечены{Colors.ENDC}")
        
        print(f"\n{Colors.HEADER}{'-'*80}{Colors.ENDC}")

def test_custom_text():
    """Интерактивный режим для тестирования своего текста"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}ИНТЕРАКТИВНЫЙ РЕЖИМ ТЕСТИРОВАНИЯ{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
    
    print("Введите текст для анализа (для завершения введите пустую строку):")
    print()
    
    lines = []
    while True:
        try:
            line = input()
            if not line:
                break
            lines.append(line)
        except EOFError:
            break
    
    if not lines:
        print(f"{Colors.WARNING}Текст не введен{Colors.ENDC}")
        return
    
    text = '\n'.join(lines)
    
    print(f"\n{Colors.OKCYAN}Анализируемый текст:{Colors.ENDC}")
    print(text)
    print()
    
    # Анализ
    phrases = find_context_phrases(text)
    pairs = extract_number_date_pairs(text)
    
    if phrases:
        print(f"{Colors.OKGREEN}✓ Найдены ключевые фразы: {len(phrases)}{Colors.ENDC}")
        for phrase in phrases:
            print(f"  • '{phrase['phrase']}'")
    else:
        print(f"{Colors.WARNING}⚠ Ключевые фразы не найдены{Colors.ENDC}")
    print()
    
    if pairs:
        print(f"{Colors.OKGREEN}✓ Извлечены документы: {len(pairs)}{Colors.ENDC}")
        for pair in pairs:
            print(f"  • №{pair['number']} от {pair['date']}")
            print(f"    Найдено: '{pair['matched_text']}'")
    else:
        print(f"{Colors.WARNING}⚠ Документы не извлечены{Colors.ENDC}")

def show_patterns():
    """Показать все поддерживаемые паттерны"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}ПОДДЕРЖИВАЕМЫЕ ПАТТЕРНЫ{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
    
    print(f"{Colors.OKBLUE}1. КЛЮЧЕВЫЕ ФРАЗЫ (контекстные маркеры):{Colors.ENDC}")
    for i, pattern in enumerate(CONTEXT_KEYWORDS, 1):
        # Преобразуем regex в читаемый вид
        readable = pattern.replace(r'\s+', ' ').replace('[', '(').replace(']', ')')
        print(f"   {i:2}. {readable}")
    
    print(f"\n{Colors.OKBLUE}2. ФОРМАТЫ НОМЕРОВ И ДАТ:{Colors.ENDC}")
    formats = [
        "от DD.MM.YYYY года? №NUM",
        "№NUM от DD.MM.YYYY",
        "постановление/распоряжение №NUM от DD.MM.YYYY",
        "№NUM от DD.MM.YY (короткий год)",
        "N NUM от DATE (латинская N)",
        "# NUM от DATE (решетка)",
    ]
    for i, fmt in enumerate(formats, 1):
        print(f"   {i}. {fmt}")
    
    print(f"\n{Colors.OKBLUE}3. СПЕЦИАЛЬНЫЕ СЛУЧАИ:{Colors.ENDC}")
    special = [
        "Списки через запятую: 'от DATE1 №NUM1, от DATE2 №NUM2, ...'",
        "В скобках: '(в редакции постановлений от DATE №NUM, ...)'",
        "Частичная отмена: 'пункт X.Y постановления №NUM от DATE'",
        "Множественные номера: '№1, №2, №3 от DATE'",
    ]
    for i, case in enumerate(special, 1):
        print(f"   {i}. {case}")

def main():
    """Главное меню"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}ТЕСТИРОВЩИК ПАТТЕРНОВ ПАРСИНГА ДОКУМЕНТОВ{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
    
    print("Выберите режим:")
    print(f"  {Colors.OKGREEN}1{Colors.ENDC}. Протестировать на готовых примерах")
    print(f"  {Colors.OKGREEN}2{Colors.ENDC}. Интерактивный ввод текста")
    print(f"  {Colors.OKGREEN}3{Colors.ENDC}. Показать все паттерны")
    print(f"  {Colors.OKGREEN}0{Colors.ENDC}. Выход")
    print()
    
    try:
        choice = input("Ваш выбор: ").strip()
        
        if choice == '1':
            test_all_examples()
        elif choice == '2':
            test_custom_text()
        elif choice == '3':
            show_patterns()
        elif choice == '0':
            print("Выход.")
            return
        else:
            print(f"{Colors.FAIL}Неверный выбор{Colors.ENDC}")
    
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Прервано пользователем{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Ошибка: {e}{Colors.ENDC}")

if __name__ == '__main__':
    main()
