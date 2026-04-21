# -*- coding: utf-8 -*-
"""
字段映射器：自然语言财务问题 → SQL 查询
支持 4 张表：
  1. balance_sheet（资产负债表）
  2. income_sheet（利润表）
  3. stock_income_statement_data（股票利润表/每股收益）
  4. core_performance_indicators_sheet（核心财务指标）

用法：
  mapper = FieldMapper()
  sql, params = mapper.map("金花股份2022年的总资产是多少")
"""
import json, os, re
from typing import Optional

BASE = os.path.dirname(os.path.abspath(__file__))


class FieldMapper:
    """中文财务问题 → SQL 字段映射"""

    def __init__(self):
        self.dict_path = os.path.join(BASE, "config", "financial_dictionary.json")
        self.alias_path = os.path.join(BASE, "data", "company_alias.json")
        self.subject_path = os.path.join(BASE, "data", "subject_synonym.json")
        self.time_path = os.path.join(BASE, "data", "time_dict.json")
        self._dict = self._load_json(self.dict_path, {})
        self._field_to_table = self._build_field_table_map()
        self._subject_dict = self._load_json(self.subject_path, {})
        self._company_alias = self._load_json(self.alias_path, {})
        self._time_dict = self._load_json(self.time_path, {})

    def _load_json(self, path, default=None):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default if default is not None else {}

    def _build_field_table_map(self):
        return {
            # balance_sheet
            "total_assets": "balance_sheet", "total_liabilities": "balance_sheet",
            "total_equity": "balance_sheet", "monetary_fund": "balance_sheet",
            "accounts_receivable": "balance_sheet", "inventory": "balance_sheet",
            "fixed_assets": "balance_sheet", "intangible_assets": "balance_sheet",
            "short_term_borrowings": "balance_sheet", "long_term_borrowings": "balance_sheet",
            "accounts_payable": "balance_sheet",
            # income_sheet
            "operating_revenue": "income_sheet", "operating_cost": "income_sheet",
            "net_profit": "income_sheet", "financial_expense": "income_sheet",
            "selling_expense": "income_sheet", "administrative_expense": "income_sheet",
            "rd_expense": "income_sheet", "operating_profit": "income_sheet",
            "total_profit": "income_sheet", "investment_income": "income_sheet",
            "non_operating_income": "income_sheet", "non_operating_expense": "income_sheet",
            "income_tax_expense": "income_sheet",
            # stock_income_statement_data
            "basic_eps": "stock_income_statement_data", "diluted_eps": "stock_income_statement_data",
            "net_profit_excluding_non_recurring": "stock_income_statement_data",
            "basic_eps_excluding_non_recurring": "stock_income_statement_data",
            # core_performance_indicators_sheet
            "gross_margin": "core_performance_indicators_sheet",
            "net_margin": "core_performance_indicators_sheet",
            "weighted_roe": "core_performance_indicators_sheet",
            "revenue_growth_rate": "core_performance_indicators_sheet",
            "profit_growth_rate": "core_performance_indicators_sheet",
            "asset_turnover": "core_performance_indicators_sheet",
            "inventory_turnover": "core_performance_indicators_sheet",
            "receivables_turnover": "core_performance_indicators_sheet",
            "debt_asset_ratio": "core_performance_indicators_sheet",
            "current_ratio": "core_performance_indicators_sheet",
            "quick_ratio": "core_performance_indicators_sheet",
            "operating_profit_margin": "core_performance_indicators_sheet",
            "operating_cash_flow_per_share": "core_performance_indicators_sheet",
        }

    def normalize(self, text: str) -> str:
        text = text.strip()
        for term, std in self._dict.items():
            if term in text:
                text = text.replace(term, std)
        for alias, std in self._subject_dict.items():
            if alias in text:
                text = text.replace(alias, std)
        return text

    def extract_company(self, text: str) -> Optional[str]:
        """从问句中提取公司代码或名称"""
        for alias, name in self._company_alias.items():
            if alias in text:
                return alias
        # 6位数字代码，避免 \b 在字符串开头失效
        m = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
        if m:
            return m.group(1)
        return None

    def extract_year(self, text: str) -> Optional[str]:
        """从问句中提取年份"""
        m = re.search(r"(20[2-3]\d)", text)
        return m.group(1) if m else None

    def map(self, question: str, intent=None):
        norm = self.normalize(question)
        stock_code = self.extract_company(question)
        year = self.extract_year(question)
        params = {}
        if stock_code:
            params["stock_code"] = stock_code
        if year:
            params["year"] = year
        field = self._detect_field(norm, intent)
        if not field:
            return self._fallback_sql(intent, params)
        table = self._field_to_table.get(field, "income_sheet")
        if intent and intent != "multi_table_query":
            table = self._intent_to_table(intent)
        sql = self._build_select_sql(table, field, params)
        return sql, params

    def _detect_field(self, norm, intent=None):
        for term, field in self._dict.items():
            if term in norm:
                return field
        keywords_map = {
            "总资产": "total_assets", "资产总计": "total_assets",
            "净利润": "net_profit", "营业收入": "operating_revenue", "营收": "operating_revenue",
            "货币资金": "monetary_fund", "现金": "monetary_fund",
            "应收账款": "accounts_receivable", "存货": "inventory",
            "基本每股收益": "basic_eps", "每股收益": "basic_eps",
            "稀释每股收益": "diluted_eps", "毛利率": "gross_margin",
            "净利率": "net_margin", "加权平均净资产收益率": "weighted_roe", "ROE": "weighted_roe",
            "资产负债率": "debt_asset_ratio", "流动比率": "current_ratio",
            "速动比率": "quick_ratio", "总资产周转率": "asset_turnover",
            "存货周转率": "inventory_turnover", "应收账款周转率": "receivables_turnover",
            "营业收入增长率": "revenue_growth_rate", "净利润增长率": "profit_growth_rate",
            "扣非": "net_profit_excluding_non_recurring", "财务费用": "financial_expense",
            "销售费用": "selling_expense", "管理费用": "administrative_expense",
            "研发费用": "rd_expense",
        }
        for kw, field in keywords_map.items():
            if kw in norm:
                return field
        return None

    def _intent_to_table(self, intent):
        return {
            "balance_sheet": "balance_sheet",
            "income_sheet": "income_sheet",
            "stock_income_statement_data": "stock_income_statement_data",
            "core_performance_indicators": "core_performance_indicators_sheet",
        }.get(intent, "income_sheet")

    def _build_select_sql(self, table, field, params):
        conditions = []
        if "stock_code" in params:
            conditions.append("stock_code = {stock_code}")
        if "year" in params:
            conditions.append("report_date LIKE {year}%")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        return f"SELECT stock_code, report_date, {field} FROM {table}{where} ORDER BY report_date DESC LIMIT 1"

    def _fallback_sql(self, intent, params):
        table = self._intent_to_table(intent) if intent else "income_sheet"
        return self._build_select_sql(table, "*", params)


_mapper_instance = None

def get_mapper() -> "FieldMapper":
    global _mapper_instance
    if _mapper_instance is None:
        _mapper_instance = FieldMapper()
    return _mapper_instance


if __name__ == "__main__":
    m = FieldMapper()
    test_qs = [
        "金花股份2022年的总资产是多少？",
        "600080的净利润？",
        "乐普医疗毛利率？",
        "格力电器基本每股收益？",
        "万邦德2023年营业收入增长率？",
    ]
    for q in test_qs:
        sql, params = m.map(q)
        print(f"Q: {q}")
        print(f"  SQL: {sql}")
        print(f"  Params: {params}\n")
