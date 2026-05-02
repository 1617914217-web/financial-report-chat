# -*- coding: utf-8 -*-
"""运行field_matcher处理万邦德数据"""
import sys
import os
import pymysql

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from field_matcher import FieldMatcher

matcher = FieldMatcher()
matcher.connect()

try:
    # 只处理万邦德的pending记录
    with matcher.conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""
            SELECT * FROM raw_extracted
            WHERE stock_code='002082' AND process_status='pending'
        """)
        records = cur.fetchall()
        print(f"找到 {len(records)} 条万邦德待处理记录")

        success = failed = 0
        for rec in records:
            try:
                ok_flag, err, mapped = matcher.process_record(rec)
                if ok_flag and mapped:
                    if matcher.upsert(mapped['table'], mapped['data']):
                        matcher.update_status(rec['id'], 'mapped')
                        success += 1
                        print(f"  [OK] ID={rec['id']} -> {mapped['table']}")
                    else:
                        matcher.update_status(rec['id'], 'failed', 'upsert失败')
                        failed += 1
                else:
                    matcher.update_status(rec['id'], 'failed', err)
                    failed += 1
            except Exception as e:
                matcher.update_status(rec['id'], 'failed', str(e)[:200])
                failed += 1
                print(f"  [ERROR] ID={rec['id']}: {e}")

        print(f"\n完成: {success} 成功, {failed} 失败")

finally:
    matcher.close()
