# -*- coding: utf-8 -*-
"""
字段匹配器：根据问句意图，匹配目标数据库表和字段
支持：
  - 单表字段匹配
  - 多表联合查询（通过 stock_code + report_date JOIN）
  - 同比/环比分析
"""
import re, os, json
from typing import Optional, Dict, List, Tuple

# 相对导入（兼容根目录和 extractors/ 子目录两种运行方式）
try:
    from extractors.table_mapper import FieldMapper, get_mapper
except ImportError:
    from table_mapper import FieldMapper, get_mapper


class FieldMatcher:
    """
    自然语言财务问题 → 数据库表/字段匹配

    问句类型:
      - 单字段查询（"金花股份的总资产"）
      - 多字段查询（"金花股份的资产和利润"）
      - 同比/环比分析（"2022年比2021年增长多少"）
      - 财务指标计算（"毛利率"、"ROE"等）
    """

    # 同义标签（用于归一化）
    FIELD_ALIASES = {
        "营业收入": "operating_revenue", "营收": "operating_revenue",
        "净利润": "net_profit", "归母净利润": "net_profit",
        "资产总计": "total_assets", "总资产": "total_assets",
        "货币资金": "monetary_fund", "现金": "monetary_fund",
        "基本每股收益": "basic_eps", "每股收益": "basic_eps",
        "毛利率": "gross_margin", "净利率": "net_margin",
        "加权平均净资产收益率": "weighted_roe", "ROE": "weighted_roe",
    }

    # 表类型对应字段
    TABLE_FIELDS = {
        "balance_sheet": [
            "total_assets", "total_liabilities", "total_equity",
            "monetary_fund", "accounts_receivable", "inventory",
            "fixed_assets", "intangible_assets",
            "short_term_borrowings", "long_term_borrowings",
            "accounts_payable", "other_current_assets",
        ],
        "income_sheet": [
            "operating_revenue", "operating_cost", "net_profit",
            "financial_expense", "selling_expense", "administrative_expense",
            "rd_expense", "operating_profit", "total_profit",
            "investment_income", "non_operating_income",
            "non_operating_expense", "income_tax_expense",
        ],
        "stock_income_statement_data": [
            "basic_eps", "diluted_eps",
            "net_profit_excluding_non_recurring",
            "basic_eps_excluding_non_recurring",
        ],
        "core_performance_indicators_sheet": [
            "gross_margin", "net_margin", "weighted_roe",
            "revenue_growth_rate", "profit_growth_rate",
            "asset_turnover", "inventory_turnover",
            "receivables_turnover", "debt_asset_ratio",
            "current_ratio", "quick_ratio",
            "operating_cash_flow_per_share",
        ],
    }

    def __init__(self):
        self.mapper = get_mapper()

    def match(self, question: str, intent: Optional[str] = None) -> Dict:
        """
        匹配问句，返回匹配结果

        返回格式:
          {
            "stock_code": "600080",
            "years": ["2022", "2021"],
            "tables": [{"name": "balance_sheet", "fields": ["total_assets"]}],
            "analysis_type": "single" | "comparative" | "ratio",
            "sql_fragments": [...],
          }
        """
        # 1. 提取公司代码
        stock_code = self._extract_stock_code(question)
        # 2. 提取年份
        years = self._extract_years(question)
        # 3. 识别分析类型
        analysis_type = self._detect_analysis_type(question)
        # 4. 识别字段
        fields = self._extract_fields(question, intent)
        # 5. 确定目标表
        tables = self._resolve_tables(fields, intent)

        return {
            "stock_code": stock_code,
            "years": years,
            "analysis_type": analysis_type,
            "tables": tables,
            "fields": fields,
            "question": question,
        }

    def _extract_stock_code(self, q: str) -> Optional[str]:
        m = re.search(r"(?<!\d)(6\d{5}|0\d{5}|2\d{5}|3\d{5})(?!\d)", q)
        return m.group(1) if m else None

    def _extract_years(self, q: str) -> List[str]:
        years = []
        for m in re.finditer(r"(20[12]\d)", q):
            y = m.group(1)
            if y not in years:
                years.append(y)
        return years

    def _detect_analysis_type(self, q: str) -> str:
        q_lower = q.lower()
        if any(kw in q_lower for kw in ["比", "同比", "增长", "下降", "变化", "增减", "vs", "versus"]):
            return "comparative"
        if any(kw in q_lower for kw in ["毛利率", "净利率", "roa", "roe", "周转率", "比率"]):
            return "ratio"
        return "single"

    def _extract_fields(self, q: str, intent: Optional[str]) -> List[str]:
        """从问句中提取财务字段"""
        fields = []
        for alias, field in self.FIELD_ALIASES.items():
            if alias in q:
                if field not in fields:
                    fields.append(field)
        # 如果没找到，降级用 mapper
        if not fields:
            sql, params = self.mapper.map(q, intent)
            # 从 SQL 提取字段名
            m = re.search(r"SELECT\s+.*?\s+FROM", sql, re.IGNORECASE)
            if m:
                col_part = m.group()
                for t, flds in self.TABLE_FIELDS.items():
                    for f in flds:
                        if f in col_part.lower():
                            if f not in fields:
                                fields.append(f)
        return fields

    def _resolve_tables(self, fields: List[str], intent: Optional[str]) -> List[Dict]:
        """根据字段确定目标表"""
        if intent and intent not in ("multi_table_query", "comparative_analysis", "financial_ratio"):
            table_name = {
                "balance_sheet": "balance_sheet",
                "income_sheet": "income_sheet",
                "stock_income_statement_data": "stock_income_statement_data",
                "core_performance_indicators": "core_performance_indicators_sheet",
            }.get(intent, "income_sheet")
            return [{"name": table_name, "fields": fields}]

        # 根据字段自动推断
        table_fields: Dict[str, List[str]] = {}
        for f in fields:
            for tbl, flds in self.TABLE_FIELDS.items():
                if f in flds:
                    if tbl not in table_fields:
                        table_fields[tbl] = []
                    if f not in table_fields[tbl]:
                        table_fields[tbl].append(f)

        return [{"name": k, "fields": v} for k, v in table_fields.items()]

    def build_sql(self, match_result: Dict) -> List[str]:
        """根据匹配结果构建 SQL"""
        stock_code = match_result.get("stock_code", "")
        years = match_result.get("years", [])
        tables = match_result.get("tables", [])
        analysis_type = match_result.get("analysis_type", "single")

        queries = []
        for tbl in tables:
            tbl_name = tbl["name"]
            flds = tbl["fields"]

            for field in flds:
                if analysis_type == "comparative" and len(years) >= 2:
                    # 同比查询
                    for year in years:
                        sql = f"""
    SELECT stock_code, report_date, {field}
      FROM {tbl_name}
     WHERE stock_code = '{stock_code}'
       AND report_date LIKE '{year}%'
    ORDER BY report_date DESC LIMIT 1
                        """.strip()
                        queries.append(sql)
                else:
                    year = years[0] if years else "%"
                    sql = f"""
    SELECT stock_code, report_date, {field}
      FROM {tbl_name}
     WHERE stock_code = '{stock_code}'
       AND report_date LIKE '{year}%'
    ORDER BY report_date DESC LIMIT 1
                    """.strip()
                    queries.append(sql)

        return queries


def main():
    matcher = FieldMatcher()
    tests = [
        "金花股份2022年的总资产是多少？",
        "600080的净利润和营业收入？",
        "万邦德2022年比2021年的收入增长？",
        "乐普医疗毛利率？",
        "格力电器基本每股收益？",
    ]
    for q in tests:
        r = matcher.match(q)
        print(f"Q: {q}")
        print(f"  Stock: {r['stock_code']}, Years: {r['years']}, Type: {r['analysis_type']}")
        print(f"  Tables: {r['tables']}")
        print()


if __name__ == "__main__":
    main()
