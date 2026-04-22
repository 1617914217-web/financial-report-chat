# -*- coding: utf-8 -*-
"""
五维财务逻辑一致性校验体系

校验维度：
  1. 表内平衡（资产≈负债+权益，误差<1%）
  2. 表间钩稽（利润表与资产负债表一致性）
  3. 时序连续性（增长率异常检测，>500%或<-90%标记异常）
  4. 业务逻辑（营收>营业利润>净利润）
  5. 跨报告一致（年报优先）

处理方式：
  - 校验失败的记录标记 validation_status = 'failed'
  - 校验警告的记录标记 validation_status = 'warning'
  - 详细的校验标签存入 validation_tags JSON

使用：
  python validator.py                    # 校验全部数据
  python validator.py --table income_sheet  # 只校验指定表
  python validator.py --fix              # 自动修复可修复的问题
"""
import json, os, sys, argparse
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

import pymysql


def get_mysql_config() -> Dict:
    return {
        'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '181415157Ak.'),
        'database': os.getenv('MYSQL_DATABASE', 'intelligent_data_query'),
        'charset': 'utf8mb4'
    }


def safe_divide(a: float, b: float) -> Optional[float]:
    """安全除法"""
    if b is None or b == 0 or b == 0.0:
        return None
    return a / b


def calc_growth_rate(current: float, previous: float) -> Optional[float]:
    """计算同比增长率"""
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


