#!/usr/bin/env python3
"""Тест запуска поиска связей через API"""
import requests
import json
import time

PARSER_URL = 'https://functions.poehali.dev/8c4db4b8-687e-471b-add5-e4517d47764c'

def test_find_relations():
    print("🚀 Запуск поиска связей...")
    
    response = requests.post(
        PARSER_URL,
        json={'action': 'find_relations', 'auto_loop': False, 'iteration': 1},
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    return response.json()

if __name__ == '__main__':
    result = test_find_relations()
    
    if result.get('session_id'):
        print(f"\n✅ Session ID: {result['session_id']}")
        print(f"📊 Total: {result.get('total_documents')}")
        print(f"⏳ Remaining: {result.get('remaining')}")
        print(f"✨ Processed: {result.get('total_processed')}")
        print(f"🔗 Links created: {result.get('links_created')}")
