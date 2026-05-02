# -*- coding: utf-8 -*-
import fitz  # pymupdf

pdf_path = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件2：财务报告\reports-上交所\600080_20230428_FQ2V.pdf"

doc = fitz.open(pdf_path)
page = doc[0]

# 检查页面是否只有图片（扫描版）
images = page.get_images()
text_blocks = [b for b in page.get_text("blocks") if b[6] == 0]  # type 0 = text

print(f"Images: {len(images)}")
print(f"Text blocks: {len(text_blocks)}")

# 如果有图片，保存第一张看看
if images:
    xref = images[0][0]
    pix = fitz.Pixmap(doc, xref)
    if pix.n > 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    pix.save("_test_page1_image.png")
    print("Saved image: _test_page1_image.png")

doc.close()
