# -*- coding: utf-8 -*-
import os, glob

# 检查PDF文件目录
pdf_dirs = [
    'data/pdf',
    'data/pdfs',
    '../data/pdf',
    '../data/pdfs',
]

for d in pdf_dirs:
    if os.path.exists(d):
        files = glob.glob(f"{d}/**/*.pdf", recursive=True)
        print(f"{d}: {len(files)} 个PDF文件")
        # 查找万邦德相关文件
        wanbangde = [f for f in files if '002082' in f or '万邦德' in f]
        print(f"  万邦德相关: {len(wanbangde)} 个")
        for f in wanbangde[:5]:
            print(f"    {f}")
