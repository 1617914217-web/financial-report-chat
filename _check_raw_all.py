# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查所有记录数
        cur.execute("SELECT COUNT(*) FROM raw_extracted")
        total = cur.fetchone()[0]
        print(f"raw_extracted 总记录数: {total}")

        # 查万邦德
        cur.execute("SELECT COUNT(*) FROM raw_extracted WHERE stock_code='002082'")
        wb = cur.fetchone()[0]
        print(f"万邦德(002082)记录数: {wb}")

        # 查所有公司代码
        cur.execute("SELECT DISTINCT stock_code FROM raw_extracted LIMIT 20")
        codes = [row[0] for row in cur.fetchall()]
        print(f"前20个公司代码: {codes}")
finally:
    conn.close()
