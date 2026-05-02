# -*- coding: utf-8 -*-
"""测试端到端查询 - 金花股份和万邦德"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from pipeline import FinancialQA

qa = FinancialQA()

test_questions = [
    "金花股份2022年净利润是多少",
    "万邦德2022年净利润是多少",
    "万邦德2023年总资产是多少",
    "金花股份和万邦德2022年总资产对比",
]

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    try:
        result = qa.ask(q)
        print(f"Intent: {result.get('intent')}")
        print(f"SQL: {result.get('sql', 'N/A')}")
        print(f"Data: {result.get('data', 'N/A')}")
        print(f"Conclusion: {result.get('conclusion', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
