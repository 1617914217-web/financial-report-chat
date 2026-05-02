# -*- coding: utf-8 -*-
"""
任务三统一入口 - 整合任务二pipeline + RAG + Agent规划 + 归因溯源

功能：
1. 接收用户问题
2. 意图分类（任务二）
3. 槽位填充（任务二）
4. 实体对齐（新增）
5. Agent规划（复杂问题分解）
6. SQL查询 / RAG检索
7. 可视化 + 结论生成
8. 归因溯源输出

示例：
    assistant = Task3Assistant()
    result = assistant.ask("2023年净利润最高的公司是哪家？其增长原因是什么？")
"""
import os, sys, json
from typing import Dict, Optional

# 确保能导入任务二模块
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from pipeline import FinancialQA
from entity_aligner import EntityAligner
from agent_planner import SmartDataAssistant
from attribution_module import ExplainablePipeline


class Task3Assistant:
    """任务三智能助手 - 增强版问答"""

    def __init__(self, use_rag: bool = False, reports_dir: str = None):
        """
        Args:
            use_rag: 是否启用RAG知识库
            reports_dir: 研报目录路径
        """
        print("初始化任务三助手...")

        # 1. 任务二基础pipeline
        self.qa = FinancialQA()

        # 2. 实体对齐
        self.aligner = EntityAligner()

        # 3. Agent规划（复杂问题）
        self.agent = SmartDataAssistant()

        # 4. RAG知识库（可选）
        self.kb = None
        if use_rag and reports_dir:
            try:
                from rag_knowledge_base import KnowledgeBase
                self.kb = KnowledgeBase(embedding_model="BAAI/bge-large-zh-v1.5")
                if os.path.exists(reports_dir):
                    self.kb.add_documents(reports_dir)
                    print(f"RAG知识库已加载: {reports_dir}")
            except Exception as e:
                print(f"RAG加载失败: {e}")

        # 5. 可解释流水线
        self.explainable = ExplainablePipeline(self.qa, self.kb)

        print("任务三助手初始化完成")

    def ask(self, question: str) -> Dict:
        """
        问答入口

        Args:
            question: 用户自然语言问题

        Returns:
            标准输出格式 {Q, A: {content, image, references}}
        """
        print(f"\n{'='*60}")
        print(f"问题: {question}")
        print(f"{'='*60}")

        # Step 1: 使用任务二pipeline获取基础结果
        base_result = self.qa.ask(question)

        # Step 2: 实体对齐验证
        if base_result.get("slots"):
            aligned_slots = self.aligner.align(base_result["slots"])
            valid, msg = self.aligner.validate(aligned_slots)
            if not valid:
                print(f"对齐警告: {msg}")

        # Step 3: 判断是否复杂问题，需要Agent规划
        intent = base_result.get("intent", "QUERY_SINGLE")
        needs_planning = self._is_complex_question(question, intent)

        if needs_planning:
            # 使用Agent规划执行
            agent_result = self.agent.run(
                intent=intent,
                slots=base_result.get("slots", {}),
                original_query=question,
            )
            # 合并Agent结果
            if agent_result.get("final_answer"):
                base_result["conclusion"] = agent_result["final_answer"]

        # Step 4: 归因追踪输出
        output = self.explainable.ask(question)

        # 确保结论不为空
        if not output["A"]["content"] and base_result.get("conclusion"):
            output["A"]["content"] = base_result["conclusion"]

        # 添加图表
        if base_result.get("images"):
            output["A"]["image"] = base_result["images"]

        return output

    def _is_complex_question(self, question: str, intent: str) -> bool:
        """判断是否为复杂问题（需要多步规划）"""
        complex_keywords = [
            "为什么", "原因", "分析", "对比", "比较",
            "top", "排名", "同比", "环比", "增长",
        ]
        has_complex_kw = any(kw in question for kw in complex_keywords)
        is_multi_intent = intent in ("COMPARE", "RANK", "CALCULATE")
        return has_complex_kw or is_multi_intent

    def batch_ask(self, questions: list) -> list:
        """批量问答"""
        results = []
        for q in questions:
            try:
                result = self.ask(q)
                results.append(result)
            except Exception as e:
                results.append({
                    "Q": q,
                    "A": {
                        "content": f"处理失败: {str(e)}",
                        "image": [],
                        "references": [],
                    }
                })
        return results


if __name__ == "__main__":
    # 测试
    assistant = Task3Assistant(use_rag=False)

    test_questions = [
        "金花股份2022年净利润是多少？",
        "2022年净利润排名前3的公司是哪些？",
        "万邦德2023年总资产是多少？",
    ]

    for q in test_questions:
        result = assistant.ask(q)
        print("\n" + "="*60)
        print(f"Q: {result['Q']}")
        print(f"A: {result['A']['content']}")
        if result['A']['references']:
            print(f"References: {len(result['A']['references'])} 个来源")
