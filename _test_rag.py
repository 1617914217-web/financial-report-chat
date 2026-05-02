# -*- coding: utf-8 -*-
"""测试RAG知识库构建"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os

os.chdir(r'C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\任务B_财报智能抽取')
sys.path.insert(0, '.')

from rag_knowledge_base import KnowledgeBase

# 使用轻量级模型测试（避免下载大模型）
kb = KnowledgeBase(
    db_path="./chroma_db_test",
    embedding_model="shibing624/text2vec-base-chinese",  # 轻量级中文模型
)

pdf_dir = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件5：研报数据\个股研报"

if os.path.exists(pdf_dir):
    # 只处理前5个PDF做测试
    print("开始构建知识库...")
    kb.add_documents(pdf_dir)
    print("\n统计:", kb.get_stats())
else:
    print(f"目录不存在: {pdf_dir}")
