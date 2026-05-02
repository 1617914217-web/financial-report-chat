# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("DESCRIBE raw_extracted")
        for row in cur.fetchall():
            print(row)
finally:
    conn.close()
