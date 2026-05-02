# -*- coding: utf-8 -*-
"""
端到端问答流水线 (Pipeline)

整合所有模块：
  预处理 → 意图分类 → 槽位填充 → NL2SQL → SQL校验 → 执行 → 可视化

输入: 自然语言问句
输出: {sql, data, chart_path, conclusion, intent, slots}
"""
import os, sys
import pymysql
from typing import Dict, List, Optional

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from config_loader import load as load_env
from preprocess_pipeline import PreprocessPipeline
from predict_intent import predict as predict_intent
from slot_filler import RuleBasedSlotFiller
from nl2sql import NL2SQLGenerator
from sql_validator import SQLValidator
from knowledge_graph import FinancialKnowledgeGraph
from visualizer import Visualizer


class FinancialQA:
    """财报智能问答系统"""

    def __init__(self):
        load_env()
        self.env = os.environ
        self.preprocessor = PreprocessPipeline()
        self.intent_predictor = None  # 使用predict_intent函数
        self.slot_filler = RuleBasedSlotFiller()
        self.nl2sql = NL2SQLGenerator()
        self.kg = FinancialKnowledgeGraph()
        self.visualizer = Visualizer()
        self.db_config = {
            "host": self.env.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(self.env.get("MYSQL_PORT", "3306")),
            "user": self.env.get("MYSQL_USER", "root"),
            "password": self.env.get("MYSQL_PASSWORD", ""),
            "database": self.env.get("MYSQL_DATABASE", "intelligent_data_query"),
            "charset": "utf8mb4",
        }

    def ask(self, question: str) -> dict:
        """
        回答用户问题
        返回完整结果字典
        """
        result = {
            "question": question,
            "preprocessed": "",
            "intent": "",
            "intent_confidence": 0.0,
            "slots": {},
            "sql": "",
            "sql_valid": False,
            "data": [],
            "chart_path": "",
            "conclusion": "",
            "error": "",
        }

        try:
            # Step 1: 预处理
            preprocessed = self.preprocessor.process(question)
            result["preprocessed"] = preprocessed

            # 取标准化文本用于下游
            normalized_text = preprocessed.get("normalized", "") if isinstance(preprocessed, dict) else str(preprocessed)

            # Step 2: 意图分类
            intent, confidence = predict_intent(normalized_text)
            result["intent"] = intent
            result["intent_confidence"] = confidence

            # Step 3: 槽位填充
            slot_result = self.slot_filler.extract(normalized_text)
            result["slots"] = slot_result["slots"]

            # Step 4: NL2SQL生成
            # 用原始问题+槽位信息生成更准确的SQL
            enriched_question = normalized_text
            if result["slots"].get("company_code"):
                enriched_question += " 公司代码:" + result["slots"]["company_code"]
            elif result["slots"].get("company"):
                enriched_question += " 公司:" + result["slots"]["company"]
            if result["slots"].get("year"):
                enriched_question += " 年份:" + result["slots"]["year"]
            sql_result = self.nl2sql.generate(enriched_question, intent=intent)
            if sql_result["error"]:
                result["error"] = f"SQL生成失败: {sql_result['error']}"
                return result
            result["sql"] = sql_result["sql"]

            # Step 5: SQL校验
            v = SQLValidator.validate(result["sql"])
            result["sql_valid"] = v["valid"]
            if not v["valid"]:
                result["error"] = f"SQL不安全: {v['reason']}"
                return result

            # Step 6: 执行SQL
            data = self._execute_sql(result["sql"])
            result["data"] = data

            # Step 7: 可视化
            if data and len(data) > 0:
                chart_data = self._format_for_chart(data, sql_result.get("table", ""))
                if chart_data:
                    chart_type = "auto"
                    if intent == "RANK":
                        chart_type = "bar"
                    elif intent == "COMPARE":
                        chart_type = "bar"
                    result["chart_path"] = self.visualizer.render(
                        chart_data, chart_type=chart_type,
                        title=question[:30]
                    )
                result["conclusion"] = self.visualizer.generate_conclusion(chart_data or data, question)

            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def _execute_sql(self, sql: str) -> List[dict]:
        """执行SQL查询"""
        conn = pymysql.connect(**self.db_config)
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    def _format_for_chart(self, data: List[dict], table: str) -> List[dict]:
        """将查询结果格式化为图表数据"""
        if not data:
            return []
        
        result = []
        for d in data:
            # 查找label：优先使用stock_abbr，其次是stock_code，最后是第一个字符串列
            label = ""
            if "stock_abbr" in d and d["stock_abbr"]:
                label = str(d["stock_abbr"])
            elif "stock_code" in d and d["stock_code"]:
                label = str(d["stock_code"])
            
            # 查找value：第一个非None的数值字段
            value = None
            for k, v in d.items():
                if k in ("stock_code", "stock_abbr"):
                    continue
                if v is not None:
                    try:
                        value = float(v)
                        break
                    except (TypeError, ValueError):
                        continue
            
            if value is not None:
                result.append({"label": label or "结果", "value": value})
        
        return result if result else data


if __name__ == "__main__":
    qa = FinancialQA()

    tests = [
        "金花股份2022年净利润是多少",
        "2022年净利润最高的3家公司",
        "金花股份和万邦德2022年总资产对比",
    ]

    for q in tests:
        print("\n" + "="*60)
        print("Q: " + q)
        r = qa.ask(q)
        print("Intent: " + r['intent'] + " (conf=" + str(round(r['intent_confidence'], 3)) + ")")
        print("Slots: " + str(r['slots']))
        print("SQL: " + r['sql'])
        print("SQL Valid: " + str(r['sql_valid']))
        if r['error']:
            print("Error: " + r['error'])
        else:
            print("Data: " + str(r['data'][:3] if r['data'] else 'None'))
            print("Chart: " + r['chart_path'])
            print("Conclusion: " + r['conclusion'])
