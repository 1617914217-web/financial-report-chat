# -*- coding: utf-8 -*-
"""LLM兜底引擎 - DeepSeek V3 via SiliconFlow"""
import os
import json
import re

# 加载配置
try:
    from config_loader import get
except:
    get = lambda k, d="": os.environ.get(k, d)

API_KEY = get("SILICONFLOW_API_KEY", "")
BASE_URL = get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL = "deepseek-ai/DeepSeek-V3"

# 提示词模板
PROMPT = """你是财务分析师。根据下面信息生成SQL。

【表结构】
- balance_sheet: stock_code, report_date, total_assets, total_liabilities, total_equity, monetary_fund...
- income_sheet: stock_code, report_date, operating_revenue, net_profit, financial_expense...
- stock_income_statement_data: stock_code, report_date, basic_eps, diluted_eps...
- core_performance_indicators_sheet: stock_code, report_date, gross_margin, net_margin, weighted_roe...

【问题】
{question}

只输出SQL，不解释。
"""


def ask(question, stock_code="", year=""):
    """调用API"""
    if not API_KEY:
        return ""

    prompt = PROMPT.format(question=question + (f"\n股票代码: {stock_code}" if stock_code else ""))

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 512,
    }

    import urllib.request

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"<!-- error: {e} -->"


def extract(question, pdf_text="", stock_code="", year=""):
    """提取数据"""
    raw = ask(question, stock_code, year)
    if raw and not raw.startswith("<!--"):
        return {"sql": raw, "ok": True}
    return {"sql": "", "ok": False}


class EngineB:
    """LLM引擎"""

    def __init__(self, pdf_path, question=""):
        self.pdf_path = pdf_path
        self.question = question
        self.stock_code = self._get_code()

    def _get_code(self):
        m = re.search(r"(\d{6})", os.path.basename(self.pdf_path))
        return m.group(1) if m else ""

    def run(self):
        return extract(self.question, stock_code=self.stock_code)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python engine_b_deepseek.py <pdf> <question>")
        sys.exit(1)
    engine = EngineB(sys.argv[1], sys.argv[2])
    print(json.dumps(engine.run(), ensure_ascii=False, indent=2))
