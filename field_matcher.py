# -*- coding: utf-8 -*-
"""
字段映射模块：从 raw_extracted 读取数据，映射后写入4张标准表

功能：
  1. 读取 raw_extracted（process_status=pending）
  2. 字段映射：中文财务术语 → 数据库英文字段
  3. 数据清洗：统一格式、转换类型
  4. 写入目标表
  5. 更新 process_status

使用：
  python field_matcher.py                    # 处理全部pending
  python field_matcher.py --limit 100       # 只处理100条
  python field_matcher.py --reprocess failed # 重新处理failed数据
"""
import json, os, argparse
from typing import Dict, List, Optional, Tuple

try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

import pymysql


# ======================== 字段映射表（已核实：只含4张表里实际存在的字段）=======================
CHINESE_TO_FIELD = {
    # === balance_sheet ===
    "货币资金": "asset_cash_and_cash_equivalents",
    "现金及现金等价物": "asset_cash_and_cash_equivalents",
    "应收账款": "asset_accounts_receivable",
    "应收款项": "asset_accounts_receivable",
    "存货": "asset_inventory",
    "交易性金融资产": "asset_trading_financial_assets",
    "在建工程": "asset_construction_in_progress",
    "资产总计": "asset_total_assets",
    "总资产": "asset_total_assets",
    "资产总计_同比增长": "asset_total_assets_yoy_growth",
    "应付账款": "liability_accounts_payable",
    "预收款项": "liability_advance_from_customers",
    "预收账款": "liability_advance_from_customers",
    "合同负债": "liability_contract_liabilities",
    "短期借款": "liability_short_term_loans",
    "负债合计": "liability_total_liabilities",
    "总负债": "liability_total_liabilities",
    "负债合计_同比增长": "liability_total_liabilities_yoy_growth",
    "所有者权益合计": "equity_total_equity",
    "股东权益合计": "equity_total_equity",
    "未分配利润": "equity_unappropriated_profit",
    "资产负债率": "asset_liability_ratio",

    # === income_sheet (现金流量) ===
    "经营活动产生的现金流量净额": "net_cash_flow",
    "经营活动现金净流量": "net_cash_flow",
    "经营活动产生的现金流量净额_同比增长": "net_cash_flow_yoy_growth",
    "经营活动现金流入小计": "operating_cf_net_amount",
    "购买商品、接受劳务支付的现金": "operating_cf_cash_from_sales",
    "经营活动现金流出小计": "operating_cf_cash_from_sales",
    "经营活动产生的现金流量净额占净利润比率": "operating_cf_ratio_of_net_cf",
    "投资活动产生的现金流量净额": "investing_cf_net_amount",
    "投资活动产生的现金流量净额占经营活动现金流量净额比率": "investing_cf_ratio_of_net_cf",
    "投资活动现金流出小计": "investing_cf_cash_for_investments",
    "投资活动现金流入小计": "investing_cf_cash_from_investment_recovery",
    "取得借款收到的现金": "financing_cf_cash_from_borrowing",
    "偿还债务支付的现金": "financing_cf_cash_for_debt_repayment",
    "筹资活动产生的现金流量净额": "financing_cf_net_amount",
    "筹资活动产生的现金流量净额占经营活动现金流量净额比率": "financing_cf_ratio_of_net_cf",

    # === stock_income_statement_data ===
    "营业收入": "total_operating_revenue",
    "主营业务收入": "total_operating_revenue",
    "营业总收入": "total_operating_revenue",
    "营业收入_同比增长": "operating_revenue_yoy_growth",
    "营业成本": "operating_expense_cost_of_sales",
    "主营业务成本": "operating_expense_cost_of_sales",
    "销售费用": "operating_expense_selling_expenses",
    "管理费用": "operating_expense_administrative_expenses",
    "财务费用": "operating_expense_financial_expenses",
    "研发费用": "operating_expense_rnd_expenses",
    "研发支出": "operating_expense_rnd_expenses",
    "税金及附加": "operating_expense_taxes_and_surcharges",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "净利润": "net_profit",
    "归属于母公司股东的净利润": "net_profit",
    "归属于上市公司股东的净利润": "net_profit",
    "净利润_同比增长": "net_profit_yoy_growth",
    "归属于上市公司股东的净利润_同比增长": "net_profit_yoy_growth",
    "营业外收入": "other_income",
    "资产减值损失": "asset_impairment_loss",
    "信用减值损失": "credit_impairment_loss",

    # === core_performance_indicators_sheet ===
    "基本每股收益": "eps",
    "每股收益": "eps",
    "稀释每股收益": "eps",
    "归属于上市公司股东的扣除非经常性损益的净利润": "net_profit_excl_non_recurring",
    "扣除非经常性损益后的净利润": "net_profit_excl_non_recurring",
    "归属于上市公司股东的扣除非经常性损益的净利润_同比增长": "net_profit_excl_non_recurring_yoy",
    "归属于上市公司股东的净资产": "net_asset_per_share",
    "归属于上市公司股东的每股净资产": "net_asset_per_share",
    "净资产收益率": "roe",
    "加权平均净资产收益率": "roe",
    "加权平均净资产收益率_扣除非经常性损益": "roe_weighted_excl_non_recurring",
    "销售毛利率": "gross_profit_margin",
    "毛利率": "gross_profit_margin",
    "销售净利率": "net_profit_margin",
    "净利率": "net_profit_margin",
    "每股经营活动产生的现金流量净额": "operating_cf_per_share",
    "归属于上市公司股东净利润_10万元": "net_profit_10k_yuan",
    "营业收入_本报告期比上年同期增减": "operating_revenue_yoy_growth",
}


