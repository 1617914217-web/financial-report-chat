# -*- coding: utf-8 -*-
"""
RAG知识库构建模块

流程：
1. 解析附件5研报PDF → 文本
2. 语义切分（按段落/标题层级）
3. BAAI/bge-large-zh-v1.5 向量化
4. 存入Chroma向量数据库
5. 检索：混合检索(Dense+BM25) → Rerank精排

依赖：chromadb, sentence-transformers, rank-bm25
"""
import os, re, json, hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi


@dataclass
class Chunk:
    """文本块"""
    text: str
    source: str          # PDF文件名
    page: int            # 页码
    chunk_type: str      # 'text' | 'table' | 'heading'
    heading_path: str    # 标题路径，如 "行业概述/市场现状"


class PDFParser:
    """PDF解析器 - 基于PyMuPDF，保留结构信息"""

    def __init__(self):
        pass

    def parse(self, pdf_path: str) -> List[Dict]:
        """
        解析PDF，返回段落列表
        每个段落包含：text, page, bbox, font_size, is_heading
        """
        doc = fitz.open(pdf_path)
        paragraphs = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue
                text = ""
                max_font_size = 0
                for line in block["lines"]:
                    for span in line["spans"]:
                        text += span["text"]
                        max_font_size = max(max_font_size, span["size"])

                text = text.strip()
                if not text or len(text) < 10:
                    continue

                # 判断是否为标题（字体较大或包含编号）
                is_heading = max_font_size > 12 or re.match(r'^\d+[\.、]', text)

                paragraphs.append({
                    "text": text,
                    "page": page_num + 1,
                    "font_size": max_font_size,
                    "is_heading": is_heading,
                })

        doc.close()
        return paragraphs


