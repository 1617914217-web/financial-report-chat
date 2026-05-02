# -*- coding: utf-8 -*-
"""提取万邦德的PDF数据 - 使用pdf_extractor的正确格式"""
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from extractors.pdf_extractor import PDFExtractor

# 万邦德的PDF文件路径
pdf_files = [
    r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2022年年度报告.pdf",
    r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2023年年度报告.pdf",
]

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
            # 使用内置的to_mysql方法
            n = extractor.to_mysql()
            print(f"  已写入MySQL: {n} 条")
        else:
            print("  未提取到数据")

    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
