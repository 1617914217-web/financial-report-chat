# -*- coding: utf-8 -*-
"""
LLM兜底填充模块：当规则提取结果为空时，调用DeepSeek API补充数据

保守合并原则：
  - 只填充规则提取结果为 NULL 的字段
  - 绝不覆盖规则已提取的数据
  - 防止LLM幻觉污染

使用：
  python llm_filler.py --limit 50          # 处理50条
  python llm_filler.py --dry-run           # 只测试不写入
"""
import json, os, sys, argparse, re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

import pymysql
import requests


# ======================== 财务字段英文名 → 中文名 ========================
FIELD_TO_CHINESE = {
    # 资产负债表
    "asset_cash_and_cash_equivalents": "货币资金",
    "asset_accounts_receivable": "应收账款",
    "asset_inventory": "存货",
    "asset_total_assets": "资产总计",
    "liability_accounts_payable": "应付账款",
    "liability_advance_from_customers": "预收款项",
    "liability_short_term_loans": "短期借款",
    "liability_total_liabilities": "负债合计",
    "equity_total_equity": "所有者权益合计",
    "equity_unappropriated_profit": "未分配利润",
    "asset_liability_ratio": "资产负债率",
    
    # 利润表
    "total_operating_revenue": "营业收入",
    "operating_expense_cost_of_sales": "营业成本",
    "operating_expense_selling_expenses": "销售费用",
    "operating_expense_administrative_expenses": "管理费用",
    "operating_expense_financial_expenses": "财务费用",
    "operating_expense_rnd_expenses": "研发费用",
    "operating_profit": "营业利润",
    "total_profit": "利润总额",
    "net_profit": "净利润",
    
    # 核心指标
    "eps": "每股收益",
    "roe": "净资产收益率",
    "gross_profit_margin": "销售毛利率",
    "net_profit_margin": "销售净利率",
    "net_profit_yoy_growth": "净利润同比增长",
    "operating_revenue_yoy_growth": "营业收入同比增长",
}


def get_mysql_config() -> Dict:
    return {
        'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '181415157Ak.'),
        'database': os.getenv('MYSQL_DATABASE', 'intelligent_data_query'),
        'charset': 'utf8mb4'
    }


def get_siliconflow_config() -> Dict:
    """获取SiliconFlow API配置"""
    return {
        'api_key': os.getenv('SILICONFLOW_API_KEY', 'sk-jjauygujsfgzhmdftrmcpuahuuzlwqpkoymyqmdkpvkrbvlu'),
        'base_url': os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1'),
        'model': os.getenv('SILICONFLOW_MODEL', 'deepseek-ai/DeepSeek-V3')
    }


def call_llm(prompt: str, temperature: float = 0.1) -> Optional[str]:
    """调用SiliconFlow API"""
    config = get_siliconflow_config()
    
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": config['model'],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1024
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"API调用失败: {e}")
        return None


def parse_llm_response(text: str) -> Dict[str, float]:
    """解析LLM返回的JSON"""
    # 尝试提取JSON
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    
    # 备用：手动解析 "字段: 值" 格式
    result = {}
    for line in text.split('\n'):
        if ':' in line:
            parts = line.split(':', 1)
            field = parts[0].strip().strip('"').strip("'")
            value = parts[1].strip().strip('"').strip("'")
            try:
                result[field] = float(value.replace(',', '').replace('%', ''))
            except:
                pass
    
    return result


def build_llm_prompt(table_name: str, stock_code: str, report_period: str, 
                     missing_fields: List[str], page_text: str = '') -> str:
    """构建LLM prompt"""
    # 缺失的中文字段
    missing_chinese = [FIELD_TO_CHINESE.get(f, f) for f in missing_fields]
    
    prompt = f"""你是一个专业的财务数据提取助手。请从以下财务报表文本中提取缺失的财务数据。

股票代码: {stock_code}
报告期: {report_period}
报表类型: {table_name}

需要提取的字段（中文）: {', '.join(missing_chinese)}

请直接从文本中提取数值，不要估算。如果某个字段在文本中不存在，请不要返回该字段。

要求：
1. 只返回JSON格式，如 {{"货币资金": 1234567.89, "应收账款": 987654.32}}
2. 数值应为原始金额，不要百分比
3. 如果文本中没有该字段，则不返回
4. 不要返回任何解释或说明

"""
    
    if page_text:
        prompt += f"\n财务报表文本：\n{page_text[:3000]}"
    
    return prompt


