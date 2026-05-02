# -*- coding: utf-8 -*-
"""
槽位填充模块 (Slot Filling)

规则版：基于正则 + 词典匹配，提取BIO标注实体
实体类型：公司(COM)、时间(TIM)、科目(SUB)、运算符(OP)、数值(NUM)

注：BERT+BiLSTM+CRF版本作为升级路径，当前先用规则版保证系统可运行。
"""
import re, json, os
from typing import Dict, List, Tuple, Optional


class RuleBasedSlotFiller:
    """基于规则的槽位填充器"""

    def __init__(self, project_dir: str = None):
        self.project_dir = project_dir or os.path.dirname(os.path.abspath(__file__))
        self._load_dictionaries()

    def _load_dictionaries(self):
        """加载词典"""
        # 公司别名
        ca_path = os.path.join(self.project_dir, "data", "company_alias.json")
        if os.path.exists(ca_path):
            with open(ca_path, "r", encoding="utf-8") as f:
                self.company_alias = json.load(f)
        else:
            self.company_alias = {}

        # 时间词
        td_path = os.path.join(self.project_dir, "data", "time_dict.json")
        if os.path.exists(td_path):
            with open(td_path, "r", encoding="utf-8") as f:
                self.time_dict = json.load(f)
        else:
            self.time_dict = {}

        # 科目同义词
        ss_path = os.path.join(self.project_dir, "data", "subject_synonym.json")
        if os.path.exists(ss_path):
            with open(ss_path, "r", encoding="utf-8") as f:
                self.subject_synonym = json.load(f)
        else:
            self.subject_synonym = {}

        # 财务词典（中文术语 -> 数据库字段）
        fd_path = os.path.join(self.project_dir, "config", "financial_dictionary.json")
        if os.path.exists(fd_path):
            with open(fd_path, "r", encoding="utf-8") as f:
                self.financial_dict = json.load(f)
        else:
            self.financial_dict = {}

        # 构建公司名列表（按长度降序，优先匹配长名）
        # 排除内部元数据键
        alias_keys = [k for k in self.company_alias.keys() if not k.startswith('_')]
        alias_vals = [v for k, v in self.company_alias.items() if not k.startswith('_')]
        self.company_names = sorted(
            list(alias_keys) + list(alias_vals),
            key=len, reverse=True
        )
        # 去重
        self.company_names = list(dict.fromkeys(self.company_names))
        # 公司名 -> 股票代码映射
        self.company_to_code = self.company_alias.get("_code_map", {})

        # 科目词列表
        self.subject_terms = sorted(
            list(self.subject_synonym.keys()) + list(self.subject_synonym.values()) + list(self.financial_dict.keys()),
            key=len, reverse=True
        )
        self.subject_terms = list(dict.fromkeys(self.subject_terms))

    def extract(self, question: str) -> dict:
        """
        提取槽位
        返回: {
            "entities": [{"text": str, "type": str, "start": int, "end": int, "normalized": str}],
            "slots": {"company": str, "year": str, "period": str, "subjects": [str], "operators": [str], "numbers": [float]}
        }
        """
        entities = []
        slots = {
            "company": None,
            "year": None,
            "period": None,
            "subjects": [],
            "operators": [],
            "numbers": [],
        }

        # 1. 提取公司名
        com_result = self._extract_company(question)
        if com_result:
            entities.append({
                "text": com_result["text"],
                "type": "COM",
                "start": com_result["start"],
                "end": com_result["end"],
                "normalized": com_result["normalized"],
            })
            slots["company"] = com_result["normalized"]
            slots["company_code"] = com_result.get("code", "")

        # 2. 提取年份和报告期
        time_result = self._extract_time(question)
        if time_result:
            for tr in time_result:
                entities.append({
                    "text": tr["text"],
                    "type": "TIM",
                    "start": tr["start"],
                    "end": tr["end"],
                    "normalized": tr["normalized"],
                })
                if tr["kind"] == "year":
                    slots["year"] = tr["normalized"]
                elif tr["kind"] == "period":
                    slots["period"] = tr["normalized"]

        # 3. 提取科目
        sub_results = self._extract_subjects(question)
        for sr in sub_results:
            entities.append({
                "text": sr["text"],
                "type": "SUB",
                "start": sr["start"],
                "end": sr["end"],
                "normalized": sr["normalized"],
            })
            slots["subjects"].append(sr["normalized"])

        # 4. 提取运算符
        op_results = self._extract_operators(question)
        for or_ in op_results:
            entities.append({
                "text": or_["text"],
                "type": "OP",
                "start": or_["start"],
                "end": or_["end"],
                "normalized": or_["text"],
            })
            slots["operators"].append(or_["text"])

        # 5. 提取数值
        num_results = self._extract_numbers(question)
        for nr in num_results:
            entities.append({
                "text": nr["text"],
                "type": "NUM",
                "start": nr["start"],
                "end": nr["end"],
                "normalized": nr["value"],
            })
            slots["numbers"].append(nr["value"])

        return {"entities": entities, "slots": slots}

    def _extract_company(self, text: str) -> Optional[dict]:
        """提取公司名"""
        for name in self.company_names:
            idx = text.find(name)
            if idx != -1:
                # 标准化：优先用别名映射的值
                normalized = self.company_alias.get(name, name)
                # 获取股票代码
                code = self.company_to_code.get(normalized, "")
                return {"text": name, "start": idx, "end": idx + len(name), "normalized": normalized, "code": code}
        # 尝试股票代码匹配
        m = re.search(r'\b(\d{6})\b', text)
        if m:
            code = m.group(1)
            # 反向查找
            for alias, std in self.company_alias.items():
                if alias.startswith('_'):
                    continue
                if code in alias or code in std:
                    return {"text": code, "start": m.start(), "end": m.end(), "normalized": std, "code": code}
            return {"text": code, "start": m.start(), "end": m.end(), "normalized": code, "code": code}
        return None

    def _extract_time(self, text: str) -> List[dict]:
        """提取时间信息"""
        results = []

        # 年份匹配：2022年、2022
        for m in re.finditer(r'(20\d{2})\s*年?', text):
            year = m.group(1)
            results.append({
                "text": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "normalized": year,
                "kind": "year",
            })

        # 报告期匹配：年报、半年报、季报、Q1、H1、FY
        period_map = {
            r'年报|年度报告': 'FY',
            r'半年报|半年度报告|中期报告': 'H1',
            r'一季报|第一季度|Q1': 'Q1',
            r'三季报|第三季度|Q3': 'Q3',
            r'季报|季度报告': 'Q',
        }
        for pattern, ptype in period_map.items():
            for m in re.finditer(pattern, text):
                results.append({
                    "text": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "normalized": ptype,
                    "kind": "period",
                })

        # 时间词词典匹配
        for word, mapped in self.time_dict.items():
            idx = text.find(word)
            if idx != -1:
                kind = "period" if "Q" in mapped or "H" in mapped or "FY" in mapped else "year"
                results.append({
                    "text": word,
                    "start": idx,
                    "end": idx + len(word),
                    "normalized": mapped,
                    "kind": kind,
                })

        # 去重（按位置）
        seen = set()
        unique = []
        for r in results:
            key = (r["start"], r["end"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _extract_subjects(self, text: str) -> List[dict]:
        """提取财务科目"""
        results = []
        for term in self.subject_terms:
            idx = text.find(term)
            if idx != -1:
                # 标准化
                normalized = self.subject_synonym.get(term, term)
                # 如果标准化后还在同义词里，再查一次
                normalized = self.subject_synonym.get(normalized, normalized)
                results.append({
                    "text": term,
                    "start": idx,
                    "end": idx + len(term),
                    "normalized": normalized,
                })
        # 去重
        seen = set()
        unique = []
        for r in results:
            key = (r["start"], r["end"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _extract_operators(self, text: str) -> List[dict]:
        """提取运算符/比较词"""
        ops = ["大于", "小于", "等于", "超过", "低于", "高于", "不少于", "不超过",
               "最高", "最低", "最多", "最少", "排名", "前", "后"]
        results = []
        for op in ops:
            idx = text.find(op)
            if idx != -1:
                results.append({"text": op, "start": idx, "end": idx + len(op)})
        return results

    def _extract_numbers(self, text: str) -> List[dict]:
        """提取数值"""
        results = []
        # 匹配数字（支持千分位逗号、小数）
        pattern = r'[\d,]+\.?\d*'
        for m in re.finditer(pattern, text):
            val_str = m.group(0).replace(',', '')
            try:
                val = float(val_str)
                results.append({"text": m.group(0), "start": m.start(), "end": m.end(), "value": val})
            except ValueError:
                pass
        return results


if __name__ == "__main__":
    filler = RuleBasedSlotFiller()
    tests = [
        "金花股份2022年净利润是多少",
        "2022年ROE最高的5家公司",
        "万邦德2022年毛利率和净利率分别是多少",
        "哪家公司2022年总资产超过100亿",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        r = filler.extract(q)
        print(f"  Slots: {r['slots']}")
        for e in r['entities']:
            print(f"    {e['type']}: {e['text']} -> {e['normalized']}")
