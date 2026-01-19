#!/usr/bin/env python3
"""
Упрощенный скрипт для анализа паттернов связей между документами.
Анализирует только данные в БД без скачивания файлов.
"""

import os
import re
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict, Counter
from datetime import datetime

def get_db_connection():
    """Подключение к базе данных через DATABASE_URL"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise Exception('DATABASE_URL не настроен в переменных окружения')
    return psycopg2.connect(db_url)

def analyze_link_finding_logs(cursor, schema='public'):
    """Анализировать логи поиска связей для извлечения паттернов"""
    
    query = f"""
        SELECT 
            lfl.document_id,
            lfl.found_references,
            lfl.matched_documents,
            lfl.log_data,
            lfl.created_at,
            d.title,
            d.document_number,
            d.document_date
        FROM {schema}.link_finding_logs lfl
        JOIN {schema}.documents d ON d.id = lfl.document_id
        WHERE lfl.found_references IS NOT NULL 
          AND jsonb_array_length(lfl.found_references) > 0
        ORDER BY lfl.created_at DESC
        LIMIT 100
    """
    
    cursor.execute(query)
    return cursor.fetchall()

def main():
    print("=" * 80)
    print("УПРОЩЕННЫЙ АНАЛИЗ ПАТТЕРНОВ (БЕЗ СКАЧИВАНИЯ ФАЙЛОВ)")
    print("=" * 80)
    print()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()['current_schema']
        print(f"✓ Подключено к базе данных (схема: {schema})")
        print()
        
    except Exception as e:
        print(f"✗ Ошибка подключения к базе данных: {e}")
        return
    
    # Общая статистика
    print("СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("-" * 80)
    
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total_docs,
            COUNT(*) FILTER (WHERE related_count > 0) as docs_with_incoming_links,
            COUNT(*) FILTER (WHERE related_to IS NOT NULL) as docs_with_outgoing_links,
            COUNT(*) FILTER (WHERE is_phantom = TRUE) as phantom_docs,
            COUNT(*) FILTER (WHERE file_cdn_url IS NOT NULL) as docs_with_files
        FROM {schema}.documents
    """)
    stats = cursor.fetchone()
    
    print(f"Всего документов: {stats['total_docs']}")
    print(f"Документов с входящими ссылками (related_count > 0): {stats['docs_with_incoming_links']}")
    print(f"Документов с исходящими ссылками (related_to): {stats['docs_with_outgoing_links']}")
    print(f"Фантомных документов: {stats['phantom_docs']}")
    print(f"Документов с файлами: {stats['docs_with_files']}")
    print()
    
    # Топ документов по количеству входящих ссылок
    print("\nТОП-20 ДОКУМЕНТОВ ПО КОЛИЧЕСТВУ ВХОДЯЩИХ ССЫЛОК")
    print("-" * 80)
    
    cursor.execute(f"""
        SELECT id, title, document_number, document_date, related_count, section
        FROM {schema}.documents
        WHERE related_count > 0
        ORDER BY related_count DESC
        LIMIT 20
    """)
    
    top_docs = cursor.fetchall()
    for i, doc in enumerate(top_docs, 1):
        print(f"{i:2}. [{doc['related_count']:3} ссылок] {doc['title'][:60]}...")
        print(f"    №{doc['document_number']} от {doc['document_date']} | Раздел: {doc['section']}")
    
    # Анализ логов поиска связей
    print("\n\nАНАЛИЗ ЛОГОВ ПОИСКА СВЯЗЕЙ")
    print("-" * 80)
    
    cursor.execute(f"""
        SELECT COUNT(*) as total_logs,
               COUNT(*) FILTER (WHERE found_references IS NOT NULL 
                                AND jsonb_array_length(found_references) > 0) as logs_with_refs
        FROM {schema}.link_finding_logs
    """)
    log_stats = cursor.fetchone()
    
    print(f"Всего логов поиска связей: {log_stats['total_logs']}")
    print(f"Логов с найденными ссылками: {log_stats['logs_with_refs']}")
    print()
    
    # Получаем примеры логов
    logs = analyze_link_finding_logs(cursor, schema)
    print(f"Проанализировано последних логов: {len(logs)}")
    print()
    
    # Анализируем найденные ссылки
    reference_patterns = defaultdict(int)
    matched_counts = Counter()
    
    for log in logs:
        if log['found_references']:
            num_refs = len(log['found_references'])
            reference_patterns[num_refs] += 1
            
            if log['matched_documents']:
                num_matched = len(log['matched_documents'])
                matched_counts[num_matched] += 1
    
    print("\nРАСПРЕДЕЛЕНИЕ НАЙДЕННЫХ ССЫЛОК:")
    print("-" * 80)
    for num_refs in sorted(reference_patterns.keys()):
        count = reference_patterns[num_refs]
        print(f"Документов с {num_refs} ссылками: {count}")
    
    print("\n\nРАСПРЕДЕЛЕНИЕ СОВПАВШИХ ДОКУМЕНТОВ:")
    print("-" * 80)
    for num_matched in sorted(matched_counts.keys()):
        count = matched_counts[num_matched]
        print(f"Логов с {num_matched} совпадениями: {count}")
    
    # Примеры найденных ссылок
    print("\n\nПРИМЕРЫ НАЙДЕННЫХ ССЫЛОК (последние 10):")
    print("-" * 80)
    
    for i, log in enumerate(logs[:10], 1):
        print(f"\n[{i}] Документ: {log['title'][:70]}...")
        print(f"    №{log['document_number']} от {log['document_date']}")
        print(f"    Найдено ссылок: {len(log['found_references'])}")
        
        for ref in log['found_references'][:3]:  # Показываем первые 3
            print(f"      - №{ref.get('number')} от {ref.get('date')}")
        
        if log['matched_documents'] and len(log['matched_documents']) > 0:
            print(f"    Совпало документов в БД: {len(log['matched_documents'])}")
    
    # Анализ структуры связей
    print("\n\nАНАЛИЗ ЦЕПОЧЕК СВЯЗЕЙ")
    print("-" * 80)
    
    # Находим самые длинные цепочки
    cursor.execute(f"""
        WITH RECURSIVE doc_chain AS (
            -- Начальные документы (на них ссылаются, но сами не ссылаются)
            SELECT id, title, document_number, document_date, related_to, 
                   1 as chain_length, 
                   ARRAY[id] as chain_ids
            FROM {schema}.documents
            WHERE related_count > 0 AND related_to IS NULL
            
            UNION ALL
            
            -- Рекурсивно идем по цепочке
            SELECT d.id, d.title, d.document_number, d.document_date, d.related_to,
                   dc.chain_length + 1,
                   dc.chain_ids || d.id
            FROM {schema}.documents d
            INNER JOIN doc_chain dc ON d.related_to = dc.id
            WHERE NOT (d.id = ANY(dc.chain_ids))  -- Избегаем циклов
              AND dc.chain_length < 10  -- Ограничение глубины
        )
        SELECT id, title, document_number, document_date, chain_length, chain_ids
        FROM doc_chain
        ORDER BY chain_length DESC
        LIMIT 10
    """)
    
    chains = cursor.fetchall()
    
    print(f"Найдено цепочек связей: {len(chains)}")
    if chains:
        print(f"Максимальная длина цепочки: {chains[0]['chain_length']}")
        print("\nПримеры самых длинных цепочек:")
        for i, chain in enumerate(chains[:5], 1):
            print(f"\n{i}. Длина цепочки: {chain['chain_length']}")
            print(f"   Документ: {chain['title'][:70]}...")
            print(f"   №{chain['document_number']} от {chain['document_date']}")
            print(f"   ID цепочки: {' -> '.join(map(str, chain['chain_ids']))}")
    
    # Анализ разделов
    print("\n\nСТАТИСТИКА ПО РАЗДЕЛАМ")
    print("-" * 80)
    
    cursor.execute(f"""
        SELECT 
            section,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE related_count > 0) as with_incoming,
            COUNT(*) FILTER (WHERE related_to IS NOT NULL) as with_outgoing,
            AVG(related_count) as avg_incoming
        FROM {schema}.documents
        WHERE section IS NOT NULL
        GROUP BY section
        ORDER BY total DESC
    """)
    
    sections = cursor.fetchall()
    print(f"{'Раздел':<30} | {'Всего':>8} | {'Входящие':>10} | {'Исходящие':>11} | {'Ср.входящих':>13}")
    print("-" * 80)
    
    for sec in sections:
        print(f"{sec['section'][:30]:<30} | {sec['total']:>8} | {sec['with_incoming']:>10} | "
              f"{sec['with_outgoing']:>11} | {float(sec['avg_incoming'] or 0):>13.2f}")
    
    # РЕКОМЕНДАЦИИ
    print("\n\n" + "=" * 80)
    print("РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ ПАРСИНГА")
    print("=" * 80)
    print()
    
    print("1. ПРИОРИТЕТНЫЕ ПАТТЕРНЫ ДЛЯ ДОБАВЛЕНИЯ:")
    print("-" * 80)
    
    recommended_patterns = [
        ("Утрата силы (множ. число)", r"утрачивают\s+силу", 
         "Для случаев когда несколько документов утрачивают силу"),
        
        ("Частичная отмена", r"считать\s+утратившим\s+силу\s+(?:пункт|раздел|часть)", 
         "Для отмены отдельных частей документа"),
        
        ("Приостановление", r"приостановить\s+(?:действие|исполнение)", 
         "Временная приостановка, не отмена"),
        
        ("Продление сроков", r"продлить\s+(?:срок|действие)", 
         "Изменение без фактического изменения содержания"),
        
        ("Ссылки с предлогом", r"(?:на\s+основании|во\s+исполнение|в\s+соответствии\s+с)", 
         "Ссылки на основополагающие документы"),
        
        ("Списки в скобках", r"\((?:в\s+редакции|с\s+изменениями)[^\)]{0,500}\)", 
         "Множественные ссылки в скобках"),
    ]
    
    for i, (name, pattern, desc) in enumerate(recommended_patterns, 1):
        print(f"{i}. {name}")
        print(f"   Паттерн: {pattern}")
        print(f"   Описание: {desc}")
        print()
    
    print("\n2. УЛУЧШЕНИЯ ФОРМАТОВ ДАТА/НОМЕР:")
    print("-" * 80)
    print("Текущий код уже поддерживает:")
    print("  ✓ №NUM от DD.MM.YYYY")
    print("  ✓ от DD.MM.YYYY года №NUM")
    print("  ✓ постановление №NUM от DATE")
    print()
    print("Рекомендуется добавить:")
    print("  • N NUM (латинская N вместо кириллической №)")
    print("  • # NUM (решетка вместо №)")
    print("  • NUM от DATE (без символа номера)")
    print("  • Поддержка диапазонов: №1-5 от DATE")
    print("  • Списки через запятую: №1 от DATE1, №2 от DATE2")
    print()
    
    print("\n3. ОСОБЫЕ СЛУЧАИ:")
    print("-" * 80)
    print("  • Циклические ссылки (когда документы ссылаются друг на друга)")
    print("  • Множественные версии одного документа")
    print("  • Объединенные/разделенные документы")
    print("  • Ссылки на несуществующие документы (создание фантомов)")
    print("  • Ссылки на диапазоны документов")
    print()
    
    print("\n4. ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ:")
    print("-" * 80)
    print("  • Кешировать результаты парсинга для часто обновляемых разделов")
    print("  • Пакетная обработка документов из одного раздела")
    print("  • Индексы на (document_number, document_date) для быстрого поиска")
    print("  • Периодическая переиндексация старых документов")
    print()
    
    # Сохраняем отчет
    report = {
        'analyzed_at': datetime.now().isoformat(),
        'database_stats': dict(stats),
        'top_referenced_documents': [
            {
                'id': d['id'],
                'title': d['title'],
                'number': d['document_number'],
                'date': str(d['document_date']) if d['document_date'] else None,
                'reference_count': d['related_count']
            }
            for d in top_docs
        ],
        'section_stats': [dict(s) for s in sections],
        'longest_chains': [
            {
                'length': c['chain_length'],
                'chain_ids': c['chain_ids'],
                'title': c['title']
            }
            for c in chains[:5]
        ] if chains else [],
        'recommendations': {
            'priority_patterns': [
                {'name': name, 'pattern': pattern, 'description': desc}
                for name, pattern, desc in recommended_patterns
            ]
        }
    }
    
    with open('patterns_analysis_simple.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✓ Отчет сохранен в: patterns_analysis_simple.json")
    print()
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
