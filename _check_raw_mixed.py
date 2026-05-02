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
        # 抽样检查100条raw_data，看是否有正确的中文
        cur.execute("SELECT id, raw_columns, raw_data FROM raw_extracted LIMIT 100")
        correct = 0
        garbled = 0
        for row in cur.fetchall():
            raw_data = row[2]
            if raw_data:
                try:
                    data = json.loads(raw_data)
                    keys = list(data.keys())
                    for k in keys[:3]:
                        # 检查是否包含常见中文字符
                        if any('\u4e00' <= c <= '\u9fff' for c in k):
                            correct += 1
                            break
                    else:
                        # 检查是否全是乱码（非中文非ASCII）
                        if keys and any(ord(c) > 127 for c in keys[0]):
                            garbled += 1
                except:
                    pass
        print(f"Correct Chinese: {correct}")
        print(f"Garbled: {garbled}")

        # 看几条具体的
        cur.execute("SELECT id, raw_columns FROM raw_extracted WHERE auto_table_type='balance_sheet' LIMIT 10")
        print("\n=== Sample raw_columns ===")
        for row in cur.fetchall():
            print(f"ID {row[0]}: {row[1][:100] if row[1] else 'None'}")
finally:
    conn.close()
