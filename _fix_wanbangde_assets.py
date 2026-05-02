# -*- coding: utf-8 -*-
"""修复万邦德缺失的总资产数据 - 根据会计恒等式计算"""
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)

try:
    with conn.cursor() as cur:
        # 查找万邦德所有缺失asset_total_assets的记录
        cur.execute("""
            SELECT stock_code, report_period, liability_total_liabilities, equity_total_equity
            FROM balance_sheet
            WHERE stock_code='002082' AND asset_total_assets IS NULL
        """)
        rows = cur.fetchall()
        
        fixed = 0
        for code, period, liab, equity in rows:
            if liab is not None and equity is not None:
                total_assets = float(liab) + float(equity)
                cur.execute("""
                    UPDATE balance_sheet
                    SET asset_total_assets = %s
                    WHERE stock_code=%s AND report_period=%s
                """, (total_assets, code, period))
                fixed += 1
                print(f"Fixed {code} {period}: {liab} + {equity} = {total_assets}")
        
        conn.commit()
        print(f"\nFixed {fixed} records")
        
        # 验证
        cur.execute("SELECT report_period, asset_total_assets FROM balance_sheet WHERE stock_code='002082'")
        for row in cur.fetchall():
            print(f"  {row[0]}: asset_total_assets={row[1]}")
            
finally:
    conn.close()
