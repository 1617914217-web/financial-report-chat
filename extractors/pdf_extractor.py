# -*- coding: utf-8 -*-
"""PDF提取整合入口"""
import os
import json
import time
import re
import multiprocessing as mp

from .engine_a_rules import EngineA
from .engine_b_deepseek import EngineB

# 加载配置
try:
    from config_loader import get
except:
    import os
    get = lambda k, d="": os.environ.get(k, d)

MYSQL = {
    "host": get("MYSQL_HOST", "127.0.0.1"),
    "port": int(get("MYSQL_PORT", "3306")),
    "user": get("MYSQL_USER", "root"),
    "password": get("MYSQL_PASSWORD", ""),
    "database": get("MYSQL_DATABASE", "intelligent_data_query"),
    "charset": "utf8mb4",
}

# 中文→英文字段映射
FIELD_MAP = {
    "资产总计": "total_assets", "总资产": "total_assets",
    "负债合计": "total_liabilities", "总负债": "total_liabilities",
    "所有者权益合计": "total_equity", "净资产": "total_equity",
    "货币资金": "monetary_fund",
    "应收账款": "accounts_receivable",
    "存货": "inventory",
    "固定资产": "fixed_assets",
    "无形资产": "intangible_assets",
    "短期借款": "short_term_borrowings",
    "长期借款": "long_term_borrowings",
    "应付账款": "accounts_payable",
    "营业收入": "operating_revenue",
    "营业成本": "operating_cost",
    "净利润": "net_profit",
    "财务费用": "financial_expense",
    "销售费用": "selling_expense",
    "管理费用": "administrative_expense",
    "研发费用": "rd_expense",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "基本每股收益": "basic_eps",
    "稀释每股收益": "diluted_eps",
    "毛利率": "gross_margin",
    "净利率": "net_margin",
    "加权平均净资产收益率": "weighted_roe",
    "ROE": "weighted_roe",
    "资产负债率": "debt_asset_ratio",
    "流动比率": "current_ratio",
    "速动比率": "quick_ratio",
}


class PDFExtractor:
    """提取器"""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.stock_code = self._get_code()
        self.results = []

    def _get_code(self):
        m = re.search(r"(\d{6})", os.path.basename(self.pdf_path))
        return m.group(1) if m else ""

    def extract(self):
        """执行提取"""
        # 先用规则引擎
        try:
            engine_a = EngineA(self.pdf_path)
            tables = engine_a.run()
            self.results = self._norm(tables)
        except Exception as e:
            print(f"[A失败] {self.pdf_path}: {e}")
            self.results = []

        # 失败则用LLM
        if not self.results:
            self._try_llm()

        return self.results

    def _try_llm(self):
        try:
            engine_b = EngineB(self.pdf_path)
            raw = engine_b.run()
            if raw.get("ok"):
                self.results = [{
                    "stock_code": self.stock_code,
                    "source": "llm",
                    "raw": raw.get("sql", ""),
                }]
        except Exception as e:
            print(f"[B失败] {self.pdf_path}: {e}")

    def _norm(self, tables):
        """标准化结果"""
        records = []
        for tbl in tables:
            for row in tbl.get("rows", []):
                label = row.get("label", "")
                col = FIELD_MAP.get(label)
                if not col:
                    continue
                records.append({
                    "stock_code": tbl.get("stock_code", self.stock_code),
                    "table": tbl.get("type"),
                    "year": row.get("year"),
                    "field_cn": label,
                    "field_en": col,
                    "value": row.get("value"),
                    "page": tbl.get("page_no"),
                })
        return records

    def to_mysql(self):
        """写入MySQL"""
        if not self.results:
            self.extract()
        if not self.results:
            return 0

        try:
            import pymysql
        except:
            print("[错误] 缺pymysql")
            return 0

        conn = pymysql.connect(**MYSQL)
        cur = conn.cursor()
        n = 0

        for rec in self.results:
            table = rec.get("table", "income_sheet")
            field = rec.get("field_en")
            if not field:
                continue

            year = rec.get("year")
            if not year:
                continue
            report_date = f"{year}-12-31"

            sql = f"""
                INSERT INTO {table} (stock_code, report_date, {field})
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE {field} = VALUES({field})
            """
            try:
                cur.execute(sql, (
                    rec.get("stock_code", self.stock_code),
                    report_date,
                    rec.get("value"),
                ))
                n += 1
            except Exception as e:
                print(f"[写入失败] {e}")

        conn.commit()
        cur.close()
        conn.close()
        return n


# 批量处理
def _worker(args):
    pdf_path, = args
    try:
        ext = PDFExtractor(pdf_path)
        ext.extract()
        n = ext.to_mysql()
        return pdf_path, True, len(ext.results), n, None
    except Exception as e:
        return pdf_path, False, 0, 0, str(e)


def batch(pdf_dir, n_workers=8):
    """批量提取"""
    pdfs = []
    for root, _, files in os.walk(pdf_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))

    if not pdfs:
        return {"total": 0, "ok": 0, "fail": 0}

    print(f"[批量] 找到{len(pdfs)}个PDF，{n_workers}进程")
    t0 = time.time()

    with mp.Pool(n_workers) as pool:
        results = pool.map(_worker, [(p,) for p in pdfs])

    ok = sum(1 for r in results if r[1])
    fail = len(results) - ok
    elapsed = time.time() - t0

    print(f"[完成] {ok}成功 / {fail}失败 / 耗时{elapsed:.1f}秒")

    return {
        "total": len(pdfs),
        "ok": ok,
        "fail": fail,
        "time": round(elapsed, 1),
        "results": results,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python pdf_extractor.py <pdf或目录>")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.isdir(target):
        print(json.dumps(batch(target), ensure_ascii=False, indent=2))
    else:
        ext = PDFExtractor(target)
        r = ext.extract()
        print(f"提取{len(r)}条:")
        for x in r:
            print(f"  {x}")
