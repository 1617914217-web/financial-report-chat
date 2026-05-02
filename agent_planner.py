# -*- coding: utf-8 -*-
"""
Agent规划模块 - Plan-and-Execute模式

针对复杂多步问题，先规划DAG执行计划，再逐步执行。
替代ReAct的边想边做，避免死循环和错误累积。

示例：
  用户："2024年利润最高的top10企业是哪些？这些企业的利润年同比是多少？"
  规划：
    Step1: 查询2024年利润Top10 → 得到公司列表
    Step2: 对每家公司查询2023年利润 → 计算同比
"""
import os, json, re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    QUERY_SQL = "query_sql"          # NL2SQL查询
    QUERY_RAG = "query_rag"          # RAG知识库检索
    CALCULATE = "calculate"          # 计算（同比、环比等）
    COMPARE = "compare"              # 对比分析
    SUMMARIZE = "summarize"          # 总结生成


@dataclass
class PlanStep:
    """执行计划步骤"""
    step_id: int
    task_type: TaskType
    description: str                 # 人类可读描述
    slots: Dict = field(default_factory=dict)  # 槽位参数
    depends_on: List[int] = field(default_factory=list)  # 依赖步骤ID
    status: str = "pending"          # pending/running/done/failed
    result: any = None               # 执行结果


class Planner:
    """规划器 - 将复杂问题分解为DAG执行计划"""

    def __init__(self):
        # 规则模板库
        self.templates = self._load_templates()

    def _load_templates(self) -> List[Dict]:
        """加载规划模板"""
        return [
            {
                "pattern": r"top\d+.*同比|同比.*top\d+",
                "description": "TopN排名 + 同比计算",
                "plan": [
                    {"task_type": "query_sql", "description": "查询TopN列表"},
                    {"task_type": "calculate", "description": "计算同比"},
                ]
            },
            {
                "pattern": r"对比|比较|vs|VS",
                "description": "多实体对比",
                "plan": [
                    {"task_type": "query_sql", "description": "查询多实体数据"},
                    {"task_type": "compare", "description": "生成对比分析"},
                ]
            },
            {
                "pattern": r"为什么|原因|分析",
                "description": "因果分析（数据+研报）",
                "plan": [
                    {"task_type": "query_sql", "description": "查询相关数据"},
                    {"task_type": "query_rag", "description": "检索研报分析"},
                    {"task_type": "summarize", "description": "综合分析结论"},
                ]
            },
            {
                "pattern": r"排名|前\d+|第[一二三四五六七八九十\d]+",
                "description": "排名查询",
                "plan": [
                    {"task_type": "query_sql", "description": "查询排名数据"},
                ]
            },
        ]

    def plan(self, intent: str, slots: Dict, original_query: str) -> List[PlanStep]:
        """
        根据意图和槽位生成执行计划

        Args:
            intent: 意图类型 (QUERY_SINGLE/CALCULATE/COMPARE/RANK/QUERY_MULTI)
            slots: 槽位填充结果
            original_query: 原始问句

        Returns:
            PlanStep列表（已按依赖排序）
        """
        steps = []
        step_id = 1

        # 检查是否匹配复杂模板
        for template in self.templates:
            if re.search(template["pattern"], original_query):
                for t in template["plan"]:
                    deps = []
                    if t["task_type"] in ("calculate", "compare", "summarize") and step_id > 1:
                        deps = [step_id - 1]

                    steps.append(PlanStep(
                        step_id=step_id,
                        task_type=TaskType(t["task_type"]),
                        description=t["description"],
                        slots=slots.copy(),
                        depends_on=deps,
                    ))
                    step_id += 1
                break
        else:
            # 默认单步计划
            if intent == "RANK":
                steps.append(PlanStep(
                    step_id=1,
                    task_type=TaskType.QUERY_SQL,
                    description="查询排名数据",
                    slots=slots,
                ))
            elif intent == "COMPARE":
                steps.append(PlanStep(
                    step_id=1,
                    task_type=TaskType.QUERY_SQL,
                    description="查询对比数据",
                    slots=slots,
                ))
                steps.append(PlanStep(
                    step_id=2,
                    task_type=TaskType.COMPARE,
                    description="生成对比分析",
                    slots=slots,
                    depends_on=[1],
                ))
            elif intent == "CALCULATE":
                steps.append(PlanStep(
                    step_id=1,
                    task_type=TaskType.QUERY_SQL,
                    description="查询基础数据",
                    slots=slots,
                ))
                steps.append(PlanStep(
                    step_id=2,
                    task_type=TaskType.CALCULATE,
                    description="执行计算",
                    slots=slots,
                    depends_on=[1],
                ))
            else:
                # QUERY_SINGLE / QUERY_MULTI
                steps.append(PlanStep(
                    step_id=1,
                    task_type=TaskType.QUERY_SQL,
                    description="查询数据",
                    slots=slots,
                ))

        return steps


