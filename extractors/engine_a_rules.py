# -*- coding: utf-8 -*-
"""
规则引擎：从PDF提取财务数据
支持上交所/深交所，处理列错位问题
"""
import re
import os
import pdfplumber


def parse_num(s):
    """解析数字，处理千分位"""
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "—", "/", "nan", "None"):
        return None
    try:
        return float(s)
    except:
        return None


def find_years(texts):
    """从文本找年份，返回{列索引: 年份}"""
    years = {}
    for i, t in enumerate(texts):
        t = str(t).strip()
        m = re.search(r"(20[12]\d)", t)
        if m:
            years[i] = int(m.group(1))
    return years


def detect_type(headers, page_text=""):
    """识别表类型"""
    h = " ".join(str(x) for x in headers).lower()
    t = page_text.lower()

    # 利润表
    if any(k in h or k in t for k in ["营业收入", "净利润", "财务费用", "营业利润"]):
        if "利润表" in h or "利润表" in t:
            return "income_sheet"
        if any(k in h for k in ["营业利润", "财务费用"]):
            return "income_sheet"

    # 每股收益
    if any(k in h for k in ["基本每股收益", "稀释每股收益", "扣非"]):
        if "每股" in h:
            return "stock_income_statement_data"

    # 核心指标
    if any(k in h for k in ["毛利率", "净利率", "ROE", "资产负债率", "流动比率"]):
        return "core_performance_indicators_sheet"

    # 资产负债表
    if any(k in h for k in ["货币资金", "应收账款", "存货", "固定资产", "资产总计"]):
        if "资产负债表" in h or "资产" in h:
            return "balance_sheet"

    return "unknown"


def is_valid(row):
    """判断是否有效数据行"""
    if not row or len(row) < 2:
        return False
    # 有标签
    labels = sum(1 for c in row[:3] if str(c).strip() and str(c).strip() not in ("-", "—"))
    if labels == 0:
        return False
    # 有数值
    return any(parse_num(c) is not None for c in row)


class EngineA:
    """规则引擎"""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.code = self._get_code()
        self.tables = []

    def _get_code(self):
        m = re.search(r"(\d{6})", os.path.basename(self.pdf_path))
        return m.group(1) if m else ""

    def run(self):
        """执行提取"""
        self.tables = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    self._page(page, i)
        except Exception as e:
            print(f"[失败] {self.pdf_path}: {e}")
        return self.tables

    def _page(self, page, page_no):
        """处理单页"""
        tbls = page.extract_tables()
        if not tbls:
            return

        txt = page.extract_text() or ""

        for tbl in tbls:
            if not tbl or len(tbl) < 2:
                continue

            headers = tbl[0]
            ttype = detect_type(headers, txt)
            if ttype == "unknown":
                continue

            # 找年份
            years = self._find_years(tbl, txt)
            if not years:
                inferred = self._infer_year()
                if inferred:
                    years = {i: inferred for i in range(len(tbl[0]))}

            # 解析行
            rows = self._parse(tbl, years)
            if rows:
                self.tables.append({
                    "type": ttype,
                    "stock_code": self.code,
                    "page_no": page_no,
                    "years": years,
                    "rows": rows,
                })

    def _find_years(self, tbl, txt):
        """找年份列"""
        # 扫描所有单元格
        all_texts = []
        for row in tbl:
            for cell in row:
                all_texts.append(str(cell) if cell else "")
        return find_years(all_texts)

    def _infer_year(self):
        """从文件名推断年份"""
        m = re.search(r"(20[12]\d)", os.path.basename(self.pdf_path))
        return int(m.group(1)) if m else None

    def _parse(self, tbl, years):
        """解析行数据，处理列错位"""
        results = []

        for row in tbl[1:]:  # 跳表头
            if not is_valid(row):
                continue

            # 找标签列
            label_col = None
            for i, cell in enumerate(row):
                v = str(cell).strip() if cell else ""
                if v and v not in ("-", "—", "/"):
                    label_col = i
                    break
            if label_col is None:
                continue

            label = str(row[label_col]).strip()

            # 找数值：当前列 → 向右 → 向左（解决列错位）
            col_idx = None
            for i in range(len(row)):
                if parse_num(row[i]) is not None:
                    col_idx = i
                    break

            # 向右扫
            if col_idx is None:
                for i in range(label_col + 1, len(row)):
                    if parse_num(row[i]) is not None:
                        col_idx = i
                        break

            # 向左扫
            if col_idx is None:
                for i in range(label_col - 1, -1, -1):
                    if parse_num(row[i]) is not None:
                        col_idx = i
                        break

            if col_idx is None:
                continue

            # 年份（可能错位1列）
            year = years.get(col_idx) or years.get(col_idx - 1)
            if not year and years:
                year = list(years.values())[0]

            results.append({
                "label": label,
                "year": year,
                "value": parse_num(row[col_idx]) if col_idx < len(row) else None,
                "col": col_idx,
            })

        return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python engine_a_rules.py <pdf>")
        sys.exit(1)

    engine = EngineA(sys.argv[1])
    tables = engine.run()
    print(f"找到{len(tables)}张表")
    for t in tables:
        print(f"\n[{t['type']}] 第{t['page_no']}页")
        for r in t["rows"][:5]:
            print(f"  {r['label']}: {r['value']} ({r['year']})")
