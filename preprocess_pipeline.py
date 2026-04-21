# -*- coding: utf-8 -*-
"""
问句预处理管道：
1. 文本清洗（去噪声字符）
2. 公司名称/代码标准化
3. 时间词标准化
4. 术语标准化（同义词展开）
5. 意图分类（TF-IDF → LR）
6. 输出结构化表示
"""
import re, os, json
from typing import Dict, List, Optional, Tuple

try:
    from extractors.table_mapper import get_mapper
except ImportError:
    from table_mapper import get_mapper


class QuestionPreprocessor:
    """
    财务问句预处理管道

    输入: "金花股份2022年的总资产是多少"
    输出: {
        "cleaned": "金花股份2022年的总资产是多少",
        "stock_code": "600080",
        "years": ["2022"],
        "standardized_terms": {"总资产": "total_assets"},
        "intent": "balance_sheet",
        "sql_template": "SELECT ... FROM balance_sheet ...",
    }
    """

    # 公司名称 → 代码（从字典加载）
    _company_map = None

    def __init__(self):
        self.mapper = get_mapper()
        self._load_company_map()

    def _load_company_map(self):
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "data", "company_alias.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    # 反向映射：名称→代码
                    self._company_map = {v: k for k, v in raw.items()}
                    # 也保留代码→代码的直接映射
                    for k, v in raw.items():
                        if k.isdigit():
                            self._company_map[k] = v
            except Exception:
                self._company_map = {}
        else:
            self._company_map = {}

    def process(self, question: str) -> Dict:
        """完整预处理流程"""
        cleaned = self._clean(question)
        stock_code = self._extract_stock_code(cleaned)
        years = self._extract_years(cleaned)
        terms = self._extract_terms(cleaned)
        sql, params = self.mapper.map(cleaned)

        return {
            "original": question,
            "cleaned": cleaned,
            "stock_code": stock_code,
            "years": years,
            "standardized_terms": terms,
            "sql": sql,
            "sql_params": params,
        }

    def _clean(self, text: str) -> str:
        """清洗文本"""
        # 去除多余空格
        text = re.sub(r"\s+", " ", text).strip()
        # 去除常见噪声
        text = re.sub(r"[?？]+$", "", text)  # 结尾问号
        text = re.sub(r"^[请问帮我查查看看]+", "", text)  # 开头语气词
        return text

    def _extract_stock_code(self, text: str) -> Optional[str]:
        # 1. 数字代码
        m = re.search(r"(?<!\d)(6\d{5}|0\d{5}|2\d{5}|3\d{5})(?!\d)", text)
        if m:
            return m.group(1)
        # 2. 公司名称查字典
        for name, code in (self._company_map or {}).items():
            if name in text:
                return code if code.isdigit() else None
        return None

    def _extract_years(self, text: str) -> List[str]:
        years = []
        for m in re.finditer(r"(20[12]\d)", text):
            y = m.group(1)
            if y not in years:
                years.append(y)
        return years

    def _extract_terms(self, text: str) -> Dict[str, str]:
        """术语标准化，返回 {原始: 标准} 映射"""
        terms = {}
        dict_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config", "financial_dictionary.json"
        )
        if os.path.exists(dict_path):
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    fd = json.load(f)
                    for orig, std in fd.items():
                        if orig in text:
                            terms[orig] = std
            except Exception:
                pass
        return terms

    def batch_process(self, questions: List[str]) -> List[Dict]:
        """批量处理"""
        return [self.process(q) for q in questions]


if __name__ == "__main__":
    pp = QuestionPreprocessor()
    tests = [
        "金花股份2022年的总资产是多少？",
        "帮我查一下600080的净利润",
        "万邦德毛利率怎么样？",
        "请看乐普医疗2022年的每股收益",
    ]
    for q in tests:
        r = pp.process(q)
        print(f"原始: {q}")
        print(f"清洗: {r['cleaned']}")
        print(f"代码: {r['stock_code']}, 年份: {r['years']}")
        print(f"术语: {r['standardized_terms']}")
        print(f"SQL: {r['sql']}")
        print()
