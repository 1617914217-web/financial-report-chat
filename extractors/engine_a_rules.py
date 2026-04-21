# -*- coding: utf-8 -*-
"""
上交所/深交所 PDF 年报财务数据提取引擎（规则引擎）
基于 pdfplumber，支持：
  - 上交所（600xxx）：标准格式，表头含年份
  - 深交所（00xxxx / 002xxx / 300xxx）：年份在数据行，数值列错位

表类型识别：
  利润表、资产负债表、核心指标表、股票利润表
"""
import re, os, json
from typing import List, Dict, Optional, Tuple
import pdfplumber


# ── 工具函数 ──────────────────────────────────────────────────────────────

def parse_numeric(s: str) -> Optional[float]:
    """解析含千分位/逗号的数值，返回 float 或 None"""
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "—", "―", "/", "nan", "None", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_years_from_texts(texts: List[str]) -> Dict[int, int]:
    """
    从文本列表中识别年份列映射。
    支持：'2022年'、'2022-12-31'、'2022/12/31'、'2023年1-3月'
    返回: {col_idx: year}
    """
    year_map = {}
    for ci, t in enumerate(texts):
        t = str(t).strip()
        m = re.search(r"(20[12]\d)", t)
        if m:
            year_map[ci] = int(m.group(1))
    return year_map


def detect_table_type(headers: List[str], page_text: str = "") -> str:
    """
    根据表头关键词识别表类型。
    返回：'income_sheet' | 'balance_sheet' | 'core_performance_indicators_sheet'
          | 'stock_income_statement_data' | 'unknown'
    """
    header_str = " ".join(str(h) for h in headers).lower()
    text_str = page_text.lower()

    # 利润表
    if any(kw in header_str or kw in text_str for kw in
           ["营业收入", "营业成本", "净利润", "利润总额", "财务费用",
            "销售费用", "管理费用", "研发费用", "投资收益"]):
        # 区分：核心指标表 vs 利润表
        if any(kw in header_str for kw in ["毛利率", "净利率", "加权平均净资产收益率",
                                            "扣除非经常性损益", "基本每股收益"]):
            # 这类同时出现多个关键词，按具体内容细分
            pass
        if "利润表" in header_str or "利润表" in text_str:
            return "income_sheet"
        if any(kw in header_str for kw in ["营业利润", "利润总额", "财务费用"]):
            return "income_sheet"

    # 股票利润表（每股收益相关）
    if any(kw in header_str for kw in
           ["基本每股收益", "稀释每股收益", "扣除非经常性损益", "扣非净利润"]):
        if "每股" in header_str:
            return "stock_income_statement_data"

    # 核心绩效指标
    if any(kw in header_str for kw in
           ["毛利率", "净利率", "加权平均净资产收益率", "基本每股收益",
            "稀释每股收益", "资产负债率", "流动比率", "速动比率",
            "总资产周转率", "营业收入增长率", "净利润增长率",
            "存货周转率", "应收账款周转率", "净资产收益率"]):
        return "core_performance_indicators_sheet"

    # 资产负债表
    if any(kw in header_str for kw in
           ["货币资金", "应收账款", "存货", "固定资产", "无形资产",
            "短期借款", "长期借款", "应付账款", "资产总计", "负债合计",
            "所有者权益", "净资产"]):
        if "资产负债表" in header_str or "资产" in header_str:
            return "balance_sheet"

    # 通用关键词 fallback
    if "利润表" in text_str or "利润表" in header_str:
        return "income_sheet"
    if "资产负债表" in text_str or "资产负债表" in header_str:
        return "balance_sheet"

    return "unknown"


def is_valid_row(row: List[str], min_cols: int = 2) -> bool:
    """判断是否为有效数据行（至少有标签列+一个数值列）"""
    if not row or len(row) < min_cols:
        return False
    # 至少有一个非空非短横的标签
    labels = sum(1 for c in row[:3] if str(c).strip() and str(c).strip() not in ("-", "—"))
    if labels == 0:
        return False
    # 至少有一个可解析数值
    return any(parse_numeric(c) is not None for c in row)


# ── 主引擎 ─────────────────────────────────────────────────────────────────

