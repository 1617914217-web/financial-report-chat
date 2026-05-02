# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # 检查4张表中万邦德的数据
        tables = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE stock_code='002082'")
            count = cur.fetchone()[0]
            print(f"{table}: {count} 条")

            if count > 0:
                cur.execute(f"SELECT stock_code, report_period, report_year FROM {table} WHERE stock_code='002082' LIMIT 3")
                for row in cur.fetchall():
                    print(f"  {row}")
finally:
    conn.close()
