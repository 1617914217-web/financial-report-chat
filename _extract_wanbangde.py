# -*- coding: utf-8 -*-
"""提取万邦德的PDF数据"""
import sys
import os

# 添加项目根目录到path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from extractors.pdf_extractor import PDFExtractor
import pymysql

# 万邦德的PDF文件路径
pdf_files = [
    r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2022年年度报告.pdf",
    r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2023年年度报告.pdf",
]

# MySQL配置
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "181415157Ak.",
    "database": "intelligent_data_query",
    "charset": "utf8mb4",
}

def save_to_mysql(results):
    """保存提取结果到MySQL"""
    if not results:
        return 0

    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            count = 0
            for item in results:
                # 插入raw_extracted表
                sql = """
                    INSERT INTO raw_extracted
                    (stock_code, stock_abbr, report_period, report_year, auto_table_type,
                     raw_columns, raw_data, process_status, error_msg, source_file, source_engine, source_page)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', '', %s, %s, %s)
                """
                cur.execute(sql, (
                    item.get('stock_code', ''),
                    item.get('stock_abbr', ''),
                    item.get('report_period', ''),
                    item.get('report_year', 0),
                    item.get('table_type', 'unknown'),
                    json.dumps(item.get('columns', []), ensure_ascii=False),
                    json.dumps(item.get('data', {}), ensure_ascii=False),
                    item.get('source_file', ''),
                    item.get('source_engine', 'engine_a'),
                    item.get('source_page', 0),
                ))
                count += 1
            conn.commit()
            return count
    finally:
        conn.close()

# 处理每个PDF
import json

for pdf_path in pdf_files:
    if not os.path.exists(pdf_path):
        print(f"文件不存在: {pdf_path}")
        continue

    print(f"\n处理: {os.path.basename(pdf_path)}")
    try:
        extractor = PDFExtractor(pdf_path)
        results = extractor.extract()

        if results:
            print(f"  提取成功: {len(results)} 条记录")
            for r in results[:3]:  # 只显示前3条
                print(f"    - {r.get('table_type')}: {r.get('columns', [])[:3]}...")

            # 保存到MySQL
            count = save_to_mysql(results)
            print(f"  已保存到MySQL: {count} 条")
        else:
            print("  未提取到数据")

    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
