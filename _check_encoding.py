# -*- coding: utf-8 -*-
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        cur.execute("SHOW VARIABLES LIKE 'character_set_%'")
        for row in cur.fetchall():
            print(row[0], '=', row[1])
        print('---')
        cur.execute("SHOW CREATE TABLE balance_sheet")
        print(cur.fetchone()[1][:300])
        print('---')
        cur.execute("SELECT stock_abbr FROM balance_sheet LIMIT 5")
        for row in cur.fetchall():
            print(repr(row[0]))
finally:
    conn.close()
