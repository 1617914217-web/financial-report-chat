# -*- coding: utf-8 -*-
"""测试万邦德数据查询"""
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from pipeline import FinancialQA

qa = FinancialQA()

# 测试查询
test_questions = [
    "万邦德2022年净利润是多少",
    "万邦德2023年总资产是多少",
    "金花股份和万邦德2022年总资产对比",
]

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    result = qa.process(q)
    print(f"SQL: {result.get('sql', 'N/A')}")
    print(f"Data: {result.get('data', 'N/A')}")
    print(f"Conclusion: {result.get('conclusion', 'N/A')}")
