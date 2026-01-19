#!/usr/bin/env python3
"""Тест логики классификации упоминаний"""
import sys
import re

# КОПИЯ КОДА ИЗ backend/parser/link_patterns.py

VERSION_KEYWORDS = [
    r'утратившим\s+силу', r'утрачива[ею]т\s+силу', r'считать\s+утратившим',
    r'признать\s+утратившим', r'внести\s+изменени[яе]', r'внесены\s+изменения',
    r'вносятся\s+изменения', r'с\s+изменениями,\s+внесенными',
    r'дополнить', r'дополняется', r'дополнен',
    r'изложить\s+в\s+новой\s+редакции', r'в\s+редакции\s+постановлени',
    r'действует\s+в\s+редакции', r'отменить', r'отменяется', r'отменен',
    r'заменить', r'исключить'
]

RELATED_KEYWORDS = [
    r'в\s+соответствии\s+с', r'на\s+основании', r'руководствуясь',
    r'в\s+целях', r'согласно', r'во\s+исполнение'
]

EXCLUSION_PHRASES = [
    'правительства смоленской области',
    'администрации смоленской области',
    'правительства российской федерации',
    'правительства рф'
]

def classify_mention(context: str):
    """Классифицировать упоминание: EXTERNAL, VERSION или RELATED"""
    context_lower = context.lower()
    
    # 1. Проверяем на внешний документ (высший приоритет)
    for phrase in EXCLUSION_PHRASES:
        if phrase in context_lower:
            return 'EXTERNAL', [phrase]
    
    # 2. Ищем VERSION ключевые слова
    found_version = []
    for keyword in VERSION_KEYWORDS:
        if re.search(keyword, context_lower):
            found_version.append(keyword)
    
    if found_version:
        return 'VERSION', found_version
    
    # 3. Ищем RELATED ключевые слова
    found_related = []
    for keyword in RELATED_KEYWORDS:
        if re.search(keyword, context_lower):
            found_related.append(keyword)
    
    if found_related:
        return 'RELATED', found_related
    
    # 4. Если ничего не нашли → считаем RELATED по умолчанию
    return 'RELATED', []


# ТЕСТЫ
test_cases = [
    ("приложение к постановлению №687 от 10.10.2025", "Обычное упоминание БЕЗ ключевых слов"),
    ("согласно постановлению №687 от 10.10.2025", "Есть RELATED ключевое слово 'согласно'"),
    ("внести изменения в постановление №687 от 10.10.2025", "Есть VERSION ключевое слово"),
    ("постановление правительства рф №687 от 10.10.2025", "Внешний документ (Правительство РФ)"),
    ("на основании постановления №123 от 01.01.2024 утверждаю", "Есть и RELATED, и VERSION → приоритет VERSION"),
]

print("=" * 80)
print("ТЕСТ НОВОЙ ЛОГИКИ КЛАССИФИКАЦИИ")
print("=" * 80)

for context, description in test_cases:
    mention_type, keywords = classify_mention(context)
    print(f"\n📝 Контекст: {context}")
    print(f"💡 Ожидание: {description}")
    print(f"✅ Результат: {mention_type}")
    if keywords:
        print(f"🔑 Ключевые слова: {keywords}")
    else:
        print(f"🔑 Ключевые слова: НЕТ (default RELATED)")
    
    # Проверка логики обработки
    if mention_type == 'EXTERNAL':
        print(f"⏭  Действие: ПРОПУСТИТЬ (внешний документ)")
    else:
        print(f"✨ Действие: СОЗДАТЬ СВЯЗЬ типа {mention_type}")

print("\n" + "=" * 80)
print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
print("=" * 80)
