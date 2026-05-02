# -*- coding: utf-8 -*-
"""
FastAPI 后端服务
提供前端需要的 API 接口
"""
import os, sys
import pymysql
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# 初始化问答系统
qa = FinancialQA()
validator = SQLValidator()

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
    return {"status": "ok", "service": "Financial Report QA API"}


@app.post("/chat")
def chat(req: ChatRequest):
    """对话式问答"""
    try:
        result = qa.ask(req.question)
        return {
            "answer": result.get("conclusion", result.get("answer", "")),
            "sql": result.get("sql", ""),
            "data": result.get("data"),
            "chart_path": result.get("chart_path"),
            "intent": result.get("intent"),
            "slots": result.get("slots"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/intent")
def intent(req: ChatRequest):
    """意图识别"""
    try:
        from predict_intent import predict as predict_intent
        intent_label, confidence = predict_intent(req.question)
        return {"intent": intent_label, "confidence": confidence}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sql")
def execute_sql(req: SQLRequest):
    """执行 SQL 查询"""
    if not validator.validate(req.sql):
        raise HTTPException(status_code=400, detail="SQL 安全检查未通过")
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(req.sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        return {
            "columns": columns,
            "rows": rows,
            "rowCount": len(rows),
            "sql": req.sql,
        }
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
        return {"tables": tables}
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
        return {
            "columns": columns,
            "rows": rows,
            "rowCount": len(rows),
            "sql": f"SELECT * FROM {table_name} LIMIT {limit}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
