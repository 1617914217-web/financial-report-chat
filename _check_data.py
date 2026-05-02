# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT stock_code, net_profit FROM stock_income_statement_data WHERE stock_code='600080' AND report_period='2022-12-31' LIMIT 5")
        print('=== 利润表 ===')
        for row in cur.fetchall():
            print(row)

        cur.execute("SELECT stock_code, asset_total_assets FROM balance_sheet WHERE stock_code='600080' AND report_period='2022-12-31' LIMIT 5")
        print('=== 资产负债表 ===')
        for row in cur.fetchall():
            print(row)

        cur.execute("SELECT stock_code, gross_profit_margin FROM core_performance_indicators_sheet WHERE stock_code='600080' AND report_period='2022-12-31' LIMIT 5")
        print('=== 核心指标 ===')
        for row in cur.fetchall():
            print(row)
finally:
    conn.close()
