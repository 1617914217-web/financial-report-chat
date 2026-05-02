# -*- coding: utf-8 -*-
"""
NL2SQL 生成模块

Prompt工程 + DeepSeek-V3 Few-Shot，生成标准SQL查询。
安全校验：调用 sql_validator 拦截危险操作。
"""
import os, re, json
from typing import Dict, List, Optional

# 数据库schema（从实际表结构整理）
SCHEMA = """
表名: balance_sheet (资产负债表)
字段:
  stock_code VARCHAR(20) -- 股票代码
  stock_abbr VARCHAR(50) -- 公司简称
  asset_cash_and_cash_equivalents DECIMAL(20,2) -- 货币资金
  asset_accounts_receivable DECIMAL(20,2) -- 应收账款
  asset_inventory DECIMAL(20,2) -- 存货
  asset_trading_financial_assets DECIMAL(20,2) -- 交易性金融资产
  asset_construction_in_progress DECIMAL(20,2) -- 在建工程
  asset_total_assets DECIMAL(20,2) -- 资产总计
  asset_total_assets_yoy_growth DECIMAL(10,4) -- 总资产同比增长率
  liability_accounts_payable DECIMAL(20,2) -- 应付账款
  liability_advance_from_customers DECIMAL(20,2) -- 预收款项
  liability_total_liabilities DECIMAL(20,2) -- 负债合计
  liability_total_liabilities_yoy_growth DECIMAL(10,4) -- 总负债同比增长率
  liability_contract_liabilities DECIMAL(20,2) -- 合同负债
  liability_short_term_loans DECIMAL(20,2) -- 短期借款
  asset_liability_ratio DECIMAL(10,4) -- 资产负债率
  equity_unappropriated_profit DECIMAL(20,2) -- 未分配利润
  equity_total_equity DECIMAL(20,2) -- 所有者权益合计
  report_period VARCHAR(20) -- 报告期，格式: '2022-12-31'表示年报，'2022-06-30'表示半年报
  report_year INT -- 报告年份

表名: income_sheet (现金流量表)
字段:
  stock_code VARCHAR(20)
  stock_abbr VARCHAR(50)
  net_cash_flow DECIMAL(20,2) -- 现金净增加额
  net_cash_flow_yoy_growth DECIMAL(10,4) -- 现金净增加额同比
  operating_cf_net_amount DECIMAL(20,2) -- 经营活动现金流量净额
  operating_cf_ratio_of_net_cf DECIMAL(10,4) -- 经营现金流占比
  operating_cf_cash_from_sales DECIMAL(20,2) -- 销售商品收到的现金
  investing_cf_net_amount DECIMAL(20,2) -- 投资活动现金流量净额
  investing_cf_ratio_of_net_cf DECIMAL(10,4) -- 投资现金流占比
  investing_cf_cash_for_investments DECIMAL(20,2) -- 购建固定资产支付的现金
  investing_cf_cash_from_investment_recovery DECIMAL(20,2) -- 收回投资收到的现金
  financing_cf_cash_from_borrowing DECIMAL(20,2) -- 取得借款收到的现金
  financing_cf_cash_for_debt_repayment DECIMAL(20,2) -- 偿还债务支付的现金
  financing_cf_net_amount DECIMAL(20,2) -- 筹资活动现金流量净额
  financing_cf_ratio_of_net_cf DECIMAL(10,4) -- 筹资现金流占比
  report_period VARCHAR(20)
  report_year INT

表名: stock_income_statement_data (利润表)
字段:
  stock_code VARCHAR(20)
  stock_abbr VARCHAR(50)
  net_profit DECIMAL(20,2) -- 净利润
  net_profit_yoy_growth DECIMAL(10,4) -- 净利润同比增长率
  other_income DECIMAL(20,2) -- 其他收益
  total_operating_revenue DECIMAL(20,2) -- 营业总收入
  operating_revenue_yoy_growth DECIMAL(10,4) -- 营业收入同比增长率
  operating_expense_cost_of_sales DECIMAL(20,2) -- 营业成本
  operating_expense_selling_expenses DECIMAL(20,2) -- 销售费用
  operating_expense_administrative_expenses DECIMAL(20,2) -- 管理费用
  operating_expense_financial_expenses DECIMAL(20,2) -- 财务费用
  operating_expense_rnd_expenses DECIMAL(20,2) -- 研发费用
  operating_expense_taxes_and_surcharges DECIMAL(20,2) -- 税金及附加
  total_operating_expenses DECIMAL(20,2) -- 营业总成本
  operating_profit DECIMAL(20,2) -- 营业利润
  total_profit DECIMAL(20,2) -- 利润总额
  asset_impairment_loss DECIMAL(20,2) -- 资产减值损失
  credit_impairment_loss DECIMAL(20,2) -- 信用减值损失
  report_period VARCHAR(20)
  report_year INT

表名: core_performance_indicators_sheet (核心财务指标)
字段:
  stock_code VARCHAR(20)
  stock_abbr VARCHAR(50)
  eps DECIMAL(10,4) -- 每股收益
  total_operating_revenue DECIMAL(20,2) -- 营业总收入
  operating_revenue_yoy_growth DECIMAL(10,4) -- 营收同比增长率
  operating_revenue_qoq_growth DECIMAL(10,4) -- 营收环比增长率
  net_profit_10k_yuan DECIMAL(20,2) -- 净利润(万元)
  net_profit_yoy_growth DECIMAL(10,4) -- 净利润同比增长率
  net_profit_qoq_growth DECIMAL(10,4) -- 净利润环比增长率
  net_asset_per_share DECIMAL(10,4) -- 每股净资产
  roe DECIMAL(10,4) -- 净资产收益率
  operating_cf_per_share DECIMAL(10,4) -- 每股经营现金流
  net_profit_excl_non_recurring DECIMAL(20,2) -- 扣非净利润
  net_profit_excl_non_recurring_yoy DECIMAL(10,4) -- 扣非净利润同比增长率
  gross_profit_margin DECIMAL(10,4) -- 毛利率
  net_profit_margin DECIMAL(10,4) -- 净利率
  roe_weighted_excl_non_recurring DECIMAL(10,4) -- 扣非加权ROE
  report_period VARCHAR(20)
  report_year INT
"""