class SemanticChunker:
    """语义切分器 - 按标题层级和语义完整性切分"""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, paragraphs: List[Dict], source: str) -> List[Chunk]:
        """
        将段落列表切分为语义块
        策略：
        1. 标题单独成块
        2. 正文按chunk_size切分，保持段落完整性
        3. 记录标题路径用于上下文
        """
        chunks = []
        current_heading = ""
        buffer = []
        buffer_len = 0

        for para in paragraphs:
            text = para["text"]

            # 标题单独成块
            if para["is_heading"]:
                # 先刷新buffer
                if buffer:
                    chunks.extend(self._flush_buffer(buffer, source, current_heading))
                    buffer = []
                    buffer_len = 0
                # 更新当前标题
                current_heading = text
                # 标题本身也作为一个块
                chunks.append(Chunk(
                    text=text,
                    source=source,
                    page=para["page"],
                    chunk_type="heading",
                    heading_path=current_heading,
                ))
                continue

            # 正文累积
            buffer.append(text)
            buffer_len += len(text)

            # 超过chunk_size则切分
            if buffer_len >= self.chunk_size:
                chunks.extend(self._flush_buffer(buffer, source, current_heading))
                buffer = []
                buffer_len = 0

        # 刷新剩余buffer
        if buffer:
            chunks.extend(self._flush_buffer(buffer, source, current_heading))

        return chunks

    def _flush_buffer(self, buffer: List[str], source: str, heading: str) -> List[Chunk]:
        """将buffer内容切分为固定大小的块"""
        text = "\n".join(buffer)
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            # 尽量在句号或换行处切断
            if end < len(text):
                for i in range(end, max(start + self.chunk_size // 2, end - 100), -1):
                    if i < len(text) and text[i] in '。\n':
                        end = i + 1
                        break

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= 20:
                chunks.append(Chunk(
                    text=chunk_text,
                    source=source,
                    page=0,  # 简化处理
                    chunk_type="text",
                    heading_path=heading,
                ))
            start = end - self.overlap

        return chunks


class KnowledgeBase:
    """知识库 - 向量存储 + 混合检索 + Rerank"""

    def __init__(self,
                 db_path: str = "./chroma_db",
                 embedding_model: str = "BAAI/bge-large-zh-v1.5",
                 reranker_model: Optional[str] = None):
        """
        Args:
            db_path: ChromaDB持久化路径
            embedding_model: 向量化模型名称
            reranker_model: 重排模型名称（如BAAI/bge-reranker-v2-m3）
        """
        self.db_path = db_path
        self.embedding_model_name = embedding_model
        self.reranker_model_name = reranker_model

        # 初始化ChromaDB
        self.client = chromadb.Client(Settings(
            persist_directory=db_path,
            anonymized_telemetry=False,
        ))
        self.collection = self.client.get_or_create_collection(
            name="research_reports",
            metadata={"hnsw:space": "cosine"}
        )

        # 加载向量化模型
        print(f"加载向量化模型: {embedding_model}")
        # 优先使用本地路径
        local_path = os.path.join(os.path.dirname(__file__), "models", "BAAI", "bge-large-zh-v1___5")
        if os.path.exists(local_path):
            print(f"使用本地模型: {local_path}")
            self.encoder = SentenceTransformer(local_path, trust_remote_code=True, local_files_only=True)
        else:
            try:
                self.encoder = SentenceTransformer(embedding_model, trust_remote_code=True)
            except Exception as e:
                print(f"模型加载失败: {e}")
                raise

        # 加载重排模型（如有）
        self.reranker = None
        if reranker_model:
            print(f"加载重排模型: {reranker_model}")
            try:
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder(reranker_model, trust_remote_code=True)
            except Exception as e:
                print(f"重排模型加载失败: {e}")

        # BM25索引
        self.bm25 = None
        self.bm25_corpus = []

    def add_documents(self, pdf_dir: str):
        """批量添加PDF文档到知识库"""
        parser = PDFParser()
        chunker = SemanticChunker(chunk_size=500, overlap=50)

        all_chunks = []
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        print(f"发现 {len(pdf_files)} 个PDF文件")

        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            print(f"处理: {pdf_file}")

            try:
                paragraphs = parser.parse(pdf_path)
                chunks = chunker.chunk(paragraphs, source=pdf_file)
                all_chunks.extend(chunks)
                print(f"  生成 {len(chunks)} 个chunks")
            except Exception as e:
                print(f"  解析失败: {e}")

        print(f"\n总计 {len(all_chunks)} 个chunks，开始编码...")

        # 批量编码
        batch_size = 32
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            texts = [c.text for c in batch]
            embeddings = self.encoder.encode(texts, normalize_embeddings=True)

            ids = [self._hash(c.text + c.source) for c in batch]
            metadatas = [{
                "source": c.source,
                "page": c.page,
                "chunk_type": c.chunk_type,
                "heading_path": c.heading_path,
            } for c in batch]

            self.collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                documents=texts,
            )
            print(f"  已编码 {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

        # 构建BM25索引
        self._build_bm25(all_chunks)
        print("知识库构建完成！")

    def _build_bm25(self, chunks: List[Chunk]):
        """构建BM25索引"""
        self.bm25_corpus = chunks
        tokenized = [self._tokenize(c.text) for c in chunks]
        self.bm25 = BM25Okapi(tokenized)
        print(f"BM25索引构建完成，{len(chunks)} 个文档")

    def _tokenize(self, text: str) -> List[str]:
        """简单中文分词（按字符）"""
        return list(text)

    def _hash(self, text: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(text.encode()).hexdigest()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        混合检索 + Rerank
        1. Dense检索召回top-20
        2. BM25检索召回top-20
        3. 合并去重
        4. Rerank精排取top-k
        """
        # Dense检索
        query_embedding = self.encoder.encode([query], normalize_embeddings=True)
        dense_results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=20,
        )

        dense_docs = []
        if dense_results["ids"]:
            for i, doc_id in enumerate(dense_results["ids"][0]):
                dense_docs.append({
                    "id": doc_id,
                    "text": dense_results["documents"][0][i],
                    "metadata": dense_results["metadatas"][0][i],
                    "score": dense_results["distances"][0][i] if dense_results["distances"] else 0,
                    "source": "dense",
                })

        # BM25检索
        bm25_docs = []
        if self.bm25:
            tokenized_query = self._tokenize(query)
            scores = self.bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:20]
            for idx in top_indices:
                chunk = self.bm25_corpus[idx]
                bm25_docs.append({
                    "id": self._hash(chunk.text + chunk.source),
                    "text": chunk.text,
                    "metadata": {
                        "source": chunk.source,
                        "page": chunk.page,
                        "chunk_type": chunk.chunk_type,
                        "heading_path": chunk.heading_path,
                    },
                    "score": scores[idx],
                    "source": "bm25",
                })

        # 合并去重（按id）
        seen = set()
        merged = []
        for doc in dense_docs + bm25_docs:
            if doc["id"] not in seen:
                seen.add(doc["id"])
                merged.append(doc)

        # Rerank精排
        if self.reranker and len(merged) > 0:
            pairs = [[query, doc["text"]] for doc in merged]
            rerank_scores = self.reranker.predict(pairs)
            for doc, score in zip(merged, rerank_scores):
                doc["rerank_score"] = float(score)
            merged.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        else:
            # 无reranker时按dense score排序
            merged.sort(key=lambda x: x["score"])

        return merged[:top_k]

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        count = self.collection.count()
        return {
            "total_documents": count,
            "embedding_model": self.embedding_model_name,
            "reranker_model": self.reranker_model_name,
            "db_path": self.db_path,
        }


if __name__ == "__main__":
    # 测试
    kb = KnowledgeBase(
        db_path="./chroma_db",
        embedding_model="BAAI/bge-large-zh-v1.5",
        # reranker_model="BAAI/bge-reranker-v2-m3",  # 如需重排取消注释
    )

    # 添加文档（示例路径）
    pdf_dir = r"C:\Users\Administrator\开发项目\PycharmProjects\PythonProject\正式数据\附件5：研报数据\个股研报"
    if os.path.exists(pdf_dir):
        kb.add_documents(pdf_dir)
        print("\n知识库统计:", kb.get_stats())

        # 测试检索
        query = "2024年净利润增长"
        results = kb.search(query, top_k=3)
        print(f"\n查询: {query}")
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] {r['metadata']['source']} (score: {r.get('rerank_score', r['score']):.3f})")
            print(f"    {r['text'][:150]}...")
    else:
        print(f"PDF目录不存在: {pdf_dir}")
