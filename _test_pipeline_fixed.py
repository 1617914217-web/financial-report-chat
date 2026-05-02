# -*- coding: utf-8 -*-
"""测试端到端查询 - 修复编码问题"""
import sys, os, io

# 强制UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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

print("=" * 60)
print("财务智能问数系统 - 端到端测试")
print("=" * 60)

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"问题: {q}")
    try:
        result = qa.ask(q)
        print(f"意图: {result.get('intent')}")
        print(f"SQL: {result.get('sql', 'N/A')}")
        data = result.get('data', [])
        if data:
            print(f"数据: {data}")
        conclusion = result.get('conclusion', 'N/A')
        print(f"结论: {conclusion}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*60}")
print("测试完成")