FEW_SHOT_EXAMPLES = """
示例1:
用户问题：金花股份2022年净利润是多少？
分析：查询单值，公司=金花股份(代码600080)，年份=2022，科目=净利润，表=stock_income_statement_data
SQL: SELECT net_profit FROM stock_income_statement_data WHERE stock_code='600080' AND report_period='2022-12-31';

示例2:
用户问题：2022年利润最高的3家公司？
分析：排序查询，年份=2022，科目=净利润，表=stock_income_statement_data，取前3
SQL: SELECT stock_code, stock_abbr, net_profit FROM stock_income_statement_data WHERE report_period='2022-12-31' ORDER BY net_profit DESC LIMIT 3;

示例3:
用户问题：万邦德2022年毛利率和净利率分别是多少？
分析：多值查询，公司=万邦德(代码002082)，年份=2022，科目=毛利率+净利率，表=core_performance_indicators_sheet
SQL: SELECT stock_code, stock_abbr, gross_profit_margin, net_profit_margin FROM core_performance_indicators_sheet WHERE stock_code='002082' AND report_period='2022-12-31';

示例4:
用户问题：金花股份和万邦德2022年总资产对比
分析：比较查询，公司=金花股份(600080)+万邦德(002082)，年份=2022，科目=总资产，表=balance_sheet
SQL: SELECT stock_code, stock_abbr, asset_total_assets FROM balance_sheet WHERE stock_code IN ('600080','002082') AND report_period='2022-12-31';

示例5:
用户问题：2022年ROE最高的5家公司
分析：排序查询，年份=2022，科目=ROE，表=core_performance_indicators_sheet，取前5
SQL: SELECT stock_code, stock_abbr, roe FROM core_performance_indicators_sheet WHERE report_period='2022-12-31' ORDER BY roe DESC LIMIT 5;

示例6:
用户问题：金花股份2022年经营活动现金流量净额
分析：单值查询，公司=金花股份(600080)，年份=2022，科目=经营活动现金流量净额，表=income_sheet
SQL: SELECT stock_code, stock_abbr, operating_cf_net_amount FROM income_sheet WHERE stock_code='600080' AND report_period='2022-12-31';
"""