# 各表的专属字段（用于根据字段内容判断目标表）
TABLE_SIGNATURE_FIELDS = {
    'balance_sheet': [
        'asset_total_assets', 'asset_cash_and_cash_equivalents', 'asset_accounts_receivable',
        'asset_inventory', 'asset_trading_financial_assets', 'asset_construction_in_progress',
        'liability_total_liabilities', 'liability_accounts_payable', 'liability_short_term_loans',
        'equity_total_equity', 'equity_unappropriated_profit', 'asset_liability_ratio',
        'liability_total_liabilities_yoy_growth', 'asset_total_assets_yoy_growth',
        'liability_contract_liabilities', 'liability_advance_from_customers',
    ],
    'stock_income_statement_data': [
        'net_profit', 'total_operating_revenue', 'operating_profit', 'total_profit',
        'operating_expense_cost_of_sales', 'operating_expense_selling_expenses',
        'operating_expense_administrative_expenses', 'operating_expense_financial_expenses',
        'operating_expense_rnd_expenses', 'operating_expense_taxes_and_surcharges',
        'net_profit_yoy_growth', 'operating_revenue_yoy_growth',
        'other_income', 'asset_impairment_loss', 'credit_impairment_loss',
    ],
    'core_performance_indicators_sheet': [
        'eps', 'roe', 'gross_profit_margin', 'net_profit_margin',
        'net_asset_per_share', 'net_profit_excl_non_recurring',
        'operating_cf_per_share', 'net_profit_qoq_growth',
        'roe_weighted_excl_non_recurring', 'net_profit_excl_non_recurring_yoy',
        'net_profit_10k_yuan',
    ],
    'income_sheet': [
        'net_cash_flow', 'net_cash_flow_yoy_growth', 'operating_cf_net_amount',
        'investing_cf_net_amount', 'financing_cf_net_amount',
        'operating_cf_cash_from_sales', 'investing_cf_cash_for_investments',
        'financing_cf_cash_from_borrowing', 'financing_cf_cash_for_debt_repayment',
        'investing_cf_ratio_of_net_cf', 'financing_cf_ratio_of_net_cf',
        'operating_cf_ratio_of_net_cf', 'investing_cf_cash_from_investment_recovery',
    ],
}


def get_db_config() -> Dict:
    return {
        'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '181415157Ak.'),
        'database': os.getenv('MYSQL_DATABASE', 'intelligent_data_query'),
        'charset': 'utf8mb4'
    }


