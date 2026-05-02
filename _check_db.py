# -*- coding: utf-8 -*-
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='181415157Ak.', database='intelligent_data_query', charset='utf8mb4')
with conn.cursor() as cur:
    for t in ['balance_sheet','income_sheet','stock_income_statement_data','core_performance_indicators_sheet']:
        cur.execute(f"SELECT stock_code, report_period FROM {t} WHERE stock_code='002082'")
        rows = cur.fetchall()
        print(f'{t}: {len(rows)} records')
        for r in rows:
            print(f'  {r}')
conn.close()
