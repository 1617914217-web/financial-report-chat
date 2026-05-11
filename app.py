# -*- coding: utf-8 -*-
"""
FastAPI 后端服务
提供前端需要的 API 接口
"""
import os, sys
import json
import pymysql
from decimal import Decimal
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def jsonable(obj):
    """将对象转为 JSON 可序列化的格式"""
    return json.loads(json.dumps(obj, cls=DecimalEncoder, ensure_ascii=False))

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from pipeline import FinancialQA
from sql_validator import SQLValidator

app = FastAPI(title="Financial Report QA API", version="1.0")

# CORS 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化问答系统（延迟加载，确保工作目录正确）
_qa_instance = None
_validator_instance = None

def get_qa():
    global _qa_instance
    if _qa_instance is None:
        _qa_instance = FinancialQA()
    return _qa_instance

def get_validator():
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = SQLValidator()
    return _validator_instance

# MySQL 配置
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "181415157Ak.",
    "database": "intelligent_data_query",
    "charset": "utf8mb4",
}


class ChatRequest(BaseModel):
    question: str


class SQLRequest(BaseModel):
    sql: str


@app.get("/")
def root():
    return JSONResponse(content={"status": "ok", "service": "Financial Report QA API"})


@app.get("/health")
def health():
    return JSONResponse(content={"status": "healthy", "version": "1.0"})


@app.post("/chat")
def chat(req: ChatRequest):
    """对话式问答"""
    try:
        result = get_qa().ask(req.question)
        data = result.get("data")
        # 包装成前端期望的 QueryResult 格式
        if data and isinstance(data, list) and len(data) > 0:
            query_result = {
                "columns": list(data[0].keys()),
                "rows": data,
                "rowCount": len(data),
                "sql": result.get("sql", ""),
            }
        else:
            query_result = None
        # 构建思考过程
        steps = []
        preprocessed = result.get("preprocessed", "")
        if isinstance(preprocessed, dict):
            steps.append({"step": "文本预处理", "detail": f"原文 → 标准化：{preprocessed.get('normalized', '')}，清洗：{preprocessed.get('cleaned', '')}"})
        intent = result.get("intent", "")
        confidence = result.get("intent_confidence", 0)
        steps.append({"step": "意图分类", "detail": f"识别为「{intent}」，置信度 {confidence:.1%}"})
        slots = result.get("slots", {})
        slot_desc = ", ".join(f"{k}={v}" for k, v in slots.items() if v) if slots else "未提取到槽位"
        steps.append({"step": "槽位填充", "detail": slot_desc})
        sql = result.get("sql", "")
        if sql:
            steps.append({"step": "NL2SQL生成", "detail": sql})
        sql_valid = result.get("sql_valid", False)
        steps.append({"step": "SQL校验", "detail": "通过" if sql_valid else "未通过"})
        if data:
            steps.append({"step": "数据查询", "detail": f"返回 {len(data)} 条记录"})
        conclusion = result.get("conclusion", "")
        if conclusion:
            steps.append({"step": "结论生成", "detail": conclusion})
        if result.get("error"):
            steps.append({"step": "错误", "detail": result["error"]})

        return JSONResponse(content=jsonable({
            "answer": conclusion or "未查询到相关数据。",
            "sql": sql,
            "data": query_result,
            "chart_path": result.get("chart_path"),
            "intent": intent,
            "slots": slots,
            "steps": steps,
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/intent")
def intent(req: ChatRequest):
    """意图识别"""
    try:
        from predict_intent import predict as predict_intent
        intent_label, confidence = predict_intent(req.question)
        return JSONResponse(content={"intent": intent_label, "confidence": confidence})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sql")
def execute_sql(req: SQLRequest):
    """执行 SQL 查询"""
    if not get_validator().validate(req.sql):
        raise HTTPException(status_code=400, detail="SQL 安全检查未通过")
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(req.sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        return JSONResponse(content=jsonable({
            "columns": columns,
            "rows": rows,
            "rowCount": len(rows),
            "sql": req.sql,
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tables")
def get_tables():
    """获取数据库表列表"""
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [row[0] for row in cur.fetchall()]
        conn.close()
        return JSONResponse(content={"tables": tables})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tables/{table_name}/preview")
def preview_table(table_name: str, limit: int = 5):
    """预览表数据"""
    safe_tables = ["balance_sheet", "income_sheet", "stock_income_statement_data",
                   "core_performance_indicators_sheet", "raw_extracted"]
    if table_name not in safe_tables:
        raise HTTPException(status_code=400, detail="不安全的表名")
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(f"SELECT * FROM `{table_name}` LIMIT %s", (limit,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        return JSONResponse(content=jsonable({
            "columns": columns,
            "rows": rows,
            "rowCount": len(rows),
            "sql": f"SELECT * FROM {table_name} LIMIT {limit}",
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
