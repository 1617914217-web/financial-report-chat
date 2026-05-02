# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 查所有表中的公司列表
        tables = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']

        all_codes = set()
        for table in tables:
            cur.execute(f"SELECT DISTINCT stock_code FROM {table}")
            codes = {row[0] for row in cur.fetchall()}
            all_codes.update(codes)
            print(f"{table}: {len(codes)} 家公司")

        print(f"\n总共 {len(all_codes)} 家不同公司")
        print(f"公司代码: {sorted(all_codes)}")

        # 检查万邦德是否在raw_extracted中
        cur.execute("SELECT COUNT(*) FROM raw_extracted WHERE stock_code='002082'")
        count = cur.fetchone()[0]
        print(f"\nraw_extracted 中万邦德(002082)记录数: {count}")

finally:
    conn.close()
