# -*- coding: utf-8 -*-
import pymysql, json

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查金花股份的原始数据
        cur.execute("""
            SELECT id, stock_code, auto_table_type, raw_columns, raw_data
            FROM raw_extracted
            WHERE stock_code='600080' AND auto_table_type='balance_sheet'
            LIMIT 3
        """)
        for row in cur.fetchall():
            print(f"ID={row[0]}, table_type={row[2]}")
            print(f"columns={row[3]}")
            print(f"data={row[4][:500]}")
            print("---")

        # 查有多少balance_sheet的raw数据包含"资产总计"
        cur.execute("""
            SELECT COUNT(*) FROM raw_extracted
            WHERE auto_table_type='balance_sheet'
            AND raw_data LIKE '%资产总计%'
        """)
        print(f"\n包含'资产总计'的balance_sheet记录数: {cur.fetchone()[0]}")

        # 查raw_extracted中balance_sheet的总数
        cur.execute("SELECT COUNT(*) FROM raw_extracted WHERE auto_table_type='balance_sheet'")
        print(f"balance_sheet总记录数: {cur.fetchone()[0]}")

finally:
    conn.close()
