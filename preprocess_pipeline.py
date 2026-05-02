# -*- coding: utf-8 -*-
"""
问句预处理管道

将用户的自然语言财务问题标准化为结构化表示，供下游意图分类和NL2SQL使用。

处理流程：
1. 全角半角统一
2. 文本清洗（去噪声）
3. 公司名称/代码识别
4. 时间词归一化
5. 术语标准化
6. 输出结构化结果，保留原始→标准映射
"""

import re
import os
import json
from typing import Dict, List, Optional, Tuple

BASE = os.path.dirname(os.path.abspath(__file__))


class PreprocessPipeline:

    def __init__(self):
        self._load_dicts()

    def _load_dicts(self):
        def _load(path):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return {}

        self.company_alias = _load(os.path.join(BASE, "data", "company_alias.json"))
        self.time_dict = _load(os.path.join(BASE, "data", "time_dict.json"))
        self.subject_synonym = _load(os.path.join(BASE, "data", "subject_synonym.json"))
        self.financial_dict = _load(os.path.join(BASE, "config", "financial_dictionary.json"))

        # 构建公司名→代码的反向索引（优先长名匹配）
        self._company_name_to_code = {}
        for code_or_name, std_name in self.company_alias.items():
            if code_or_name.isdigit():
                # "600080" → "ST金花"：代码本身也作为key
                self._company_name_to_code[code_or_name] = code_or_name
            else:
                # "金花股份" → "ST金花"，同时记住原始key对应的代码
                # company_alias里 value 是标准名，需要找到对应的数字代码
                pass

        # 找到标准名对应的代码
        name_to_code = {}
        for k, v in self.company_alias.items():
            if k.startswith('_'):
                continue
            if k.isdigit():
                name_to_code[v] = k  # "ST金花" → "600080"

        for k, v in self.company_alias.items():
            if k.startswith('_'):
                continue
            if k.isdigit():
                self._company_name_to_code[k] = k
            else:
                code = name_to_code.get(v) or name_to_code.get(k)
                if code:
                    self._company_name_to_code[k] = code
                # 也把标准名映射到代码
                code2 = name_to_code.get(v)
                if code2:
                    self._company_name_to_code[v] = code2

        # 按名称长度降序排列，保证长名优先匹配
        self._company_names_sorted = sorted(
            self._company_name_to_code.keys(), key=len, reverse=True
        )

    def process(self, question: str) -> Dict:
        """完整预处理流程"""
        # 1. 全角半角统一
        text = self._fullwidth_to_halfwidth(question)

        # 2. 文本清洗
        text = self._clean(text)

        # 3. 公司识别（在清洗后的文本上匹配）
        stock_code, company_name = self._extract_company(text)

        # 4. 时间词归一化
        years, time_expressions = self._extract_time(text)

        # 5. 术语标准化
        term_mapping = self._standardize_terms(text)

        # 组装标准化文本（用于下游模块）
        normalized = text
        for orig, std in term_mapping.items():
            normalized = normalized.replace(orig, std)

        return {
            "original": question,
            "cleaned": text,
            "normalized": normalized,
            "stock_code": stock_code,
            "company_name": company_name,
            "years": years,
            "time_expressions": time_expressions,
            "term_mapping": term_mapping,
        }

    def batch_process(self, questions: List[str]) -> List[Dict]:
        return [self.process(q) for q in questions]

    # ------------------------------------------------------------------
    # 全角半角统一
    # ------------------------------------------------------------------

    @staticmethod
    def _fullwidth_to_halfwidth(text: str) -> str:
        """全角字符转半角（数字、字母、标点）"""
        result = []
        for ch in text:
            code = ord(ch)
            # 全角空格
            if code == 0x3000:
                result.append(" ")
            # 全角数字 ０-９ → 0-9
            elif 0xFF10 <= code <= 0xFF19:
                result.append(chr(code - 0xFEE0))
            # 全角大写 Ａ-Ｚ → A-Z
            elif 0xFF21 <= code <= 0xFF3A:
                result.append(chr(code - 0xFEE0))
            # 全角小写 ａ-ｚ → a-z
            elif 0xFF41 <= code <= 0xFF5A:
                result.append(chr(code - 0xFEE0))
            # 全角标点 → 半角（常见财务标点）
            elif ch == "\uff1a":
                result.append(":")
            elif ch == "\uff1b":
                result.append(";")
            elif ch == "\uff0c":
                result.append(",")
            elif ch == "\uff0e":
                result.append(".")
            elif ch == "\uff01":
                result.append("!")
            elif ch == "\uff1f":
                result.append("?")
            elif ch == "\uff08":
                result.append("(")
            elif ch == "\uff09":
                result.append(")")
            elif ch == "\u2018" or ch == "\u201c":
                result.append('"')
            elif ch == "\u2019" or ch == "\u201d":
                result.append('"')
            elif ch == "\u3001":
                result.append(",")
            elif ch == "\u3002":
                result.append(".")
            else:
                result.append(ch)
        return "".join(result)

    # ------------------------------------------------------------------
    # 文本清洗
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """清洗噪声"""
        # 去除多余空格
        text = re.sub(r"\s+", " ", text).strip()
        # 去除URL
        text = re.sub(r"https?://\S+", "", text)
        # 去除HTML标签
        text = re.sub(r"<[^>]+>", "", text)
        # 去除开头语气词
        text = re.sub(r"^[请问帮我查查看看告诉我分析一下]+", "", text)
        # 去除结尾标点
        text = re.sub(r"[？?！!。.]+$", "", text).strip()
        return text

    # ------------------------------------------------------------------
    # 公司识别
    # ------------------------------------------------------------------

    def _extract_company(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """识别公司代码和名称"""
        # 1. 精确匹配公司名称（长名优先）
        for name in self._company_names_sorted:
            if name in text:
                code = self._company_name_to_code[name]
                return code, name

        # 2. 匹配6位数字代码
        m = re.search(r"(?<!\d)(6\d{5}|0\d{5}|3\d{5})(?!\d)", text)
        if m:
            code = m.group(1)
            return code, self.company_alias.get(code, code)

        return None, None

    # ------------------------------------------------------------------
    # 时间词归一化
    # ------------------------------------------------------------------

    def _extract_time(self, text: str) -> Tuple[List[str], Dict[str, str]]:
        """提取并归一化时间表达"""
        years = []
        time_expressions = {}

        # 先匹配具体年份 20XX 或 19XX
        for m in re.finditer(r"((?:19|20)\d{2})\s*年?", text):
            year = m.group(1)
            if year not in years:
                years.append(year)

        # 匹配季度
        quarter_map = {
            "一季度": "Q1", "一季报": "Q1", "第一季度": "Q1",
            "二季度": "Q2", "中报": "Q2", "半年报": "Q2", "上半年": "Q2",
            "三季度": "Q3", "三季报": "Q3", "第三季度": "Q3",
            "四季度": "Q4", "年报": "Q4", "下半年": "Q4",
        }
        for cn, en in quarter_map.items():
            if cn in text:
                time_expressions[cn] = en

        # 匹配时间词典中的表达
        for cn, std in self.time_dict.items():
            if cn in text:
                time_expressions[cn] = std

        # 相对时间词（需要参考时间，暂标记）
        relative_time = {
            "去年": "last_year",
            "今年": "this_year",
            "上年同期": "prior_period",
            "去年同期": "prior_period",
            "本期": "current_period",
            "本报告期": "current_period",
            "本年": "current_period",
        }
        for cn, std in relative_time.items():
            if cn in text:
                time_expressions[cn] = std

        return years, time_expressions

    # ------------------------------------------------------------------
    # 术语标准化
    # ------------------------------------------------------------------

    def _standardize_terms(self, text: str) -> Dict[str, str]:
        """术语标准化，返回 {原文: 标准词} 映射"""
        mapping = {}

        # 先用 subject_synonym（同义词→标准财务术语）
        for alias, std in self.subject_synonym.items():
            if alias in text and alias not in mapping:
                mapping[alias] = std

        # 再用 financial_dictionary（中文财务术语→英文字段名）
        for cn_term, en_field in self.financial_dict.items():
            if cn_term in text and cn_term not in mapping:
                mapping[cn_term] = en_field

        return mapping


# 保持向后兼容的别名
QuestionPreprocessor = PreprocessPipeline


if __name__ == "__main__":
    pp = PreprocessPipeline()
    tests = [
        "金花股份2022年的总资产是多少？",
        "帮我查一下600080的净利润",
        "万邦德毛利率怎么样？",
        "请看乐普医疗2022年的每股收益",
        "格力电器去年和今年同期的营业收入对比",
        "比亚迪２０２３年上半年收入多少",
        "万科Ａ的资产负债率是多少",
    ]
    for q in tests:
        r = pp.process(q)
        print(f"原始: {q}")
        print(f"  清洗: {r['cleaned']}")
        print(f"  标准化: {r['normalized']}")
        print(f"  公司: {r['company_name']} ({r['stock_code']})")
        print(f"  年份: {r['years']}")
        print(f"  时间: {r['time_expressions']}")
        print(f"  术语: {r['term_mapping']}")
        print()
