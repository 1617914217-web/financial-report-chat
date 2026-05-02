# -*- coding: utf-8 -*-
"""合并万邦德的重复记录"""
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)

def merge_table(table):
    with conn.cursor() as cur:
        # 查找重复记录
        cur.execute(f"""
            SELECT stock_code, report_period, COUNT(*) as cnt
            FROM {table}
            WHERE stock_code='002082'
            GROUP BY stock_code, report_period
            HAVING cnt > 1
        """)
        duplicates = cur.fetchall()

        if not duplicates:
            print(f"{table}: 无重复")
            return 0

        merged = 0
        for code, period, cnt in duplicates:
            # 获取该组所有记录
            cur.execute(f"""
                SELECT * FROM {table}
                WHERE stock_code=%s AND report_period=%s
            """, (code, period))
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]

            # 合并：取非空值
            merged_data = {}
            for row in rows:
                for i, col in enumerate(col_names):
                    val = row[i]
                    if val is not None:
                        merged_data[col] = val

            # 删除旧记录
            cur.execute(f"""
                DELETE FROM {table}
                WHERE stock_code=%s AND report_period=%s
            """, (code, period))

            # 插入合并后的记录
            cols = list(merged_data.keys())
            placeholders = ', '.join(['%s'] * len(cols))
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
            cur.execute(sql, list(merged_data.values()))
            merged += 1

        conn.commit()
        print(f"{table}: 合并 {merged} 组重复记录")
        return merged

try:
    for table in ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']:
        merge_table(table)
finally:
    conn.close()
