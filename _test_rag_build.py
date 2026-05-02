# -*- coding: utf-8 -*-
"""
测试RAG知识库构建 - 用一份研报验证
"""
import os, sys

base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)

from rag_knowledge_base import KnowledgeBase

# 研报目录
reports_dir = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件5：研报数据\个股研报"

# 找一份研报测试
pdf_files = []
for root, dirs, files in os.walk(reports_dir):
    for f in files:
        if f.endswith('.pdf'):
            pdf_files.append(os.path.join(root, f))
            if len(pdf_files) >= 3:
                break
    if len(pdf_files) >= 3:
        break

print(f"找到 {len(pdf_files)} 份研报，开始测试...")
print(f"示例: {os.path.basename(pdf_files[0])}")

# 初始化RAG（使用本地模型）
kb = KnowledgeBase(
    embedding_model="BAAI/bge-large-zh-v1.5",
)

# 只测试第一份
import tempfile, shutil
# 复制到临时目录（add_documents需要目录）
tmp_dir = tempfile.mkdtemp()
for pdf_path in pdf_files[:1]:
    print(f"\n处理: {os.path.basename(pdf_path)}")
    try:
        shutil.copy(pdf_path, tmp_dir)
        kb.add_documents(tmp_dir)
        print("  解析完成")
    except Exception as e:
        print(f"  错误: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# 测试检索
print("\n测试检索: '净利润增长原因'")
results = kb.search("净利润增长原因", top_k=3)
for i, r in enumerate(results, 1):
    print(f"\n[{i}] 分数: {r.get('rerank_score', r.get('score', 0)):.4f}")
    print(f"    来源: {os.path.basename(r['metadata'].get('source', ''))}")
    print(f"    内容: {r['text'][:150]}...")

print("\nRAG测试完成!")
