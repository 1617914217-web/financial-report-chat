# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 检查数据库字符集
        cur.execute("SHOW VARIABLES LIKE 'character_set_%'")
        print("=== Database character sets ===")
        for row in cur.fetchall():
            print(row)

        # 检查连接字符集
        print("\n=== Connection encoding ===")
        cur.execute("SELECT @@character_set_client, @@character_set_connection, @@character_set_results")
        print(cur.fetchone())

        # 直接读取raw_columns的bytes
        cur.execute("SELECT raw_columns FROM raw_extracted WHERE id=54227")
        raw = cur.fetchone()[0]
        print("\n=== Raw bytes analysis ===")
        print("Type:", type(raw))
        print("Repr:", repr(raw[:50]))
        print("UTF-8 decode:", raw.encode('latin1').decode('utf-8', errors='replace')[:50])
finally:
    conn.close()
