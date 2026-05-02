# -*- coding: utf-8 -*-
"""
合并所有4张表中的重复记录
"""
import pymysql

TABLES = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)

try:
    for table in TABLES:
        print(f"\n=== 处理表: {table} ===")

        with conn.cursor() as cur:
            # 1. 找出重复记录
            cur.execute(f"""
                SELECT stock_code, report_period, COUNT(*) as cnt
                FROM {table}
                GROUP BY stock_code, report_period
                HAVING cnt > 1
            """)
            duplicates = cur.fetchall()

            if not duplicates:
                print(f"  没有重复记录")
                continue

            print(f"  找到 {len(duplicates)} 组重复记录")

            # 获取列名
            cur.execute(f"DESCRIBE {table}")
            columns = [row[0] for row in cur.fetchall()]

            # 2. 合并每组记录
            merged_count = 0
            for stock_code, report_period, count in duplicates:
                cur.execute(f"""
                    SELECT * FROM {table}
                    WHERE stock_code=%s AND report_period=%s
                """, (stock_code, report_period))
                records = cur.fetchall()

                # 合并数据
                merged = {}
                for record in records:
                    for i, col in enumerate(columns):
                        if record[i] is not None:
                            merged[col] = record[i]

                # 删除旧记录
                cur.execute(f"""
                    DELETE FROM {table}
                    WHERE stock_code=%s AND report_period=%s
                """, (stock_code, report_period))

                # 插入合并后的记录
                if merged:
                    cols = list(merged.keys())
                    placeholders = ', '.join(['%s'] * len(cols))
                    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
                    cur.execute(sql, list(merged.values()))

                merged_count += 1

            conn.commit()
            print(f"  合并完成：{merged_count} 组")

    # 最终验证
    print("\n=== 最终验证 ===")
    with conn.cursor() as cur:
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            total = cur.fetchone()[0]
            print(f"{table}: {total} 条记录")

finally:
    conn.close()
