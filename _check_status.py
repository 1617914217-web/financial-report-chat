# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT process_status, COUNT(*) FROM raw_extracted GROUP BY process_status")
        print("=== raw_extracted status ===")
        for row in cur.fetchall():
            print(row)

        # 检查balance_sheet是否有数据
        cur.execute("SELECT COUNT(*), COUNT(asset_total_assets) FROM balance_sheet")
        print("\n=== balance_sheet ===")
        print(cur.fetchone())

        # 检查core_performance_indicators_sheet
        cur.execute("SELECT COUNT(*), COUNT(gross_profit_margin) FROM core_performance_indicators_sheet")
        print("\n=== core_performance_indicators_sheet ===")
        print(cur.fetchone())
finally:
    conn.close()
