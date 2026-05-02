# -*- coding: utf-8 -*-
import fitz  # pymupdf

pdf_path = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-上交所\600080_20230428_FQ2V.pdf"

doc = fitz.open(pdf_path)
for i in range(min(3, len(doc))):
    page = doc[i]
    print(f"=== Page {i+1} ===")
    text = page.get_text()
    print("Text sample:", text[:200] if text else "None")
    print()
doc.close()
