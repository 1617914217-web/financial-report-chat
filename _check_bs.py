# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查balance_sheet中600080的所有记录
        cur.execute("""
            SELECT report_period, asset_total_assets, asset_cash_and_cash_equivalents,
                   liability_total_liabilities, equity_total_equity
            FROM balance_sheet
            WHERE stock_code='600080'
            ORDER BY report_period
        """)
        print("=== 金花股份 balance_sheet ===")
        for row in cur.fetchall():
            print(row)

        # 查stock_income_statement_data中600080的记录
        cur.execute("""
            SELECT report_period, total_operating_revenue, net_profit
            FROM stock_income_statement_data
            WHERE stock_code='600080'
            ORDER BY report_period
        """)
        print("\n=== 金花股份 income_statement ===")
        for row in cur.fetchall():
            print(row)

        # 查core_performance_indicators_sheet中600080的记录
        cur.execute("""
            SELECT report_period, gross_profit_margin, net_profit_margin, roe
            FROM core_performance_indicators_sheet
            WHERE stock_code='600080'
            ORDER BY report_period
        """)
        print("\n=== 金花股份 core_performance ===")
        for row in cur.fetchall():
            print(row)

finally:
    conn.close()
