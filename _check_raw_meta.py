# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查看raw_extracted表结构
        cur.execute("DESCRIBE raw_extracted")
        print('=== raw_extracted 结构 ===')
        for row in cur.fetchall():
            print(row)

        # 看最早的记录时间
        cur.execute("SELECT MIN(created_at), MAX(created_at), COUNT(*) FROM raw_extracted")
        print('\n=== 时间范围 ===')
        print(cur.fetchone())

        # 看一条完整记录
        cur.execute("SELECT * FROM raw_extracted WHERE auto_table_type='balance_sheet' LIMIT 1")
        print('\n=== 完整记录示例 ===')
        row = cur.fetchone()
        if row:
            for i, col in enumerate(cur.description):
                print(f"{col[0]}: {row[i]}")
finally:
    conn.close()
