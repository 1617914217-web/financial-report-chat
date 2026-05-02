# -*- coding: utf-8 -*-
"""
槽位填充模块 - BERT + BiLSTM + CRF (高级版)

基于transformers的BERT编码 + BiLSTM序列建模 + CRF解码
标注体系 (BIO):
  B-COM/I-COM (公司), B-TIM/I-TIM (时间), B-SUB/I-SUB (科目), B-OP (运算符), B-NUM (数值)

训练数据格式: JSONL，每行 {"tokens": ["金花", "股份", "2022", "年", "净利润"], "labels": ["B-COM", "I-COM", "B-TIM", "I-TIM", "B-SUB"]}
"""
import os, json, re
from typing import List, Dict, Tuple, Optional
from collections import Counter

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertModel, get_linear_schedule_with_warmup
from seqeval.metrics import f1_score, classification_report


# ============ 配置 ============
BERT_MODEL = "hfl/chinese-roberta-wwm-ext"  # 中文RoBERTa-wwm，效果比bert-base-chinese好
MAX_LEN = 128
BATCH_SIZE = 16
LR = 2e-5
EPOCHS = 10
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

LABELS = ["O", "B-COM", "I-COM", "B-TIM", "I-TIM", "B-SUB", "I-SUB", "B-OP", "I-OP", "B-NUM", "I-NUM"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


# ============ CRF 层 ============
class CRF(nn.Module):
    """条件随机场解码层"""

    def __init__(self, num_tags: int):
        super().__init__()
        self.num_tags = num_tags
        # 转移矩阵 [from_tag, to_tag]
        self.transitions = nn.Parameter(torch.randn(num_tags, num_tags))
        # START 和 END 标签的转移
        self.start_transitions = nn.Parameter(torch.randn(num_tags))
        self.end_transitions = nn.Parameter(torch.randn(num_tags))

    def forward(self, emissions: torch.Tensor, tags: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """计算负对数似然（训练用）"""
        log_likelihood = self._compute_log_likelihood(emissions, tags, mask)
        return -log_likelihood.mean()

    def decode(self, emissions: torch.Tensor, mask: torch.Tensor) -> List[List[int]]:
        """Viterbi解码（推理用）"""
        return self._viterbi_decode(emissions, mask)

    def _compute_log_likelihood(self, emissions, tags, mask):
        """计算给定标签序列的log概率"""
        batch_size, seq_len, num_tags = emissions.shape

        # 发射分数
        score = torch.zeros(batch_size, device=emissions.device)
        score += self.start_transitions[tags[:, 0]]
        score += emissions[torch.arange(batch_size), 0, tags[:, 0]]

        for t in range(1, seq_len):
            valid = mask[:, t]
            trans = self.transitions[tags[:, t - 1], tags[:, t]]
            emit = emissions[torch.arange(batch_size), t, tags[:, t]]
            score += (trans + emit) * valid

        # 最后一个有效位置的END转移
        last_valid = mask.long().sum(dim=1) - 1
        score += self.end_transitions[tags[torch.arange(batch_size), last_valid]]

        # 计算配分函数（所有路径的log-sum-exp）
        log_partition = self._compute_log_partition(emissions, mask)

        return score - log_partition

    def _compute_log_partition(self, emissions, mask):
        """前向算法计算配分函数"""
        batch_size, seq_len, num_tags = emissions.shape

        # 初始化
        alpha = self.start_transitions + emissions[:, 0, :]  # [batch, num_tags]

        for t in range(1, seq_len):
            valid = mask[:, t:t + 1]  # [batch, 1]
            # [batch, num_tags, 1] + [1, num_tags, num_tags] = [batch, num_tags, num_tags]
            emit = emissions[:, t:t + 1, :].transpose(1, 2)  # [batch, num_tags, 1]
            trans = self.transitions.unsqueeze(0)  # [1, num_tags, num_tags]
            scores = alpha.unsqueeze(2) + emit + trans  # [batch, num_tags, num_tags]
            new_alpha = torch.logsumexp(scores, dim=1)  # [batch, num_tags]
            alpha = torch.where(valid, new_alpha, alpha)

        log_partition = torch.logsumexp(alpha + self.end_transitions, dim=1)
        return log_partition

    def _viterbi_decode(self, emissions, mask):
        """Viterbi算法找最优路径"""
        batch_size, seq_len, num_tags = emissions.shape

        # 初始化
        viterbi = self.start_transitions + emissions[:, 0, :]  # [batch, num_tags]
        backpointers = []

        for t in range(1, seq_len):
            valid = mask[:, t:t + 1]  # [batch, 1]
            # [batch, num_tags, 1] + transitions = [batch, num_tags, num_tags]
            scores = viterbi.unsqueeze(2) + self.transitions.unsqueeze(0)  # [batch, num_tags, num_tags]
            scores += emissions[:, t:t + 1, :].transpose(1, 2)  # [batch, num_tags, num_tags]
            viterbi_t, backpointer_t = scores.max(dim=1)  # [batch, num_tags]
            viterbi = torch.where(valid, viterbi_t, viterbi)
            backpointers.append(backpointer_t)

        # 结束转移
        viterbi += self.end_transitions
        best_tags = [viterbi.argmax(dim=1)]  # [batch]

        # 回溯
        for backpointer_t in reversed(backpointers):
            best_tag = best_tags[-1]
            best_tags.append(backpointer_t[torch.arange(batch_size), best_tag])

        best_tags = list(reversed(best_tags[:-1]))
        return [tags.tolist() for tags in zip(*best_tags)]


# ============ BERT + BiLSTM + CRF 模型 ============
class BertBiLSTMCRF(nn.Module):
    def __init__(self, num_tags: int, lstm_hidden: int = 256, lstm_layers: int = 1):
        super().__init__()
        self.bert = BertModel.from_pretrained(BERT_MODEL)
        bert_dim = self.bert.config.hidden_size  # 768

        self.dropout = nn.Dropout(0.3)
        self.bilstm = nn.LSTM(
            bert_dim, lstm_hidden // 2, num_layers=lstm_layers,
            batch_first=True, bidirectional=True, dropout=0.1 if lstm_layers > 1 else 0
        )
        self.classifier = nn.Linear(lstm_hidden, num_tags)
        self.crf = CRF(num_tags)

    def forward(self, input_ids, attention_mask, labels=None):
        # BERT编码
        bert_out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = bert_out.last_hidden_state  # [batch, seq_len, 768]
        sequence_output = self.dropout(sequence_output)

        # BiLSTM
        lstm_out, _ = self.bilstm(sequence_output)  # [batch, seq_len, hidden]
        lstm_out = self.dropout(lstm_out)

        # 发射分数
        emissions = self.classifier(lstm_out)  # [batch, seq_len, num_tags]

        # CRF解码
        mask = attention_mask.bool()
        if labels is not None:
            loss = self.crf(emissions, labels, mask)
            return loss
        else:
            predictions = self.crf.decode(emissions, mask)
            return predictions


# ============ 数据集 ============
class SlotDataset(Dataset):
    def __init__(self, data_path: str, tokenizer: BertTokenizer, max_len: int = 128):
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.samples = []

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                self.samples.append((item["tokens"], item["labels"]))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        tokens, labels = self.samples[idx]

        # BERT tokenize（字级别）
        encoding = self.tokenizer(
            tokens,
            is_split_into_words=True,
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)

        # 标签对齐（BERT的word_ids）
        word_ids = encoding.word_ids(batch_index=0)
        label_ids = []
        previous_word_idx = None
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)  # 忽略特殊token
            elif word_idx != previous_word_idx:
                label_ids.append(LABEL2ID.get(labels[word_idx], 0))
            else:
                label_ids.append(-100)  # 子词忽略
            previous_word_idx = word_idx

        label_ids = torch.tensor(label_ids, dtype=torch.long)
        return input_ids, attention_mask, label_ids


# ============ 训练 ============
def train_model(train_path: str, val_path: str = None, save_dir: str = "models/slot_filler"):
    """训练BERT+BiLSTM+CRF槽位填充模型"""
    print(f"Device: {DEVICE}")

    tokenizer = BertTokenizer.from_pretrained(BERT_MODEL)
    train_dataset = SlotDataset(train_path, tokenizer, MAX_LEN)
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    val_loader = None
    if val_path and os.path.exists(val_path):
        val_dataset = SlotDataset(val_path, tokenizer, MAX_LEN)
        val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

    model = BertBiLSTMCRF(num_tags=len(LABELS)).to(DEVICE)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    best_f1 = 0
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        for batch in train_loader:
            input_ids, attention_mask, labels = [x.to(DEVICE) for x in batch]

            optimizer.zero_grad()
            loss = model(input_ids, attention_mask, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        print(f"Epoch {epoch + 1}/{EPOCHS}, Loss: {avg_loss:.4f}")

        # 验证
        if val_loader:
            f1 = evaluate_model(model, val_loader, tokenizer)
            print(f"  Val F1: {f1:.4f}")
            if f1 > best_f1:
                best_f1 = f1
                os.makedirs(save_dir, exist_ok=True)
                torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
                print(f"  Saved best model (F1={f1:.4f})")

    # 保存最终模型
    os.makedirs(save_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(save_dir, "final_model.pt"))
    tokenizer.save_pretrained(save_dir)
    with open(os.path.join(save_dir, "label_config.json"), "w", encoding="utf-8") as f:
        json.dump({"labels": LABELS, "label2id": LABEL2ID, "id2label": ID2LABEL}, f, ensure_ascii=False)
    print(f"Model saved to {save_dir}")


def evaluate_model(model, val_loader, tokenizer):
    """评估模型"""
    model.eval()
    all_preds, all_labels = [], []

    with torch.no_grad():
        for batch in val_loader:
            input_ids, attention_mask, labels = [x.to(DEVICE) for x in batch]
            predictions = model(input_ids, attention_mask)

            for pred_seq, label_seq in zip(predictions, labels.cpu().numpy()):
                pred_tags = [ID2LABEL.get(p, "O") for p in pred_seq]
                true_tags = [ID2LABEL.get(l, "O") for l in label_seq if l != -100]
                # 截断到相同长度
                min_len = min(len(pred_tags), len(true_tags))
                all_preds.append(pred_tags[:min_len])
                all_labels.append(true_tags[:min_len])

    return f1_score(all_labels, all_preds)


# ============ 推理 ============
class BertSlotFiller:
    """BERT槽位填充推理器"""

    def __init__(self, model_dir: str = "models/slot_filler"):
        self.tokenizer = BertTokenizer.from_pretrained(model_dir)
        with open(os.path.join(model_dir, "label_config.json"), "r", encoding="utf-8") as f:
            config = json.load(f)
        self.id2label = {int(k): v for k, v in config["id2label"].items()}

        self.model = BertBiLSTMCRF(num_tags=len(config["labels"]))
        self.model.load_state_dict(torch.load(os.path.join(model_dir, "best_model.pt"), map_location=DEVICE))
        self.model.to(DEVICE)
        self.model.eval()

    def extract(self, text: str) -> Dict:
        """提取槽位"""
        tokens = list(text)  # 字级别分词
        encoding = self.tokenizer(
            tokens, is_split_into_words=True, max_length=MAX_LEN,
            padding="max_length", truncation=True, return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(DEVICE)
        attention_mask = encoding["attention_mask"].to(DEVICE)

        with torch.no_grad():
            predictions = self.model(input_ids, attention_mask)

        # 解码标签
        word_ids = encoding.word_ids(batch_index=0)
        pred_tags = []
        for idx, word_idx in enumerate(word_ids):
            if word_idx is not None and (idx == 0 or word_ids[idx - 1] != word_idx):
                pred_tags.append(self.id2label.get(predictions[0][idx], "O"))

        # 提取实体
        entities = []
        slots = {"company": None, "year": None, "period": None, "subjects": [], "operators": [], "numbers": []}

        i = 0
        while i < len(pred_tags):
            tag = pred_tags[i]
            if tag.startswith("B-"):
                entity_type = tag[2:]
                start = i
                i += 1
                while i < len(pred_tags) and pred_tags[i] == f"I-{entity_type}":
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


# ============ 数据生成工具 ============
def generate_training_data(questions: List[str], output_path: str):
    """
    基于规则生成BIO标注训练数据（半自动标注）
    实际使用时建议人工校验
    """
    # 加载词典
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "data", "company_alias.json"), "r", encoding="utf-8") as f:
        company_alias = json.load(f)
    with open(os.path.join(base_dir, "data", "subject_synonym.json"), "r", encoding="utf-8") as f:
        subject_synonym = json.load(f)

    # 构建匹配词表
    company_names = set()
    for k, v in company_alias.items():
        if not k.startswith("_"):
            company_names.add(k)
            company_names.add(v)

    subject_names = set(list(subject_synonym.keys()) + list(subject_synonym.values()))
    time_patterns = [r"20\d{2}年?", r"第?[一二三四]季度", r"年报", r"半年报", r"中报"]
    op_words = ["大于", "小于", "等于", "超过", "低于", "高于", "排名", "前", "后"]

    samples = []
    for q in questions:
        tokens = list(q)  # 字级别
        labels = ["O"] * len(tokens)

        # 标注公司名
        for name in sorted(company_names, key=len, reverse=True):
            idx = q.find(name)
            if idx != -1:
                for i in range(idx, idx + len(name)):
                    labels[i] = "I-COM" if i > idx else "B-COM"

        # 标注射间
        for pattern in time_patterns:
            for m in re.finditer(pattern, q):
                for i in range(m.start(), m.end()):
                    labels[i] = "I-TIM" if i > m.start() else "B-TIM"

        # 标注科目
        for name in sorted(subject_names, key=len, reverse=True):
            idx = q.find(name)
            if idx != -1:
                for i in range(idx, idx + len(name)):
                    labels[i] = "I-SUB" if i > idx else "B-SUB"

        # 标注运算符
        for op in op_words:
            idx = q.find(op)
            if idx != -1:
                for i in range(idx, idx + len(op)):
                    labels[i] = "I-OP" if i > idx else "B-OP"

        samples.append({"tokens": tokens, "labels": labels})

    with open(output_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"Generated {len(samples)} samples -> {output_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "train":
        # 训练模式
        train_path = sys.argv[2] if len(sys.argv) > 2 else "data/slot_train.jsonl"
        val_path = sys.argv[3] if len(sys.argv) > 3 else None
        train_model(train_path, val_path)
    elif len(sys.argv) > 1 and sys.argv[1] == "generate":
        # 生成训练数据
        # 从intent_train.csv加载问句
        import csv
        questions = []
        with open("data/intent_train.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                questions.append(row["question"])
        generate_training_data(questions, "data/slot_train.jsonl")
    else:
        print("Usage: python slot_filler_bert.py [train|generate]")
