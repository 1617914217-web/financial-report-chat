# -*- coding: utf-8 -*-
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='181415157Ak.', database='intelligent_data_query', charset='utf8mb4')
with conn.cursor() as cur:
    cur.execute("SHOW COLUMNS FROM balance_sheet")
    cols = [r[0] for r in cur.fetchall()]
    print('Columns:', cols)
    
    cur.execute("SELECT * FROM balance_sheet WHERE stock_code='002082' AND report_period='2023-12-31'")
    row = cur.fetchone()
    if row:
        print('\nData for 002082 2023-12-31:')
        for i, col in enumerate(cols):
            if row[i] is not None:
                print(f'  {col}: {row[i]}')
    else:
        print('No data found')
conn.close()