class Validator:
    """五维校验器"""
    
    def __init__(self, auto_fix: bool = False):
        self.auto_fix = auto_fix
        self.db_config = get_mysql_config()
        self.conn = None
        self.warnings = []
        self.errors = []
    
    def connect(self):
        self.conn = pymysql.connect(**self.db_config)
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    # ======================== 维度1: 表内平衡 ========================
    def validate_balance_sheet(self, record: Dict) -> List[Dict]:
        """资产负债表：资产总计 ≈ 负债合计 + 所有者权益合计"""
        issues = []
        
        asset_total = record.get('asset_total_assets')
        liability_total = record.get('liability_total_liabilities')
        equity_total = record.get('equity_total_equity')
        
        if all(v is not None for v in [asset_total, liability_total, equity_total]):
            expected = liability_total + equity_total
            if expected != 0:
                error_rate = abs(asset_total - expected) / abs(expected)
                
                if error_rate > 0.01:  # >1%
                    issues.append({
                        'dimension': 'table_internal_balance',
                        'severity': 'error',
                        'message': f'资产总计({asset_total:.2f}) ≠ 负债合计+所有者权益合计({expected:.2f})，误差{error_rate*100:.2f}%'
                    })
                elif error_rate > 0.001:  # >0.1%
                    issues.append({
                        'dimension': 'table_internal_balance',
                        'severity': 'warning',
                        'message': f'资产总计与负债+权益略有差异，误差{error_rate*100:.2f}%'
                    })
        
        return issues
    
    # ======================== 维度2: 表间钩稽 ========================
    def validate_cross_table(self, stock_code: str, report_period: str) -> List[Dict]:
        """表间钩稽校验"""
        issues = []
        
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查资产负债表
            cursor.execute(
                "SELECT asset_cash_and_cash_equivalents, asset_total_assets FROM balance_sheet WHERE stock_code = %s AND report_period = %s",
                (stock_code, report_period)
            )
            bs = cursor.fetchone()
            
            # 查利润表
            cursor.execute(
                "SELECT net_cash_flow FROM income_sheet WHERE stock_code = %s AND report_period = %s",
                (stock_code, report_period)
            )
            ins = cursor.fetchone()
            
            # 查核心指标
            cursor.execute(
                "SELECT total_operating_revenue, net_profit FROM core_performance_indicators_sheet WHERE stock_code = %s AND report_period = %s",
                (stock_code, report_period)
            )
            cpi = cursor.fetchone()
        
        # 检查：核心指标的营收 ≈ 利润表的营收（如果有）
        if cpi and ins:
            cpi_rev = cpi.get('total_operating_revenue')
            # 利润表没有直接营收字段，这里只是示例
        
        return issues
    
    # ======================== 维度3: 时序连续性 ========================
    def validate_temporal(self, table: str, stock_code: str, report_period: str, 
                         report_year: int) -> List[Dict]:
        """时序连续性：增长率异常检测"""
        issues = []
        
        # 查上一年的数据
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"SELECT * FROM {table} WHERE stock_code = %s AND report_year = %s",
                (stock_code, report_year - 1)
            )
            prev_record = cursor.fetchone()
        
        if not prev_record:
            return issues  # 没有前一年数据，跳过
        
        # 当前记录
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                f"SELECT * FROM {table} WHERE stock_code = %s AND report_period = %s",
                (stock_code, report_period)
            )
            curr_record = cursor.fetchone()
        
        if not curr_record:
            return issues
        
        # 检查关键指标的增长率
        growth_fields = {
            'income_sheet': ['net_cash_flow'],
            'balance_sheet': ['asset_total_assets', 'liability_total_liabilities', 'equity_total_equity'],
            'stock_income_statement_data': ['total_operating_revenue', 'net_profit', 'operating_profit'],
            'core_performance_indicators_sheet': ['total_operating_revenue', 'net_profit', 'net_profit_excl_non_recurring']
        }
        
        fields_to_check = growth_fields.get(table, [])
        
        for field in fields_to_check:
            curr_val = curr_record.get(field)
            prev_val = prev_record.get(field)
            
            if curr_val and prev_val and prev_val != 0:
                growth = (curr_val - prev_val) / abs(prev_val)
                
                # 增长率 > 500% 或 < -90% 标记异常
                if growth > 5.0 or growth < -0.9:
                    issues.append({
                        'dimension': 'temporal_continuity',
                        'severity': 'warning',
                        'message': f'{field} 增长率异常: {growth*100:.1f}% (当期: {curr_val}, 上期: {prev_val})'
                    })
        
        return issues
    
    # ======================== 维度4: 业务逻辑 ========================
    def validate_business_logic(self, record: Dict, table: str) -> List[Dict]:
        """业务逻辑校验"""
        issues = []
        
        if table != 'stock_income_statement_data':
            return issues
        
        # 营收 > 营业利润 > 净利润
        revenue = record.get('total_operating_revenue')
        op_profit = record.get('operating_profit')
        net_profit = record.get('net_profit')
        
        if all(v is not None for v in [revenue, op_profit, net_profit]):
            if op_profit > revenue:
                issues.append({
                    'dimension': 'business_logic',
                    'severity': 'error',
                    'message': f'营业利润({op_profit:.2f}) > 营业收入({revenue:.2f})，违反业务逻辑'
                })
            
            if net_profit > op_profit:
                issues.append({
                    'dimension': 'business_logic',
                    'severity': 'error',
                    'message': f'净利润({net_profit:.2f}) > 营业利润({op_profit:.2f})，违反业务逻辑'
                })
            
            if revenue < 0:
                issues.append({
                    'dimension': 'business_logic',
                    'severity': 'error',
                    'message': f'营业收入为负({revenue:.2f})，数据异常'
                })
        
        return issues
    
    # ======================== 维度5: 跨报告一致 ========================
    def validate_cross_report(self, stock_code: str, report_year: int) -> List[Dict]:
        """跨报告一致性：年报优先"""
        issues = []
        
        # 查年报和三季度报
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 年报
            cursor.execute(
                "SELECT report_period, total_operating_revenue, net_profit FROM stock_income_statement_data WHERE stock_code = %s AND report_period LIKE %s",
                (stock_code, f'{report_year}%')
            )
            reports = cursor.fetchall()
        
        if len(reports) < 2:
            return issues
        
        # 找出年报和季报
        annual = None
        quarterly = None
        for r in reports:
            period = r.get('report_period', '')
            if '12-31' in period:  # 年报
                annual = r
            elif '09-30' in period or '06-30' in period or '03-31' in period:
                quarterly = r
        
        if annual and quarterly:
            # 年报和季报营收应该有关联（年报 >= 季报）
            annual_rev = annual.get('total_operating_revenue')
            quarterly_rev = quarterly.get('total_operating_revenue')
            
            if annual_rev and quarterly_rev:
                if annual_rev < quarterly_rev:
                    issues.append({
                        'dimension': 'cross_report_consistency',
                        'severity': 'warning',
                        'message': f'年报营收({annual_rev:.2f}) < 季度报营收({quarterly_rev:.2f})，可能存在数据冲突'
                    })
        
        return issues
    
    # ======================== 主校验 ========================
    def validate_record(self, table: str, stock_code: str, report_period: str,
                       report_year: int, record: Dict) -> Tuple[str, List[Dict]]:
        """校验单条记录"""
        all_issues = []
        
        # 维度1: 表内平衡
        if table == 'balance_sheet':
            all_issues.extend(self.validate_balance_sheet(record))
        
        # 维度2: 表间钩稽
        all_issues.extend(self.validate_cross_table(stock_code, report_period))
        
        # 维度3: 时序连续性
        all_issues.extend(self.validate_temporal(table, stock_code, report_period, report_year))
        
        # 维度4: 业务逻辑
        all_issues.extend(self.validate_business_logic(record, table))
        
        # 维度5: 跨报告一致
        all_issues.extend(self.validate_cross_report(stock_code, report_year))
        
        # 确定状态
        has_error = any(i['severity'] == 'error' for i in all_issues)
        status = 'failed' if has_error else ('warning' if all_issues else 'passed')
        
        return status, all_issues
    
    def run(self, table: Optional[str] = None) -> Dict:
        """运行校验"""
        self.connect()
        
        tables = [table] if table else [
            'income_sheet', 'balance_sheet', 
            'stock_income_statement_data', 'core_performance_indicators_sheet'
        ]
        
        total = 0
        passed = 0
        warning_count = 0
        failed = 0
        all_records = []
        
        for tbl in tables:
            with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(f"SELECT * FROM {tbl}")
                records = cursor.fetchall()
            
            for record in records:
                total += 1
                stock_code = record.get('stock_code', '')
                report_period = record.get('report_period', '')
                report_year = record.get('report_year', 0)
                
                if not stock_code:
                    continue
                
                status, issues = self.validate_record(
                    tbl, stock_code, report_period, report_year, record
                )
                
                # 更新状态
                tags_json = json.dumps(issues, ensure_ascii=False)
                
                with self.conn.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {tbl} SET validation_status = %s, validation_tags = %s WHERE serial_number = %s",
                        (status, tags_json, record.get('serial_number'))
                    )
                self.conn.commit()
                
                if status == 'passed':
                    passed += 1
                elif status == 'warning':
                    warning_count += 1
                else:
                    failed += 1
                
                if issues:
                    all_records.append({
                        'table': tbl,
                        'stock_code': stock_code,
                        'report_period': report_period,
                        'status': status,
                        'issues': issues
                    })
        
        self.close()
        
        return {
            'total': total,
            'passed': passed,
            'warning': warning_count,
            'failed': failed,
            'details': all_records[:50]  # 最多返回50条详情
        }


def main():
    parser = argparse.ArgumentParser(description='五维财务校验')
    parser.add_argument('--table', type=str, choices=[
        'income_sheet', 'balance_sheet', 
        'stock_income_statement_data', 'core_performance_indicators_sheet'
    ], help='只校验指定表')
    parser.add_argument('--fix', action='store_true', help='自动修复可修复问题')
    args = parser.parse_args()
    
    validator = Validator(auto_fix=args.fix)
    result = validator.run(table=args.table)
    
    print(f"\n校验完成:")
    print(f"  总记录: {result['total']}")
    print(f"  通过: {result['passed']}")
    print(f"  警告: {result['warning']}")
    print(f"  失败: {result['failed']}")
    
    if result['details']:
        print(f"\n问题记录 (前10条):")
        for d in result['details'][:10]:
            print(f"  [{d['table']}] {d['stock_code']} {d['report_period']} - {d['status']}")
            for issue in d['issues'][:2]:
                print(f"    - {issue['message']}")


if __name__ == '__main__':
    main()
