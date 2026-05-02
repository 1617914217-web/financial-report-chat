# -*- coding: utf-8 -*-
import pdfplumber

# 深交所PDF
pdf_path = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-深交所\万邦德：2022年年度报告.pdf"

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages[:3], 1):
        print(f"=== Page {i} ===")
        text = page.extract_text() or ""
        print("Text sample:", text[:200] if text else "None")
        
        tables = page.extract_tables()
        if tables:
            for j, tbl in enumerate(tables[:1]):
                print(f"\nTable {j}:")
                for row in tbl[:3]:
                    print("  Row:", [str(c)[:30] if c else "None" for c in row])
        print()
