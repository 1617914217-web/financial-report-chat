# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查report_year分布
        cur.execute("SELECT report_year, COUNT(*) FROM raw_extracted GROUP BY report_year ORDER BY report_year")
        print("=== report_year 分布 ===")
        for row in cur.fetchall():
            print(row)

        # 查report_period格式
        cur.execute("SELECT DISTINCT report_period FROM raw_extracted LIMIT 10")
        print("\n=== report_period 样例 ===")
        for row in cur.fetchall():
            print(row)

        # 查金花股份的report_year
        cur.execute("SELECT report_year, report_period, auto_table_type FROM raw_extracted WHERE stock_code='600080' LIMIT 5")
        print("\n=== 金花股份样例 ===")
        for row in cur.fetchall():
            print(row)

finally:
    conn.close()