def parse_value(val) -> Optional[float]:
    """解析数值，处理千分位、负数、百分比"""
    if val is None or val == '' or val == 'N/A' or val == '--':
        return None
    s = str(val).strip().replace('%', '').replace('％', '').replace(',', '').replace('，', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try:
        result = float(s)
        if '%' in str(val):
            result /= 100
        return result
    except (ValueError, TypeError):
        return None


def get_year_value(row_data: Dict, col: str, year: int) -> Optional[float]:
    """从 {"字段": {"2022": xxx, "2023": yyy}} 结构中取值"""
    if col not in row_data:
        return None
    year_data = row_data[col]
    if isinstance(year_data, dict):
        for k, v in year_data.items():
            if str(year) in k:
                return parse_value(v)
        for v in year_data.values():
            pv = parse_value(v)
            if pv is not None:
                return pv
    return parse_value(year_data)


class FieldMatcher:
    def __init__(self):
        self.conn = None
        self.db_config = get_db_config()

    def connect(self):
        self.conn = pymysql.connect(**self.db_config)

    def close(self):
        if self.conn:
            self.conn.close()

    def fetch_pending(self, limit: Optional[int], status: str) -> List[Dict]:
        sql = "SELECT * FROM raw_extracted WHERE process_status = %s"
        if limit:
            sql += f" LIMIT {limit}"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, (status,))
            return cur.fetchall()

    def map_field(self, chinese: str) -> Optional[str]:
        """中文 → 英文字段"""
        if chinese in CHINESE_TO_FIELD:
            return CHINESE_TO_FIELD[chinese]
        for k, v in CHINESE_TO_FIELD.items():
            if k in chinese or chinese in k:
                return v
        return None

    def determine_table(self, raw_columns: List, raw_data: Dict) -> str:
        """根据实际字段内容确定目标表"""
        mapped = set()
        for col in raw_columns:
            f = self.map_field(col)
            if f:
                mapped.add(f)
        scores = {}
        for tbl, sig in TABLE_SIGNATURE_FIELDS.items():
            score = len(mapped & set(sig))
            if score > 0:
                scores[tbl] = score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return 'income_sheet'

    def process_record(self, record: Dict) -> Tuple[bool, str, Optional[Dict]]:
        try:
            raw_columns = json.loads(record['raw_columns']) if isinstance(record['raw_columns'], str) else record['raw_columns']
            raw_data = json.loads(record['raw_data']) if isinstance(record['raw_data'], str) else record['raw_data']
            report_year = record.get('report_year', 0)
            if report_year == 0:
                period = str(record.get('report_period', ''))
                if len(period) >= 4:
                    report_year = int(period[:4])

            target_table = self.determine_table(raw_columns, raw_data)
            mapped_data = {
                'stock_code': record.get('stock_code', ''),
                'stock_abbr': record.get('stock_abbr', ''),
                'report_period': record.get('report_period', ''),
                'report_year': report_year,
                'validation_status': 'pending',
                'validation_tags': '[]'
            }

            for col in raw_columns:
                field = self.map_field(col)
                if not field:
                    continue
                for year_offset in range(3):
                    val = get_year_value(raw_data, col, report_year - year_offset)
                    if val is not None:
                        mapped_data[field] = val
                        break

            return True, "", {'table': target_table, 'data': mapped_data}
        except Exception as e:
            return False, str(e), None

    # 缓存各表实际列名
    _table_columns_cache: Dict[str, set] = {}

    def get_table_columns(self, table: str) -> set:
        if table not in self._table_columns_cache:
            with self.conn.cursor() as cur:
                cur.execute(f"DESCRIBE {table}")
                self._table_columns_cache[table] = {row[0] for row in cur.fetchall()}
        return self._table_columns_cache[table]

    # 小数点后4位的字段（decimal(10,4)），值不能超过9999
    DECIMAL4_FIELDS = {
        'gross_profit_margin', 'net_profit_margin', 'roe', 'roe_weighted_excl_non_recurring',
        'net_profit_yoy_growth', 'operating_revenue_yoy_growth', 'net_profit_qoq_growth',
        'operating_revenue_qoq_growth', 'net_profit_excl_non_recurring_yoy', 'eps',
        'net_asset_per_share', 'operating_cf_per_share', 'asset_liability_ratio',
        'operating_cf_ratio_of_net_cf', 'investing_cf_ratio_of_net_cf', 'financing_cf_ratio_of_net_cf',
    }

    def upsert(self, table: str, data: Dict) -> bool:
        valid_cols = self.get_table_columns(table)
        clean = {k: v for k, v in data.items() if v is not None and k in valid_cols}
        if not clean:
            return False
        # 过滤超出 decimal(10,4) 范围的字段
        for field in self.DECIMAL4_FIELDS:
            if field in clean:
                val = clean[field]
                if isinstance(val, float):
                    # 百分比形式（如 12.5 表示 12.5%）：转成小数后校验
                    # 小数形式（如 0.125 表示 12.5%）：已存储原始值
                    # 统一按小数处理：超过1的视为百分比格式，转成小数
                    if val > 1:
                        clean[field] = val / 100.0
                    # 再校验是否超出范围
                    if abs(clean[field]) > 0.9999:
                        clean[field] = None
        cols = list(clean.keys())
        ph = ['%s'] * len(cols)
        update = ', '.join([f'{c}=VALUES({c})' for c in cols
                           if c not in ('stock_code', 'report_period', 'serial_number')])
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(ph)})"
        if update:
            sql += f" ON DUPLICATE KEY UPDATE {update}"
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, list(clean.values()))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"  写入失败 [{table}]: {e}")
            return False

    def update_status(self, record_id: int, status: str, err: str = ''):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE raw_extracted SET process_status=%s, error_msg=%s WHERE id=%s",
                        (status, err, record_id))
        self.conn.commit()

    def run(self, limit: Optional[int] = None, reprocess: Optional[str] = None) -> Dict:
        self.connect()
        status = reprocess if reprocess else 'pending'
        records = self.fetch_pending(limit, status)
        ok, fail = 0, 0
        for rec in records:
            ok_flag, err, mapped = self.process_record(rec)
            if ok_flag and mapped:
                if self.upsert(mapped['table'], mapped['data']):
                    self.update_status(rec['id'], 'mapped')
                    ok += 1
                else:
                    self.update_status(rec['id'], 'failed', 'upsert失败')
                    fail += 1
            else:
                self.update_status(rec['id'], 'failed', err)
                fail += 1
        self.close()
        return {'total': len(records), 'success': ok, 'failed': fail}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--reprocess', choices=['pending', 'failed'], default=None)
    args = p.parse_args()
    r = FieldMatcher().run(limit=args.limit, reprocess=args.reprocess)
    print(f"\n完成: 总={r['total']} 成功={r['success']} 失败={r['failed']}")


if __name__ == '__main__':
    main()
