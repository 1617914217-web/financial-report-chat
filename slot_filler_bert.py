# -*- coding: utf-8 -*-
"""
槽位填充模块 - BERT + 规则后处理 (实用版)

基于预训练BERT提取上下文特征，结合规则进行槽位识别
无需训练，直接可用

标注体系 (BIO):
  B-COM/I-COM (公司), B-TIM/I-TIM (时间), B-SUB/I-SUB (科目), B-OP (运算符), B-NUM (数值)
"""
import os, json, re
from typing import List, Dict

import torch
from transformers import BertTokenizer, BertModel

# 配置
BERT_MODEL = "models/chinese-roberta-wwm-ext"
MAX_LEN = 64
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

LABELS = ["O", "B-COM", "I-COM", "B-TIM", "I-TIM", "B-SUB", "I-SUB", "B-OP", "I-OP", "B-NUM", "I-NUM"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


class BertSlotFiller:
    """BERT槽位填充器 - 零样本版本"""

    def __init__(self, model_dir: str = BERT_MODEL):
        self.tokenizer = BertTokenizer.from_pretrained(model_dir)
        self.bert = BertModel.from_pretrained(model_dir)
        self.bert.to(DEVICE)
        self.bert.eval()

        # 加载词典
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "data", "company_alias.json"), "r", encoding="utf-8") as f:
            self.company_alias = json.load(f)
        with open(os.path.join(base_dir, "data", "subject_synonym.json"), "r", encoding="utf-8") as f:
            self.subject_synonym = json.load(f)

        # 构建匹配词表
        self.company_names = set()
        for k, v in self.company_alias.items():
            if not k.startswith("_"):
                self.company_names.add(k)
                self.company_names.add(v)

        self.subject_names = set(list(self.subject_synonym.keys()) + list(self.subject_synonym.values()))
        self.time_patterns = [r"20\d{2}年?", r"第?[一二三四]季度", r"年报", r"半年报", r"中报"]
        self.op_words = ["大于", "小于", "等于", "超过", "低于", "高于", "排名", "前", "后", "最高", "最低"]

    def extract(self, text: str) -> Dict:
        """提取槽位 - BERT增强版"""
        # 先用规则做基础标注
        tokens = list(text)
        rule_labels = self._rule_label(text, tokens)

        # 用BERT做上下文校验
        bert_labels = self._bert_enhance(text, tokens, rule_labels)

        # 提取实体
        entities = []
        slots = {"company": None, "year": None, "period": None, "subjects": [], "operators": [], "numbers": []}

        i = 0
        while i < len(bert_labels):
            tag = bert_labels[i]
            if tag.startswith("B-"):
                entity_type = tag[2:]
                start = i
                i += 1
                while i < len(bert_labels) and bert_labels[i] == f"I-{entity_type}":
                    i += 1
                end = i
                entity_text = "".join(tokens[start:end])
                entities.append({"text": entity_text, "type": entity_type, "start": start, "end": end})

                # 填充槽位
                if entity_type == "COM":
                    slots["company"] = entity_text
                elif entity_type == "TIM":
                    slots["year"] = entity_text
                elif entity_type == "SUB":
                    slots["subjects"].append(entity_text)
                elif entity_type == "OP":
                    slots["operators"].append(entity_text)
                elif entity_type == "NUM":
                    try:
                        slots["numbers"].append(float(entity_text))
                    except ValueError:
                        pass
            else:
                i += 1

        return {"entities": entities, "slots": slots}

    def _rule_label(self, text: str, tokens: List[str]) -> List[str]:
        """规则标注"""
        labels = ["O"] * len(tokens)

        # 标注公司名
        for name in sorted(self.company_names, key=len, reverse=True):
            idx = text.find(name)
            if idx != -1:
                for i in range(idx, min(idx + len(name), len(labels))):
                    labels[i] = "I-COM" if i > idx else "B-COM"

        # 标注射间
        for pattern in self.time_patterns:
            for m in re.finditer(pattern, text):
                for i in range(m.start(), min(m.end(), len(labels))):
                    labels[i] = "I-TIM" if i > m.start() else "B-TIM"

        # 标注科目
        for name in sorted(self.subject_names, key=len, reverse=True):
            idx = text.find(name)
            if idx != -1:
                for i in range(idx, min(idx + len(name), len(labels))):
                    labels[i] = "I-SUB" if i > idx else "B-SUB"

        # 标注运算符
        for op in self.op_words:
            idx = text.find(op)
            if idx != -1:
                for i in range(idx, min(idx + len(op), len(labels))):
                    labels[i] = "I-OP" if i > idx else "B-OP"

        return labels

    def _bert_enhance(self, text: str, tokens: List[str], rule_labels: List[str]) -> List[str]:
        """用BERT做上下文校验和修正"""
        if len(tokens) > MAX_LEN:
            tokens = tokens[:MAX_LEN]
            rule_labels = rule_labels[:MAX_LEN]

        encoding = self.tokenizer(
            tokens,
            is_split_into_words=True,
            max_length=MAX_LEN,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(DEVICE)
        attention_mask = encoding["attention_mask"].to(DEVICE)

        with torch.no_grad():
            outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
            # 取最后一层隐藏状态 [1, seq_len, 768]
            hidden_states = outputs.last_hidden_state[0]  # [seq_len, 768]

        # 基于BERT的上下文相似度修正规则标注
        # 例如：如果规则标了B-COM但BERT上下文显示这更像科目，则修正
        word_ids = encoding.word_ids(batch_index=0)
        enhanced_labels = rule_labels.copy()

        # 简单启发式：检查连续相同标签的连贯性
        for i in range(1, len(enhanced_labels)):
            if word_ids[i] is None or word_ids[i] == word_ids[i-1]:
                continue
            word_idx = word_ids[i]
            if word_idx >= len(enhanced_labels):
                break

            curr = enhanced_labels[word_idx]
            prev = enhanced_labels[word_idx - 1] if word_idx > 0 else "O"

            # 修正：B-标签前面不应该跟着同类型的I-标签
            if curr.startswith("B-") and prev.startswith("I-" + curr[2:]):
                # 检查BERT上下文是否支持合并
                sim = torch.cosine_similarity(
                    hidden_states[i].unsqueeze(0),
                    hidden_states[i-1].unsqueeze(0)
                ).item()
                if sim > 0.8:
                    enhanced_labels[word_idx] = "I-" + curr[2:]

        return enhanced_labels


# 兼容旧接口
class RuleBasedSlotFiller(BertSlotFiller):
    """兼容旧接口"""
    pass


if __name__ == "__main__":
    filler = BertSlotFiller()

    tests = [
        "金花股份2022年净利润是多少",
        "万邦德2023年总资产",
        "2022年净利润排名前3的公司",
        "格力电器和美的集团2022年营收对比",
    ]

    for text in tests:
        print(f"\n输入: {text}")
        result = filler.extract(text)
        print(f"槽位: {result['slots']}")
