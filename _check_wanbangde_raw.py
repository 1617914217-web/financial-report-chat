# -*- coding: utf-8 -*-
import pymysql
import json

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, stock_code, auto_table_type, raw_columns FROM raw_extracted WHERE stock_code='002082'")
        for row in cur.fetchall():
            print(f"ID={row[0]}, code={row[1]}, type={row[2]}")
            cols = json.loads(row[3]) if row[3] else []
            print(f"  columns: {cols[:5]}...")
finally:
    conn.close()
