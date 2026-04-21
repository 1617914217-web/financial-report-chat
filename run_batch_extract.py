# -*- coding: utf-8 -*-
"""
批量提取入口：扫描目录，批量处理 PDF 文件
用法:
    python run_batch_extract.py                    # 扫描正式数据目录
    python run_batch_extract.py <pdf_dir>          # 指定目录
    python run_batch_extract.py <pdf_dir> --workers 16
"""
import os, sys, json, time, argparse

# 将项目根目录加入 path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

from extractors.pdf_extractor import run_batch, PDFExtractor, MYSQL_CONFIG

# 默认 PDF 目录
DEFAULT_PDF_DIR = os.path.join(BASE, "..", "正式数据")


def main():
    parser = argparse.ArgumentParser(description="批量提取 PDF 财务数据")
    parser.add_argument("pdf_dir", nargs="?", default=DEFAULT_PDF_DIR,
                        help="PDF 文件所在目录")
    parser.add_argument("-w", "--workers", type=int, default=8,
                        help="并行进程数（默认8）")
    parser.add_argument("--no-mysql", action="store_true",
                        help="仅提取，不写入 MySQL")
    args = parser.parse_args()

    pdf_dir = args.pdf_dir
    if not os.path.exists(pdf_dir):
        print(f"[ERROR] 目录不存在: {pdf_dir}")
        sys.exit(1)

    print(f"[Config] PDF 目录: {pdf_dir}")
    print(f"[Config] MySQL: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}")
    print(f"[Config] Workers: {args.workers}")
    print(f"[Config] MySQL写入: {'关闭' if args.no_mysql else '开启'}")
    print()

    if args.no_mysql:
        # 仅提取，不写库
        pdf_files = []
        for root, _, files in os.walk(pdf_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
        print(f"Found {len(pdf_files)} PDFs")
        success = failed = 0
        for p in pdf_files:
            try:
                ext = PDFExtractor(p)
                results = ext.extract()
                if results:
                    success += 1
                    print(f"  [OK] {os.path.basename(p)} -> {len(results)} records")
                else:
                    failed += 1
                    print(f"  [EMPTY] {os.path.basename(p)}")
            except Exception as e:
                failed += 1
                print(f"  [FAIL] {os.path.basename(p)}: {e}")
        print(f"\nDone: {success} ok / {failed} failed")
    else:
        result = run_batch(pdf_dir, n_workers=args.workers)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
