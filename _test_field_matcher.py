# -*- coding: utf-8 -*-
import pymysql
import json
from field_matcher import FieldMatcher

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)
try:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT * FROM raw_extracted WHERE auto_table_type='balance_sheet' LIMIT 1")
        rec = cur.fetchone()
        print("Raw record keys:", rec.keys())
        print("raw_columns type:", type(rec['raw_columns']))
        print("raw_columns value:", rec['raw_columns'])
        print("raw_data type:", type(rec['raw_data']))
        print("raw_data sample:", str(rec['raw_data'])[:200])
        print("stock_code:", rec['stock_code'])
        print("stock_abbr:", repr(rec['stock_abbr']))
        print("report_period:", rec['report_period'])
        print("report_year:", rec['report_year'])
        print()

        # 测试 field_matcher
        matcher = FieldMatcher()
        matcher.connect()
        ok, err, mapped = matcher.process_record(rec)
        print("Process result:", ok, err)
        if mapped:
            print("Target table:", mapped['table'])
            print("Mapped data keys:", list(mapped['data'].keys()))
            print("asset_total_assets:", mapped['data'].get('asset_total_assets'))
            print("stock_abbr:", repr(mapped['data'].get('stock_abbr')))
        matcher.close()
finally:
    conn.close()