class PDFExtractorEngineA:
    """
    规则引擎：从 PDF 提取财务数据
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.stock_code = self._extract_stock_code()
        self.tables = []  # [{type, year, rows, page_no}]
        self._exchange = None  # 'SSE' | 'SZSE'

    def _extract_stock_code(self) -> str:
        """从文件名提取股票代码"""
        fname = os.path.basename(self.pdf_path)
        m = re.search(r"(\d{6})", fname)
        return m.group(1) if m else ""

    @property
    def exchange(self) -> str:
        if self._exchange is not None:
            return self._exchange
        if self.stock_code.startswith("6"):
            self._exchange = "SSE"   # 上交所
        elif self.stock_code.startswith(("0", "2", "3")):
            self._exchange = "SZSE"  # 深交所
        else:
            self._exchange = "SSE"
        return self._exchange

    def run(self) -> List[Dict]:
        """执行提取，返回所有识别到的表"""
        self.tables = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_no, page in enumerate(pdf.pages, start=1):
                    self._process_page(page, page_no)
        except Exception as e:
            print(f"[WARN] Failed to open {self.pdf_path}: {e}")
        return self.tables

    def _process_page(self, page, page_no: int):
        """处理单页：提取表+识别类型"""
        tables = page.extract_tables()
        if not tables:
            return

        page_text = page.extract_text() or ""

        for table in tables:
            if not table or len(table) < 2:
                continue
            # 取前3行作为候选表头
            headers = table[0] if table else []
            table_type = detect_table_type(headers, page_text)
            if table_type == "unknown":
                continue

            # 提取年份（两种格式）
            years = self._extract_years(table, page_text)
            if not years:
                # 从文件名推断（单季度/年度报告）
                inferred = self._infer_year_from_filename()
                if inferred:
                    years = {i: inferred for i in range(len(table[0]))}

            # 解析行数据
            rows = self._parse_rows(table, years, table_type)

            if rows:
                self.tables.append({
                    "type": table_type,
                    "stock_code": self.stock_code,
                    "page_no": page_no,
                    "years": years,
                    "rows": rows,
                })

    def _extract_years(self, table: List[List], page_text: str) -> Dict[int, int]:
        """
        提取年份列映射。
        上交所：年份在表头行；深交所（万邦德等）：年份在数据行，比数值列偏移-1
        """
        if not table:
            return {}

        # 策略1：扫描所有行，找年份模式
        all_texts = []
        for row in table:
            for cell in row:
                all_texts.append(str(cell) if cell is not None else "")

        year_map = extract_years_from_texts(all_texts)
        if year_map:
            return year_map

        # 策略2：表头行扫描
        headers = table[0]
        return extract_years_from_texts(headers)

    def _infer_year_from_filename(self) -> Optional[int]:
        """从文件名推断报告年份"""
        fname = os.path.basename(self.pdf_path)
        m = re.search(r"(20[12]\d)", fname)
        return int(m.group(1)) if m else None

    def _parse_rows(
        self, table: List[List], years: Dict[int, int],
        table_type: str
    ) -> List[Dict]:
        """
        解析行数据，处理深交所列错位问题。
        年份标签列（如'2022年'）与实际数值列差-1。
        """
        results = []
        for row in table[1:]:  # 跳过表头
            if not is_valid_row(row):
                continue

            # 找标签列（第一个非空非短横的单元格）
            label_col = None
            for ci, cell in enumerate(row):
                v = str(cell).strip() if cell is not None else ""
                if v and v not in ("-", "—", "―", "/"):
                    label_col = ci
                    break
            if label_col is None:
                continue

            label = str(row[label_col]).strip()

            # 找数值：优先当前列，再向右扫描，再向左扫描
            for ci in range(len(row)):
                val = row[ci] if ci < len(row) else None
                num = parse_numeric(val)
                if num is not None:
                    col_idx = ci
                    break
            else:
                # 双扫描（右→左）
                col_idx = None
                for nxt in range(label_col + 1, len(row)):
                    if parse_numeric(row[nxt]) is not None:
                        col_idx = nxt
                        break
                if col_idx is None:
                    for prev in range(label_col - 1, -1, -1):
                        if parse_numeric(row[prev]) is not None:
                            col_idx = prev
                            break
                if col_idx is None:
                    continue

            year = years.get(col_idx) or years.get(col_idx - 1) or list(years.values())[0] if years else None

            results.append({
                "label": label,
                "col_idx": col_idx,
                "year": year,
                "value": parse_numeric(row[col_idx]) if col_idx < len(row) else None,
            })

        return results

    def to_records(self) -> List[Dict]:
        """将提取结果转为标准记录格式"""
        records = []
        for tbl in self.tables:
            for row in tbl.get("rows", []):
                records.append({
                    "stock_code": tbl["stock_code"],
                    "table_type": tbl["type"],
                    "year": row.get("year"),
                    "label": row.get("label"),
                    "value": row.get("value"),
                    "page_no": tbl["page_no"],
                })
        return records


# ── 单文件快速测试 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python engine_a_rules.py <pdf_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Extracting: {path}")
    engine = PDFExtractorEngineA(path)
    tables = engine.run()
    print(f"Tables found: {len(tables)}")
    for t in tables:
        print(f"\n[{t['type']}] page {t['page_no']} years={t['years']}")
        for row in t["rows"][:10]:
            print(f"  {row}")
