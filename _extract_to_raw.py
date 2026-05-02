# -*- coding: utf-8 -*-
"""提取万邦德PDF到raw_extracted表"""
import sys
import os
import json
import re

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from extractors.engine_a_rules import EngineA
import pymysql

MYSQL_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "181415157Ak.", "database": "intelligent_data_query",
    "charset": "utf8mb4"
}

# 万邦德的PDF文件路径
pdf_files = [
    (r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2022年年度报告.pdf", "002082", "万邦德"),
    (r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2023年年度报告.pdf", "002082", "万邦德"),
]

def save_raw(stock_code, stock_abbr, report_year, table_type, columns, data, source_file):
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO raw_extracted
                (stock_code, stock_abbr, report_period, report_year, auto_table_type,
                 raw_columns, raw_data, process_status, error_msg, source_file, source_engine, source_page, row_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', '', %s, 'engine_a', 0, %s)
            """
            cur.execute(sql, (
                stock_code, stock_abbr, f"{report_year}-12-31", report_year,
                table_type, json.dumps(columns, ensure_ascii=False),
                json.dumps(data, ensure_ascii=False),
                source_file, len(columns)
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"  保存失败: {e}")
        return False
    finally:
        conn.close()

for pdf_path, code, name in pdf_files:
    if not os.path.exists(pdf_path):
        print(f"文件不存在: {pdf_path}")
        continue

    print(f"\n处理: {os.path.basename(pdf_path)}")
    try:
        engine = EngineA(pdf_path)
        tables = engine.run()

        print(f"  提取到 {len(tables)} 张表")
        saved = 0
        for tbl in tables:
            tbl_type = tbl.get("type", "unknown")
            rows = tbl.get("rows", [])
            if not rows:
                continue

            # 转换为raw_extracted格式
            columns = []
            data = {}
            years = set()

            for row in rows:
                label = row.get("label", "")
                if not label:
                    continue
                columns.append(label)
                year = row.get("year")
                value = row.get("value")
                if year and value is not None:
                    years.add(year)
                    if label not in data:
                        data[label] = {}
                    data[label][str(year)] = value

            if columns and data:
                report_year = max(years) if years else 2022
                if save_raw(code, name, report_year, tbl_type, columns, data, pdf_path):
                    saved += 1
                    print(f"    [OK] {tbl_type}: {len(columns)} 个字段")

        print(f"  已保存 {saved} 条到raw_extracted")

    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
