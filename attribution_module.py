# -*- coding: utf-8 -*-
"""
归因分析模块 - 可解释性输出

为每个回答增加references字段，区分：
- SQL来源（查询的表、SQL语句、时间戳）
- 知识库来源（研报路径、相关段落、页码）

输出结构：
{
    "Q": "用户问题",
    "A": {
        "content": "回答内容",
        "image": ["./result/B003_1.jpg"],
        "references": [
            {"type": "sql_source", "table": "...", "query": "...", "timestamp": "..."},
            {"type": "knowledge_base", "paper_path": "...", "page": 12, "text": "..."}
        ]
    }
}
"""
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class SQLReference:
    """SQL查询引用"""
    type: str = "sql_source"
    table: str = ""
    query: str = ""
    timestamp: str = ""
    row_count: int = 0

    def to_dict(self):
        return {
            "type": self.type,
            "table": self.table,
            "query": self.query,
            "timestamp": self.timestamp,
            "row_count": self.row_count,
        }


@dataclass
class KnowledgeReference:
    """知识库引用"""
    type: str = "knowledge_base"
    paper_path: str = ""
    page: int = 0
    text: str = ""
    score: float = 0.0

    def to_dict(self):
        return {
            "type": self.type,
            "paper_path": self.paper_path,
            "page": self.page,
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "score": round(self.score, 4),
        }


class AttributionTracker:
    """归因追踪器 - 记录每个回答的数据来源"""

    def __init__(self):
        self.references: List[Dict] = []
        self.query_start_time: Optional[datetime] = None

    def start_query(self):
        """开始记录查询"""
        self.query_start_time = datetime.now()
        self.references = []

    def add_sql_ref(self, table: str, query: str, row_count: int = 0):
        """添加SQL引用"""
        self.references.append(SQLReference(
            table=table,
            query=query,
            timestamp=self.query_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.query_start_time else "",
            row_count=row_count,
        ).to_dict())

    def add_knowledge_ref(self, paper_path: str, page: int, text: str, score: float = 0.0):
        """添加知识库引用"""
        self.references.append(KnowledgeReference(
            paper_path=paper_path,
            page=page,
            text=text,
            score=score,
        ).to_dict())

    def get_output(self, question: str, answer_content: str, images: List[str] = None) -> Dict:
        """
        生成带归因的最终输出

        Args:
            question: 用户问题
            answer_content: 回答内容
            images: 图表路径列表

        Returns:
            标准输出格式
        """
        return {
            "Q": question,
            "A": {
                "content": answer_content,
                "image": images or [],
                "references": self.references,
            }
        }

    def format_for_display(self, output: Dict) -> str:
        """格式化为人类可读文本"""
        lines = []
        lines.append(f"问题: {output['Q']}")
        lines.append(f"\n回答: {output['A']['content']}")

        if output['A']['image']:
            lines.append(f"\n图表: {', '.join(output['A']['image'])}")

        if output['A']['references']:
            lines.append("\n数据来源:")
            for i, ref in enumerate(output['A']['references'], 1):
                if ref['type'] == 'sql_source':
                    lines.append(f"  [{i}] SQL查询 | 表: {ref.get('table', 'N/A')}")
                    lines.append(f"      语句: {ref.get('query', 'N/A')[:80]}...")
                    lines.append(f"      时间: {ref.get('timestamp', 'N/A')}")
                elif ref['type'] == 'knowledge_base':
                    lines.append(f"  [{i}] 研报引用 | 文件: {ref.get('paper_path', 'N/A')}")
                    lines.append(f"      页码: {ref.get('page', 'N/A')}")
                    lines.append(f"      内容: {ref.get('text', 'N/A')[:100]}...")

        return "\n".join(lines)


class ExplainablePipeline:
    """可解释流水线 - 整合归因追踪"""

    def __init__(self, pipeline, kb=None):
        """
        Args:
            pipeline: 任务二的FinancialQA实例
            kb: RAG知识库实例（可选）
        """
        self.pipeline = pipeline
        self.kb = kb
        self.tracker = AttributionTracker()

    def ask(self, question: str) -> Dict:
        """
        带归因追踪的问答

        Returns:
            标准输出格式（含references）
        """
        self.tracker.start_query()

        # 1. 执行原pipeline
        result = self.pipeline.ask(question)

        # 2. 记录SQL引用
        if result.get("sql"):
            # 推断表名
            sql = result["sql"]
            table = self._extract_table(sql)
            self.tracker.add_sql_ref(
                table=table,
                query=sql,
                row_count=len(result.get("data", [])),
            )

        # 3. 如启用RAG，记录知识库引用
        if self.kb and result.get("intent") in ("QUERY_SINGLE", "QUERY_MULTI"):
            rag_results = self.kb.search(question, top_k=2)
            for r in rag_results:
                self.tracker.add_knowledge_ref(
                    paper_path=r["metadata"].get("source", ""),
                    page=r["metadata"].get("page", 0),
                    text=r["text"],
                    score=r.get("rerank_score", r.get("score", 0)),
                )

        # 4. 组装输出
        conclusion = result.get("conclusion", "")
        images = result.get("images", [])

        output = self.tracker.get_output(
            question=question,
            answer_content=conclusion,
            images=images,
        )

        return output

    def _extract_table(self, sql: str) -> str:
        """从SQL中提取表名"""
        import re
        match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if match:
            return match.group(1)
        return "unknown"


if __name__ == "__main__":
    # 测试
    tracker = AttributionTracker()
    tracker.start_query()

    tracker.add_sql_ref(
        table="income_sheet",
        query="SELECT net_profit FROM income_sheet WHERE stock_code='000001'",
        row_count=1,
    )
    tracker.add_knowledge_ref(
        paper_path="./reports/行业研报_2025.pdf",
        page=12,
        text="该行业龙头企业集中度较高，平安银行净利润增长主要得益于...",
        score=0.89,
    )

    output = tracker.get_output(
        question="平安银行2023年净利润是多少？",
        answer_content="平安银行2023年净利润为456亿元，同比增长15.3%。",
        images=["./result/B003_1.jpg"],
    )

    print(json.dumps(output, ensure_ascii=False, indent=2))
    print("\n" + "="*50)
    print(tracker.format_for_display(output))
