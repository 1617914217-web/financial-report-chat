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
        cur.execute("SELECT id, raw_columns, raw_data FROM raw_extracted WHERE auto_table_type='balance_sheet' LIMIT 5")
        with open('_raw_sample.txt', 'w', encoding='utf-8') as f:
            for row in cur.fetchall():
                f.write(f"ID: {row[0]}\n")
                f.write(f"Columns: {row[1]}\n")
                f.write(f"Data: {row[2][:500]}\n")
                f.write("---\n")
        print("Written to _raw_sample.txt")
finally:
    conn.close()
