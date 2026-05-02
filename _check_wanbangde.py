# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查万邦德2022年的数据
        print("=== 万邦德 002082 balance_sheet ===")
        cur.execute("""
            SELECT report_period, asset_total_assets
            FROM balance_sheet
            WHERE stock_code='002082' AND report_period='2022-12-31'
        """)
        for row in cur.fetchall():
            print(row)

        print("\n=== 万邦德 002082 stock_income_statement ===")
        cur.execute("""
            SELECT report_period, total_operating_revenue, net_profit
            FROM stock_income_statement_data
            WHERE stock_code='002082' AND report_period='2022-12-31'
        """)
        for row in cur.fetchall():
            print(row)

        # 查所有002082的记录
        print("\n=== 万邦德所有记录 ===")
        cur.execute("""
            SELECT report_period, asset_total_assets
            FROM balance_sheet
            WHERE stock_code='002082'
            ORDER BY report_period
        """)
        for row in cur.fetchall():
            print(row)

finally:
    conn.close()
