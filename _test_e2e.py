# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
os.chdir(r'C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\任务B_财报智能抽取')
sys.path.insert(0, '.')

from pipeline import FinancialQA

qa = FinancialQA()

tests = [
    '金花股份2022年净利润是多少',
    '万邦德2023年总资产',
    '2022年净利润排名前3的公司',
    '金花股份和万邦德2022年总资产对比',
]

for q in tests:
    print(f'问题: {q}')
    r = qa.ask(q)
    print(f'意图: {r["intent"]}')
    print(f'槽位: {r["slots"]}')
    print(f'SQL: {r["sql"][:120] if r["sql"] else "None"}')
    print(f'数据: {str(r["data"][:2]) if r["data"] else "None"}')
    print(f'结论: {r["conclusion"][:100] if r["conclusion"] else "None"}')
    print('---')