class NL2SQLGenerator:
    """NL2SQL生成器"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        # 从.env加载
        try:
            from config_loader import load_env
            env = load_env()
            self.api_key = api_key or env.get("SILICONFLOW_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
            self.base_url = base_url or env.get("SILICONFLOW_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        except Exception:
            self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
            self.base_url = base_url or os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = model or "deepseek-ai/DeepSeek-V3"
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            self.client = None

    def generate(self, question: str, intent: str = None) -> dict:
        """
        生成SQL
        返回: {"sql": str, "table": str, "reasoning": str, "error": str}
        """
        if not self.client:
            return {"sql": "", "table": "", "reasoning": "", "error": "openai模块未安装"}

        prompt = self._build_prompt(question, intent)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个SQL专家，只输出SQL代码，不要解释。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=512,
            )
            raw = resp.choices[0].message.content.strip()
            sql = self._extract_sql(raw)

            # 安全校验
            from sql_validator import SQLValidator
            v = SQLValidator.validate(sql)
            if not v["valid"]:
                return {"sql": "", "table": "", "reasoning": "", "error": f"SQL校验失败: {v['reason']}"}

            table = self._infer_table(sql)
            return {"sql": sql, "table": table, "reasoning": raw, "error": ""}

        except Exception as e:
            return {"sql": "", "table": "", "reasoning": "", "error": str(e)}

    def _build_prompt(self, question: str, intent: str = None) -> str:
        intent_hint = f"\n意图: {intent}\n" if intent else ""
        return f"""你是一个SQL专家。请根据用户问题生成MySQL查询SQL。

数据库Schema:
{SCHEMA}

{FEW_SHOT_EXAMPLES}

{intent_hint}
用户问题：{question}
SQL:"""

    def _extract_sql(self, text: str) -> str:
        """从LLM输出中提取SQL代码"""
        # 去掉markdown代码块
        text = re.sub(r'```sql\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        # 去掉"SQL:"前缀
        text = re.sub(r'^\s*SQL:\s*', '', text, flags=re.IGNORECASE)
        # 清理换行，合并为单行
        text = text.replace('\n', ' ').strip()
        # 提取SELECT...;之间的内容
        m = re.search(r'(SELECT\s+.+?);', text, re.IGNORECASE)
        if m:
            return m.group(1) + ';'
        # 如果没找到，返回整个文本
        return text.rstrip(';') + ';'

    def _infer_table(self, sql: str) -> str:
        """从SQL中推断表名"""
        tables = ['balance_sheet', 'income_sheet', 'stock_income_statement_data', 'core_performance_indicators_sheet']
        for t in tables:
            if t in sql:
                return t
        return ""


if __name__ == "__main__":
    # 测试时手动传key
    gen = NL2SQLGenerator(
        api_key="sk-jjauygujsfgzhmdftrmcpuahuuzlwqpkoymyqmdkpvkrbvlu",
        base_url="https://api.siliconflow.cn/v1"
    )
    tests = [
        "金花股份2022年净利润是多少",
        "2022年净利润最高的3家公司",
        "金花股份和万邦德2022年总资产对比",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        r = gen.generate(q)
        if r["error"]:
            print(f"  Error: {r['error']}")
        else:
            print(f"  SQL: {r['sql']}")
            print(f"  Table: {r['table']}")
