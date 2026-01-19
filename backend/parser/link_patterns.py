"""Паттерны и классификация упоминаний документов"""
import re
from typing import List, Dict, Tuple

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

DOCUMENT_PATTERNS = [
    (r'от\s+(\d{2}\.\d{2}\.\d{4})\s*г(?:ода)?\.?\s+№\s*(\d+)', 'date_first'),
    (r'от\s+(\d{2}\.\d{2}\.\d{4})\s*г(?:ода)?\.?\s+N\s*(\d+)', 'date_first'),
    (r'постановлени[ея]\s+№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'постановлени[ея]\s+N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'№\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
    (r'N\s*(\d+)\s+от\s+(\d{2}\.\d{2}\.\d{4})', 'number_first'),
]

EXCLUSION_PHRASES = [
    'правительства смоленской области',
    'администрации смоленской области',
    'правительства российской федерации',
    'правительства рф'
]


def extract_mentions(text: str) -> List[Dict]:
    """Извлечь упоминания документов из текста"""
    mentions = []
    
    for pattern, order_type in DOCUMENT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if order_type == 'date_first':
                date_str = match.group(1)
                number_str = match.group(2)
            else:
                number_str = match.group(1)
                date_str = match.group(2)
            
            context_start = max(0, match.start() - 100)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end].replace('\n', ' ')
            
            pattern_name = f"{pattern[:50]}... ({order_type})"
            
            mentions.append({
                'number': number_str,
                'date': date_str,
                'context': context,
                'pattern': pattern_name,
                'position': match.start()
            })
    
    return mentions


def classify_mention(context: str) -> Tuple[str, List[str]]:
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


