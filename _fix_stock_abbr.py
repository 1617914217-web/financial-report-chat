# -*- coding: utf-8 -*-
"""
修复 stock_abbr 为空的问题
从 company_alias.json 获取公司名称
"""
import json, pymysql

# 加载公司别名映射
with open('data/company_alias.json', 'r', encoding='utf-8') as f:
    alias_data = json.load(f)

# 构建 code -> name 映射
code_to_name = {}
for name, code in alias_data.items():
    if isinstance(code, str):
        code_to_name[code] = name

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password='181415157Ak.', database='intelligent_data_query',
    charset='utf8mb4'
)

try:
    with conn.cursor() as cur:
        # 更新所有表的 stock_abbr
        tables = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']

        for table in tables:
            # 获取所有 stock_code
            cur.execute(f"SELECT DISTINCT stock_code FROM {table} WHERE stock_abbr IS NULL OR stock_abbr = ''")
            codes = [row[0] for row in cur.fetchall()]

            updated = 0
            for code in codes:
                if code in code_to_name:
                    name = code_to_name[code]
                    cur.execute(f"""
                        UPDATE {table}
                        SET stock_abbr = %s
                        WHERE stock_code = %s
                    """, (name, code))
                    updated += cur.rowcount

            print(f"{table}: 更新了 {updated} 条记录的 stock_abbr")

        conn.commit()

        # 验证
        print("\n验证:")
        for table in tables:
            cur.execute(f"SELECT stock_code, stock_abbr FROM {table} WHERE stock_code='600080' LIMIT 1")
            row = cur.fetchone()
            if row:
                print(f"  {table}: {row[0]} -> {row[1]}")

finally:
    conn.close()
