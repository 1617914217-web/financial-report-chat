# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查raw_extracted中万邦德的数据
        cur.execute("""
            SELECT auto_table_type, report_period, raw_columns
            FROM raw_extracted
            WHERE stock_code='002082'
            LIMIT 10
        """)
        print("=== raw_extracted 中万邦德的数据 ===")
        for row in cur.fetchall():
            print(f"table={row[0]}, period={row[1]}, cols={row[2][:100]}")

        # 统计万邦德各表的数据量
        cur.execute("""
            SELECT auto_table_type, COUNT(*)
            FROM raw_extracted
            WHERE stock_code='002082'
            GROUP BY auto_table_type
        """)
        print("\n=== 万邦德各表数据量 ===")
        for row in cur.fetchall():
            print(row)

finally:
    conn.close()
