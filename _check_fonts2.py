# -*- coding: utf-8 -*-
import fitz
import sys

# 强制stdout用utf-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

doc = fitz.open(r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-上交所\600080_20230428_FQ2V.pdf")
page = doc[0]
fonts = page.get_fonts()
print(f"Fonts count: {len(fonts)}")
for f in fonts:
    # 只打印安全的部分
    safe = str(f).encode('ascii', 'replace').decode('ascii')
    print(safe)
doc.close()
