# -*- coding: utf-8 -*-
"""
PDF 财务数据提取引擎 - 整合版
支持 Engine A（规则）和 Engine B（DeepSeek）两种模式，
输出到 MySQL 或直接返回结果。
"""
import os, json, time, re, multiprocessing as mp
from typing import List, Dict, Optional, Tuple

from .engine_a_rules import PDFExtractorEngineA
from .engine_b_deepseek import PDFExtractorEngineB

# ── 加载配置 ────────────────────────────────────────────────────────────────
try:
    from config_loader import get as _get_env
except ImportError:
    _get_env = lambda k, d="": os.environ.get(k, d)

MYSQL_CONFIG = {
    "host": _get_env("MYSQL_HOST", "127.0.0.1"),
    "port": int(_get_env("MYSQL_PORT", "3306")),
    "user": _get_env("MYSQL_USER", "root"),
    "password": _get_env("MYSQL_PASSWORD", ""),
    "database": _get_env("MYSQL_DATABASE", "intelligent_data_query"),
    "charset": "utf8mb4",
}


def _init_mysql():
    try:
        import pymysql
        return pymysql
    except ImportError:
        return None


# ── 字段映射（中文→MySQL列）────────────────────────────────────────────────

FIELD_MAP = {
    # 资产负债表
    "资产总计": "total_assets", "总资产": "total_assets",
    "负债合计": "total_liabilities", "总负债": "total_liabilities",
    "所有者权益合计": "total_equity", "净资产": "total_equity",
    "货币资金": "monetary_fund", "现金": "monetary_fund",
    "应收账款": "accounts_receivable", "应收账款净额": "accounts_receivable",
    "存货": "inventory", "存货净额": "inventory",
    "固定资产": "fixed_assets", "固定资产净值": "fixed_assets",
    "无形资产": "intangible_assets", "无形资产净额": "intangible_assets",
    "短期借款": "short_term_borrowings", "长期借款": "long_term_borrowings",
    "应付账款": "accounts_payable",
    # 利润表
    "营业收入": "operating_revenue", "营业成本": "operating_cost",
    "净利润": "net_profit",
    "财务费用": "financial_expense",
    "销售费用": "selling_expense", "管理费用": "administrative_expense",
    "研发费用": "rd_expense", "营业利润": "operating_profit",
    "利润总额": "total_profit",
    # 股票利润表
    "基本每股收益": "basic_eps", "稀释每股收益": "diluted_eps",
    "扣非净利润": "net_profit_excluding_non_recurring",
    "扣除非经常性损益后的净利润": "net_profit_excluding_non_recurring",
    "扣除非经常性损益后基本每股收益": "basic_eps_excluding_non_recurring",
    # 核心指标
    "毛利率": "gross_margin", "净利率": "net_margin",
    "加权平均净资产收益率": "weighted_roe", "ROE": "weighted_roe",
    "资产负债率": "debt_asset_ratio",
    "流动比率": "current_ratio", "速动比率": "quick_ratio",
    "营业收入增长率": "revenue_growth_rate",
    "净利润增长率": "profit_growth_rate",
    "总资产周转率": "asset_turnover",
    "存货周转率": "inventory_turnover",
    "应收账款周转率": "receivables_turnover",
}

TABLE_FIELD_MAP = {
    "balance_sheet": [
        "total_assets", "total_liabilities", "total_equity",
        "monetary_fund", "accounts_receivable", "inventory",
        "fixed_assets", "intangible_assets",
        "short_term_borrowings", "long_term_borrowings", "accounts_payable",
    ],
    "income_sheet": [
        "operating_revenue", "operating_cost", "net_profit",
        "financial_expense", "selling_expense", "administrative_expense",
        "rd_expense", "operating_profit", "total_profit",
    ],
    "stock_income_statement_data": [
        "basic_eps", "diluted_eps",
        "net_profit_excluding_non_recurring", "basic_eps_excluding_non_recurring",
    ],
    "core_performance_indicators_sheet": [
        "gross_margin", "net_margin", "weighted_roe",
        "revenue_growth_rate", "profit_growth_rate",
        "asset_turnover", "inventory_turnover", "receivables_turnover",
        "debt_asset_ratio", "current_ratio", "quick_ratio",
    ],
}


# ── PDFExtractor 主类 ────────────────────────────────────────────────────────

