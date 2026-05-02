# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 检查各表数据量
        tables = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']
        for tbl in tables:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            total = cur.fetchone()[0]

            # 检查有数据的记录数（非空字段）
            if tbl == 'balance_sheet':
                cur.execute(f"SELECT COUNT(asset_total_assets) FROM {tbl}")
            elif tbl == 'income_sheet':
                cur.execute(f"SELECT COUNT(net_cash_flow) FROM {tbl}")
            elif tbl == 'stock_income_statement_data':
                cur.execute(f"SELECT COUNT(net_profit) FROM {tbl}")
            elif tbl == 'core_performance_indicators_sheet':
                cur.execute(f"SELECT COUNT(gross_profit_margin) FROM {tbl}")

            non_null = cur.fetchone()[0]
            print(f"{tbl}: 总记录={total}, 有数据={non_null}")

        # 查金花股份的资产负债表
        print("\n=== 金花股份600080 balance_sheet ===")
        cur.execute("SELECT report_period, asset_total_assets, liability_total_liabilities, equity_total_equity FROM balance_sheet WHERE stock_code='600080' AND report_period LIKE '2022%' LIMIT 5")
        for row in cur.fetchall():
            print(row)

        # 查金花股份的核心指标
        print("\n=== 金花股份600080 core_performance ===")
        cur.execute("SELECT report_period, gross_profit_margin, net_profit_margin, roe FROM core_performance_indicators_sheet WHERE stock_code='600080' AND report_period LIKE '2022%' LIMIT 5")
        for row in cur.fetchall():
            print(row)

finally:
    conn.close()