class LLMFiller:
    """LLM兜底填充器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db_config = get_mysql_config()
        self.conn = None
    
    def connect(self):
        self.conn = pymysql.connect(**self.db_config)
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def get_records_with_missing_fields(self, limit: int = 50) -> List[Dict]:
        """获取需要LLM填充的记录"""
        # 找出已映射但仍有空缺的记录
        tables = ['income_sheet', 'balance_sheet', 'stock_income_statement_data', 
                  'core_performance_indicators_sheet']
        
        results = []
        
        for table in tables:
            sql = f"""
                SELECT r.*, r.raw_data, r.raw_columns, r.auto_table_type,
                       t.stock_code, t.report_period, t.report_year
                FROM raw_extracted r
                LEFT JOIN {table} t ON r.stock_code = t.stock_code AND r.report_period = t.report_period
                WHERE r.process_status = 'mapped'
                LIMIT %s
            """
            
            with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, (limit,))
                results.extend(cursor.fetchall())
        
        return results[:limit]
    
    def get_table_schema(self, table: str) -> List[str]:
        """获取表的字段列表"""
        with self.conn.cursor() as cursor:
            cursor.execute(f"DESCRIBE {table}")
            return [row[0] for row in cursor.fetchall() 
                    if row[0] not in ('serial_number', 'stock_code', 'stock_abbr', 
                                     'report_period', 'report_year', 'validation_status', 'validation_tags')]
    
    def find_missing_fields(self, table: str, stock_code: str, report_period: str) -> Tuple[Dict, List[str]]:
        """查找空缺字段，返回(当前数据, 空缺字段列表)"""
        sql = f"SELECT * FROM {table} WHERE stock_code = %s AND report_period = %s"
        
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (stock_code, report_period))
            row = cursor.fetchone()
            
            if not row:
                return {}, self.get_table_schema(table)
            
            # 找出NULL或0的字段
            schema = self.get_table_schema(table)
            missing = []
            for field in schema:
                val = row.get(field)
                if val is None or val == 0 or val == 0.0:
                    missing.append(field)
            
            return row, missing
    
    def conservative_merge(self, table: str, stock_code: str, report_period: str, 
                          new_data: Dict) -> bool:
        """保守合并：只填充NULL字段，不覆盖已有数据"""
        if not new_data:
            return False
        
        # 获取现有数据
        sql = f"SELECT * FROM {table} WHERE stock_code = %s AND report_period = %s"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (stock_code, report_period))
            row = cursor.fetchone()
        
        if not row:
            # 不存在，插入新记录
            new_data['stock_code'] = stock_code
            new_data['report_period'] = report_period
            cols = list(new_data.keys())
            vals = list(new_data.values())
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})"
        else:
            # 存在，只更新NULL字段
            updates = []
            vals = []
            for k, v in new_data.items():
                if row.get(k) is None or row.get(k) == 0:
                    updates.append(f"{k}=%s")
                    vals.append(v)
            
            if not updates:
                return True  # 没有需要更新的
            
            vals.extend([stock_code, report_period])
            sql = f"UPDATE {table} SET {', '.join(updates)} WHERE stock_code = %s AND report_period = %s"
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, vals)
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"合并失败: {e}")
            return False
    
    def run(self, limit: int = 50) -> Dict:
        """运行LLM填充"""
        self.connect()
        
        # 从映射后的记录中找缺失字段
        records = self.get_records_with_missing_fields(limit)
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        for record in records:
            stock_code = record.get('stock_code', '')
            report_period = record.get('report_period', '')
            table = record.get('auto_table_type', 'income_sheet')
            
            if not stock_code or not report_period:
                skip_count += 1
                continue
            
            # 查空缺字段
            _, missing = self.find_missing_fields(table, stock_code, report_period)
            
            if not missing:
                skip_count += 1
                continue
            
            # 构建prompt
            prompt = build_llm_prompt(
                table, stock_code, report_period, 
                missing[:5]  # 最多问5个字段
            )
            
            # 调用LLM
            resp = call_llm(prompt)
            if not resp:
                fail_count += 1
                continue
            
            # 解析结果
            extracted = parse_llm_response(resp)
            if not extracted:
                fail_count += 1
                continue
            
            # 转换为英文字段
            english_data = {}
            for cn, val in extracted.items():
                for en, cn2 in FIELD_TO_CHINESE.items():
                    if cn2 == cn:
                        english_data[en] = val
                        break
            
            if english_data:
                if self.dry_run:
                    print(f"[DRY RUN] {stock_code} {report_period} -> {english_data}")
                    success_count += 1
                else:
                    if self.conservative_merge(table, stock_code, report_period, english_data):
                        success_count += 1
                    else:
                        fail_count += 1
            else:
                skip_count += 1
        
        self.close()
        
        return {
            'total': len(records),
            'success': success_count,
            'failed': fail_count,
            'skipped': skip_count
        }


def main():
    parser = argparse.ArgumentParser(description='LLM兜底填充')
    parser.add_argument('--limit', type=int, default=50, help='处理条数')
    parser.add_argument('--dry-run', action='store_true', help='只测试不写入')
    args = parser.parse_args()
    
    filler = LLMFiller(dry_run=args.dry_run)
    result = filler.run(limit=args.limit)
    
    print(f"\n完成: 总数={result['total']}, 成功={result['success']}, "
          f"失败={result['failed']}, 跳过={result['skipped']}")


if __name__ == '__main__':
    main()
