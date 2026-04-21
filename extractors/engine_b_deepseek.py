# -*- coding: utf-8 -*-
"""
引擎B：SiliconFlow (DeepSeek V3) API 兜底提取
当 Engine A（规则引擎）提取失败时，用 LLM 直接从 PDF 文本生成 SQL/数据
"""
import os, json, re
from typing import Dict

# ── 加载 .env 配置 ──────────────────────────────────────────────
try:
    from config_loader import get as _get_env
except ImportError:
    import os
    _get_env = lambda k, d="": os.environ.get(k, d)

SILICONFLOW_API_KEY = _get_env("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = _get_env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3"

# ── 提示词模板 ─────────────────────────────────────────────────

SQL_GENERATE_PROMPT = """你是一个专业的财务分析师。请根据以下信息生成SQL查询。

【数据库表结构】
- balance_sheet（资产负债表）: stock_code, report_date, total_assets, total_liabilities, total_equity, monetary_fund, accounts_receivable, inventory, fixed_assets, intangible_assets, short_term_borrowings, long_term_borrowings, accounts_payable, other_current_assets, fixed_assets_net, construction_in_progress
- income_sheet（利润表）: stock_code, report_date, operating_revenue, operating_cost, net_profit, financial_expense, selling_expense, administrative_expense, rd_expense, operating_profit, total_profit, investment_income, non_operating_income, non_operating_expense, income_tax_expense
- stock_income_statement_data（股票利润表）: stock_code, report_date, basic_eps, diluted_eps, net_profit_excluding_non_recurring, basic_eps_excluding_non_recurring
- core_performance_indicators_sheet（核心指标）: stock_code, report_date, gross_margin, net_margin, weighted_roe, revenue_growth_rate, profit_growth_rate, asset_turnover, inventory_turnover, receivables_turnover, debt_asset_ratio, current_ratio, quick_ratio

【用户问题】
{question}

请只输出SQL语句，不要解释。格式：
```sql
SELECT ... FROM ... WHERE stock_code = '{stock_code}' AND report_date LIKE '%%{year}%%' ...
```
"""


def call_siliconflow(question: str, stock_code: str = "", year: str = "") -> str:
    """调用 SiliconFlow API 生成 SQL"""
    if not SILICONFLOW_API_KEY:
        return ""

    prompt = SQL_GENERATE_PROMPT.format(
        question=question + (f"\n股票代码: {stock_code}" if stock_code else "")
    )

    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 512,
    }

    import urllib.request
    import urllib.error

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            f"{SILICONFLOW_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"<!-- API error: {e} -->"


def extract_with_llm(question: str, pdf_text: str = "",
                    stock_code: str = "", year: str = "") -> Dict:
    """
    用 LLM 从问句+PDF文本提取财务数据
    返回: {"sql": "...", "answer": "...", "success": bool}
    """
    raw = call_siliconflow(
        question=question,
        stock_code=stock_code,
        year=year,
    )
    if raw and not raw.startswith("<!--"):
        return {"sql": raw, "answer": raw, "success": True}

    return {"sql": "", "answer": "", "success": False}


class PDFExtractorEngineB:
    """
    LLM 兜底引擎（Engine B）
    使用 SiliconFlow 托管的 DeepSeek-V3
    """

    def __init__(self, pdf_path: str, question: str = ""):
        self.pdf_path = pdf_path
        self.question = question
        self.stock_code = self._extract_stock_code()

    def _extract_stock_code(self) -> str:
        fname = os.path.basename(self.pdf_path)
        m = re.search(r"(\d{6})", fname)
        return m.group(1) if m else ""

    def run(self) -> Dict:
        """执行 LLM 提取"""
        return extract_with_llm(
            question=self.question,
            stock_code=self.stock_code,
        )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python engine_b_deepseek.py <pdf_path> <question>")
        sys.exit(1)

    path = sys.argv[1]
    question = sys.argv[2]
    engine = PDFExtractorEngineB(path, question)
    result = engine.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