class PDFExtractor:
    """
    统一提取接口

    用法:
        ext = PDFExtractor("600080_2022年年报.pdf")
        result = ext.extract()               # 直接返回
        ext.extract_to_mysql()               # 写入MySQL
    """

    def __init__(self, pdf_path: str, engine: str = "A"):
        self.pdf_path = pdf_path
        self.engine_type = engine  # "A" | "B"
        self.stock_code = self._extract_stock_code()
        self.results = []

    def _extract_stock_code(self) -> str:
        fname = os.path.basename(self.pdf_path)
        m = re.search(r"(\d{6})", fname)
        return m.group(1) if m else ""

    def extract(self) -> List[Dict]:
        """执行提取（Engine A 规则 + Engine B 兜底）"""
        # Engine A
        try:
            engine_a = PDFExtractorEngineA(self.pdf_path)
            tables = engine_a.run()
            self.results = self._normalize_results(tables)
        except Exception as e:
            print(f"[WARN] Engine A failed for {self.pdf_path}: {e}")
            self.results = []

        # 如果 Engine A 结果为空，尝试 Engine B
        if not self.results:
            self._try_engine_b()

        return self.results

    def _try_engine_b(self):
        """Engine B 兜底（需要 API key）"""
        try:
            engine_b = PDFExtractorEngineB(self.pdf_path)
            raw = engine_b.run()
            if raw.get("success"):
                # 解析 SQL 或直接存储原始回答
                self.results = [{
                    "stock_code": self.stock_code,
                    "source": "engine_b",
                    "raw": raw.get("answer", ""),
                }]
        except Exception as e:
            print(f"[WARN] Engine B failed for {self.pdf_path}: {e}")

    def _normalize_results(self, tables: List[Dict]) -> List[Dict]:
        """将提取结果标准化"""
        records = []
        for tbl in tables:
            for row in tbl.get("rows", []):
                label = row.get("label", "")
                col = FIELD_MAP.get(label)
                if not col:
                    continue
                records.append({
                    "stock_code": tbl.get("stock_code", self.stock_code),
                    "table_type": tbl.get("type"),
                    "year": row.get("year"),
                    "field_cn": label,
                    "field_en": col,
                    "value": row.get("value"),
                    "page_no": tbl.get("page_no"),
                    "source": "engine_a",
                })
        return records

    def extract_to_mysql(self) -> int:
        """提取并写入 MySQL，返回写入记录数"""
        if not self.results:
            self.extract()
        if not self.results:
            return 0

        pymysql = _init_mysql()
        if pymysql is None:
            print("[ERROR] pymysql not installed")
            return 0

        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        written = 0

        for rec in self.results:
            table = rec.get("table_type", "income_sheet")
            field = rec.get("field_en")
            if not field or field not in TABLE_FIELD_MAP.get(table, []):
                continue

            # report_date 格式
            year = rec.get("year")
            report_date = f"{year}-12-31" if year else None
            if not report_date:
                continue

            sql = f"""
                INSERT INTO {table} (stock_code, report_date, {field}, created_at)
                VALUES (%s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE {field} = VALUES({field}), updated_at = NOW()
            """
            try:
                cursor.execute(sql, (
                    rec.get("stock_code", self.stock_code),
                    report_date,
                    rec.get("value"),
                ))
                written += 1
            except Exception as e:
                print(f"[WARN] MySQL insert failed: {e}")

        conn.commit()
        cursor.close()
        conn.close()
        return written


# ── 批量提取 ────────────────────────────────────────────────────────────────

def _worker(args):
    """单进程 worker"""
    pdf_path, = args
    try:
        ext = PDFExtractor(pdf_path)
        results = ext.extract()
        n_written = ext.extract_to_mysql()
        return pdf_path, True, len(results), n_written, None
    except Exception as e:
        return pdf_path, False, 0, 0, str(e)


def run_batch(pdf_dir: str, n_workers: int = 8,
              extensions: Tuple[str, ...] = (".pdf",)) -> Dict:
    """
    批量提取目录下所有 PDF

    返回: {total, success, failed, results}
    """
    # 扫描 PDF 文件
    pdf_files = []
    for root, _, files in os.walk(pdf_dir):
        for f in files:
            if f.lower().endswith(extensions):
                pdf_files.append(os.path.join(root, f))

    if not pdf_files:
        return {"total": 0, "success": 0, "failed": 0, "results": []}

    print(f"[Batch] Found {len(pdf_files)} PDFs, using {n_workers} workers")
    t0 = time.time()

    with mp.Pool(n_workers) as pool:
        outcomes = pool.map(_worker, [(p,) for p in pdf_files])

    results = []
    success = failed = 0
    for path, ok, n_results, n_written, err in outcomes:
        if ok:
            success += 1
        else:
            failed += 1
        results.append({
            "path": path, "ok": ok,
            "n_results": n_results, "n_written": n_written,
            "error": err,
        })

    elapsed = time.time() - t0
    print(f"[Batch] Done in {elapsed:.1f}s | {success} ok / {failed} failed / {len(pdf_files)} total")

    return {
        "total": len(pdf_files),
        "success": success,
        "failed": failed,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python pdf_extractor.py <pdf_path_or_dir>")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.isdir(target):
        result = run_batch(target, n_workers=8)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        ext = PDFExtractor(target)
        results = ext.extract()
        print(f"Found {len(results)} records:")
        for r in results:
            print(f"  {r}")
