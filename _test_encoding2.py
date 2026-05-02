# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT raw_columns FROM raw_extracted WHERE id=54227")
        raw = cur.fetchone()[0]

        # 写入UTF-8文件
        with open('_encoding_test.txt', 'w', encoding='utf-8') as f:
            f.write(raw)
        print("Written to _encoding_test.txt")

        # 检查字符串的unicode码点
        print("Codepoints:", [hex(ord(c)) for c in raw[:10]])
finally:
    conn.close()