class Executor:
    """执行器 - 按DAG顺序执行计划"""

    def __init__(self,
                 sql_tool: Optional[Callable] = None,
                 rag_tool: Optional[Callable] = None,
                 calculate_tool: Optional[Callable] = None,
                 compare_tool: Optional[Callable] = None,
                 summarize_tool: Optional[Callable] = None):
        self.tools = {
            TaskType.QUERY_SQL: sql_tool,
            TaskType.QUERY_RAG: rag_tool,
            TaskType.CALCULATE: calculate_tool,
            TaskType.COMPARE: compare_tool,
            TaskType.SUMMARIZE: summarize_tool,
        }

    def execute(self, plan: List[PlanStep]) -> List[PlanStep]:
        """
        执行计划，按依赖顺序逐个执行

        Args:
            plan: 计划步骤列表

        Returns:
            执行后的计划（包含结果）
        """
        completed = {}  # step_id -> result

        for step in plan:
            # 检查依赖是否完成
            if step.depends_on:
                for dep_id in step.depends_on:
                    if dep_id not in completed:
                        step.status = "failed"
                        step.result = f"依赖步骤 {dep_id} 未完成"
                        continue

            # 执行步骤
            tool = self.tools.get(step.task_type)
            if tool is None:
                step.status = "failed"
                step.result = f"未找到工具: {step.task_type.value}"
                continue

            step.status = "running"
            try:
                # 将依赖结果注入slots
                context = {"completed_steps": completed}
                result = tool(step.slots, context)
                step.result = result
                step.status = "done"
                completed[step.step_id] = result
            except Exception as e:
                step.status = "failed"
                step.result = str(e)

        return plan


class SmartDataAssistant:
    """智能数据助手 - 整合规划+执行"""

    def __init__(self, sql_tool=None, rag_tool=None):
        self.planner = Planner()
        self.executor = Executor(
            sql_tool=sql_tool,
            rag_tool=rag_tool,
            calculate_tool=self._default_calculate,
            compare_tool=self._default_compare,
            summarize_tool=self._default_summarize,
        )

    def run(self, intent: str, slots: Dict, original_query: str) -> Dict:
        """
        执行完整流程

        Returns:
            {
                "plan": [...],
                "results": [...],
                "final_answer": str,
                "references": [...]
            }
        """
        # 1. 规划
        plan = self.planner.plan(intent, slots, original_query)

        # 2. 执行
        executed_plan = self.executor.execute(plan)

        # 3. 组装结果
        references = []
        for step in executed_plan:
            if step.status == "done" and step.result:
                ref_type = "sql_source" if step.task_type == TaskType.QUERY_SQL else "knowledge_base"
                references.append({
                    "type": ref_type,
                    "step": step.step_id,
                    "description": step.description,
                    "result_preview": str(step.result)[:200] if step.result else "",
                })

        # 4. 生成最终答案
        final_result = executed_plan[-1].result if executed_plan else None
        final_answer = self._format_answer(final_result, original_query)

        return {
            "plan": [
                {
                    "step_id": s.step_id,
                    "task_type": s.task_type.value,
                    "description": s.description,
                    "status": s.status,
                }
                for s in executed_plan
            ],
            "results": [s.result for s in executed_plan],
            "final_answer": final_answer,
            "references": references,
        }

    def _default_calculate(self, slots: Dict, context: Dict) -> Dict:
        """默认计算工具（同比/环比）"""
        return {"operation": "calculate", "slots": slots}

    def _default_compare(self, slots: Dict, context: Dict) -> Dict:
        """默认对比工具"""
        return {"operation": "compare", "slots": slots}

    def _default_summarize(self, slots: Dict, context: Dict) -> Dict:
        """默认总结工具"""
        return {"operation": "summarize", "slots": slots}

    def _format_answer(self, result, query: str) -> str:
        """格式化最终答案"""
        if result is None:
            return "未获取到结果。"
        if isinstance(result, str):
            return result
        if isinstance(result, (list, dict)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)


if __name__ == "__main__":
    # 测试
    def mock_sql(slots, context):
        return {"data": [{"company": "A", "profit": 100}]}

    def mock_rag(slots, context):
        return {"docs": ["研报内容..."]}

    assistant = SmartDataAssistant(sql_tool=mock_sql, rag_tool=mock_rag)

    result = assistant.run(
        intent="QUERY_SINGLE",
        slots={"company": "平安银行", "year": "2023", "subject": "净利润"},
        original_query="平安银行2023年净利润是多少？",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
