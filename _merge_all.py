# -*- coding: utf-8 -*-
"""
合并 balance_sheet 中所有重复记录
"""
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)

try:
    with conn.cursor() as cur:
        # 1. 找出所有重复记录
        cur.execute("""
            SELECT stock_code, report_period, COUNT(*) as cnt
            FROM balance_sheet
            GROUP BY stock_code, report_period
            HAVING cnt > 1
        """)
        duplicates = cur.fetchall()
        print(f"找到 {len(duplicates)} 组重复记录")

        # 获取列名
        cur.execute("DESCRIBE balance_sheet")
        columns = [row[0] for row in cur.fetchall()]

        # 2. 对每组重复记录进行合并
        merged_count = 0
        for stock_code, report_period, count in duplicates:
            # 获取该组所有记录
            cur.execute("""
                SELECT * FROM balance_sheet
                WHERE stock_code=%s AND report_period=%s
            """, (stock_code, report_period))
            records = cur.fetchall()

            # 合并数据：取第一个非None值
            merged = {}
            for record in records:
                for i, col in enumerate(columns):
                    if record[i] is not None:
                        merged[col] = record[i]

            # 删除旧记录
            cur.execute("""
                DELETE FROM balance_sheet
                WHERE stock_code=%s AND report_period=%s
            """, (stock_code, report_period))

            # 插入合并后的记录
            if merged:
                cols = list(merged.keys())
                placeholders = ', '.join(['%s'] * len(cols))
                sql = f"INSERT INTO balance_sheet ({', '.join(cols)}) VALUES ({placeholders})"
                cur.execute(sql, list(merged.values()))

            merged_count += 1

            if merged_count % 100 == 0:
                print(f"  已处理 {merged_count} 组...")

        conn.commit()
        print(f"\n合并完成：处理了 {merged_count} 组重复记录")

        # 3. 验证结果
        cur.execute("""
            SELECT stock_code, report_period,
                   asset_total_assets, asset_cash_and_cash_equivalents
            FROM balance_sheet
            WHERE stock_code='600080' AND report_period='2022-12-31'
        """)
        result = cur.fetchall()
        print(f"\n验证：金花股份2022年合并后有 {len(result)} 条记录")
        for row in result:
            print(f"  {row}")

finally:
    conn.close()
