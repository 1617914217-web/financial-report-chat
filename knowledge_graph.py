# -*- coding: utf-8 -*-
"""
财务知识图谱模块

科目节点 + 关系边 + 派生指标推理

例如：问"毛利率" → 自动推导 = (营业总收入 - 营业成本) / 营业总收入
"""
from typing import Dict, List, Optional, Tuple


class FinancialKnowledgeGraph:
    """财务知识图谱"""

    # 科目节点定义：名称 -> (表名, 字段名, 描述)
    NODES = {
        # 利润表
        "营业总收入": ("stock_income_statement_data", "total_operating_revenue", "营业总收入"),
        "营业成本": ("stock_income_statement_data", "operating_expense_cost_of_sales", "营业成本"),
        "销售费用": ("stock_income_statement_data", "operating_expense_selling_expenses", "销售费用"),
        "管理费用": ("stock_income_statement_data", "operating_expense_administrative_expenses", "管理费用"),
        "财务费用": ("stock_income_statement_data", "operating_expense_financial_expenses", "财务费用"),
        "研发费用": ("stock_income_statement_data", "operating_expense_rnd_expenses", "研发费用"),
        "税金及附加": ("stock_income_statement_data", "operating_expense_taxes_and_surcharges", "税金及附加"),
        "营业利润": ("stock_income_statement_data", "operating_profit", "营业利润"),
        "利润总额": ("stock_income_statement_data", "total_profit", "利润总额"),
        "净利润": ("stock_income_statement_data", "net_profit", "净利润"),
        "其他收益": ("stock_income_statement_data", "other_income", "其他收益"),
        "资产减值损失": ("stock_income_statement_data", "asset_impairment_loss", "资产减值损失"),
        "信用减值损失": ("stock_income_statement_data", "credit_impairment_loss", "信用减值损失"),
        "营业总成本": ("stock_income_statement_data", "total_operating_expenses", "营业总成本"),
        # 资产负债表
        "货币资金": ("balance_sheet", "asset_cash_and_cash_equivalents", "货币资金"),
        "应收账款": ("balance_sheet", "asset_accounts_receivable", "应收账款"),
        "存货": ("balance_sheet", "asset_inventory", "存货"),
        "交易性金融资产": ("balance_sheet", "asset_trading_financial_assets", "交易性金融资产"),
        "在建工程": ("balance_sheet", "asset_construction_in_progress", "在建工程"),
        "资产总计": ("balance_sheet", "asset_total_assets", "资产总计"),
        "总资产同比增长率": ("balance_sheet", "asset_total_assets_yoy_growth", "总资产同比增长率"),
        "应付账款": ("balance_sheet", "liability_accounts_payable", "应付账款"),
        "预收款项": ("balance_sheet", "liability_advance_from_customers", "预收款项"),
        "负债合计": ("balance_sheet", "liability_total_liabilities", "负债合计"),
        "总负债同比增长率": ("balance_sheet", "liability_total_liabilities_yoy_growth", "总负债同比增长率"),
        "合同负债": ("balance_sheet", "liability_contract_liabilities", "合同负债"),
        "短期借款": ("balance_sheet", "liability_short_term_loans", "短期借款"),
        "资产负债率": ("balance_sheet", "asset_liability_ratio", "资产负债率"),
        "未分配利润": ("balance_sheet", "equity_unappropriated_profit", "未分配利润"),
        "所有者权益合计": ("balance_sheet", "equity_total_equity", "所有者权益合计"),
        # 核心指标表
        "每股收益": ("core_performance_indicators_sheet", "eps", "每股收益"),
        "营收同比增长率": ("core_performance_indicators_sheet", "operating_revenue_yoy_growth", "营收同比增长率"),
        "营收环比增长率": ("core_performance_indicators_sheet", "operating_revenue_qoq_growth", "营收环比增长率"),
        "净利润万元": ("core_performance_indicators_sheet", "net_profit_10k_yuan", "净利润(万元)"),
        "净利润同比增长率": ("core_performance_indicators_sheet", "net_profit_yoy_growth", "净利润同比增长率"),
        "净利润环比增长率": ("core_performance_indicators_sheet", "net_profit_qoq_growth", "净利润环比增长率"),
        "每股净资产": ("core_performance_indicators_sheet", "net_asset_per_share", "每股净资产"),
        "ROE": ("core_performance_indicators_sheet", "roe", "净资产收益率"),
        "每股经营现金流": ("core_performance_indicators_sheet", "operating_cf_per_share", "每股经营现金流"),
        "扣非净利润": ("core_performance_indicators_sheet", "net_profit_excl_non_recurring", "扣非净利润"),
        "扣非净利润同比增长率": ("core_performance_indicators_sheet", "net_profit_excl_non_recurring_yoy", "扣非净利润同比增长率"),
        "毛利率": ("core_performance_indicators_sheet", "gross_profit_margin", "毛利率"),
        "净利率": ("core_performance_indicators_sheet", "net_profit_margin", "净利率"),
        "扣非加权ROE": ("core_performance_indicators_sheet", "roe_weighted_excl_non_recurring", "扣非加权ROE"),
        # 现金流量表
        "现金净增加额": ("income_sheet", "net_cash_flow", "现金净增加额"),
        "现金净增加额同比": ("income_sheet", "net_cash_flow_yoy_growth", "现金净增加额同比"),
        "经营活动现金流量净额": ("income_sheet", "operating_cf_net_amount", "经营活动现金流量净额"),
        "经营现金流占比": ("income_sheet", "operating_cf_ratio_of_net_cf", "经营现金流占比"),
        "销售商品收到的现金": ("income_sheet", "operating_cf_cash_from_sales", "销售商品收到的现金"),
        "投资活动现金流量净额": ("income_sheet", "investing_cf_net_amount", "投资活动现金流量净额"),
        "投资现金流占比": ("income_sheet", "investing_cf_ratio_of_net_cf", "投资现金流占比"),
        "购建固定资产支付的现金": ("income_sheet", "investing_cf_cash_for_investments", "购建固定资产支付的现金"),
        "收回投资收到的现金": ("income_sheet", "investing_cf_cash_from_investment_recovery", "收回投资收到的现金"),
        "取得借款收到的现金": ("income_sheet", "financing_cf_cash_from_borrowing", "取得借款收到的现金"),
        "偿还债务支付的现金": ("income_sheet", "financing_cf_cash_for_debt_repayment", "偿还债务支付的现金"),
        "筹资活动现金流量净额": ("income_sheet", "financing_cf_net_amount", "筹资活动现金流量净额"),
        "筹资现金流占比": ("income_sheet", "financing_cf_ratio_of_net_cf", "筹资现金流占比"),
    }

    # 派生指标定义：名称 -> (公式描述, 依赖字段列表, 计算函数)
    DERIVED = {
        "毛利": {
            "formula": "营业总收入 - 营业成本",
            "deps": ["total_operating_revenue", "operating_expense_cost_of_sales"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: vals.get("total_operating_revenue", 0) - vals.get("operating_expense_cost_of_sales", 0),
        },
        "毛利率_计算": {
            "formula": "(营业总收入 - 营业成本) / 营业总收入",
            "deps": ["total_operating_revenue", "operating_expense_cost_of_sales"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: (vals.get("total_operating_revenue", 0) - vals.get("operating_expense_cost_of_sales", 0)) / vals.get("total_operating_revenue", 1) if vals.get("total_operating_revenue") else None,
        },
        "净利率_计算": {
            "formula": "净利润 / 营业总收入",
            "deps": ["net_profit", "total_operating_revenue"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: vals.get("net_profit", 0) / vals.get("total_operating_revenue", 1) if vals.get("total_operating_revenue") else None,
        },
        "ROE_杜邦": {
            "formula": "净利率 * 总资产周转率 * 权益乘数",
            "deps": ["net_profit_margin", "total_operating_revenue", "asset_total_assets", "equity_total_equity"],
            "table": "multi",
            "compute": lambda vals: None,  # 需要跨表数据，暂不支持
        },
        "资产负债率_计算": {
            "formula": "负债合计 / 资产总计",
            "deps": ["liability_total_liabilities", "asset_total_assets"],
            "table": "balance_sheet",
            "compute": lambda vals: vals.get("liability_total_liabilities", 0) / vals.get("asset_total_assets", 1) if vals.get("asset_total_assets") else None,
        },
        "营业利润率": {
            "formula": "营业利润 / 营业总收入",
            "deps": ["operating_profit", "total_operating_revenue"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: vals.get("operating_profit", 0) / vals.get("total_operating_revenue", 1) if vals.get("total_operating_revenue") else None,
        },
        "三费合计": {
            "formula": "销售费用 + 管理费用 + 财务费用",
            "deps": ["operating_expense_selling_expenses", "operating_expense_administrative_expenses", "operating_expense_financial_expenses"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: sum(vals.get(k, 0) for k in ["operating_expense_selling_expenses", "operating_expense_administrative_expenses", "operating_expense_financial_expenses"]),
        },
        "三费率": {
            "formula": "三费合计 / 营业总收入",
            "deps": ["operating_expense_selling_expenses", "operating_expense_administrative_expenses", "operating_expense_financial_expenses", "total_operating_revenue"],
            "table": "stock_income_statement_data",
            "compute": lambda vals: (sum(vals.get(k, 0) for k in ["operating_expense_selling_expenses", "operating_expense_administrative_expenses", "operating_expense_financial_expenses"]) / vals.get("total_operating_revenue", 1)) if vals.get("total_operating_revenue") else None,
        },
    }

    # 关系边：科目A -> 科目B (关系类型)
    EDGES = {
        ("营业总收入", "营业成本"): "减项",
        ("营业成本", "毛利"): "等于",
        ("毛利", "销售费用"): "减项",
        ("毛利", "管理费用"): "减项",
        ("毛利", "财务费用"): "减项",
        ("毛利", "研发费用"): "减项",
        ("营业利润", "利润总额"): "等于",
        ("利润总额", "净利润"): "减项",
        ("资产总计", "负债合计"): "减项",
        ("资产总计", "所有者权益合计"): "等于",
        ("负债合计", "所有者权益合计"): "等于",
    }

    def lookup(self, term: str) -> Optional[Tuple[str, str, str]]:
        """查询科目节点"""
        return self.NODES.get(term)

    def is_derived(self, term: str) -> bool:
        """是否为派生指标"""
        return term in self.DERIVED

    def get_derived_info(self, term: str) -> Optional[dict]:
        """获取派生指标信息"""
        return self.DERIVED.get(term)

    def resolve(self, term: str) -> dict:
        """
        解析术语：返回可直接查询的信息或需要计算的信息
        返回: {"type": "direct"|"derived", "table": str, "field": str, "formula": str, "deps": list}
        """
        if term in self.NODES:
            table, field, desc = self.NODES[term]
            return {
                "type": "direct",
                "table": table,
                "field": field,
                "desc": desc,
            }
        if term in self.DERIVED:
            info = self.DERIVED[term]
            return {
                "type": "derived",
                "table": info["table"],
                "formula": info["formula"],
                "deps": info["deps"],
                "desc": info["formula"],
            }
        # 尝试同义词匹配
        synonyms = {
            "营收": "营业总收入",
            "收入": "营业总收入",
            "净利": "净利润",
            "利润": "净利润",
            "总资产": "资产总计",
            "总负债": "负债合计",
            "净资产": "所有者权益合计",
            "股东权益": "所有者权益合计",
            "EPS": "每股收益",
            "每股盈利": "每股收益",
        }
        if term in synonyms:
            return self.resolve(synonyms[term])
        return {"type": "unknown", "table": "", "field": "", "desc": f"未找到: {term}"}

    def compute_derived(self, term: str, values: dict) -> Optional[float]:
        """计算派生指标值"""
        info = self.DERIVED.get(term)
        if not info:
            return None
        try:
            return info["compute"](values)
        except Exception:
            return None

    def get_all_terms(self) -> List[str]:
        """获取所有支持的术语"""
        return list(self.NODES.keys()) + list(self.DERIVED.keys())


if __name__ == "__main__":
    kg = FinancialKnowledgeGraph()

    # 测试直接查询
    r = kg.resolve("毛利率")
    print(f"毛利率: {r}")

    # 测试派生指标
    r = kg.resolve("毛利率_计算")
    print(f"毛利率_计算: {r}")

    # 测试计算
    vals = {
        "total_operating_revenue": 1000.0,
        "operating_expense_cost_of_sales": 600.0,
    }
    result = kg.compute_derived("毛利率_计算", vals)
    print(f"计算结果: {result}")

    # 测试同义词
    r = kg.resolve("营收")
    print(f"营收: {r}")
