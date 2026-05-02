# -*- coding: utf-8 -*-
"""
意图分类推理脚本
用法: python predict_intent.py "金花股份的总资产是多少"
"""
import os, sys, pickle

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "models", "intent_classifier")


def load_model():
    with open(os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"), "rb") as f:
        vec = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "logistic_regression.pkl"), "rb") as f:
        clf = pickle.load(f)
    return vec, clf


# 规则关键词（用于CALCULATE和RANK的优先判断）
RANK_KEYWORDS = ["排名", "最高", "最低", "最强", "最好", "最差", "前", "后",
                 "第一", "第二", "第三", "前十", "前五", "前三"]
CALCULATE_KEYWORDS = ["计算", "怎么算", "求", "增长率", "增速", "增幅", "同比", "环比",
                      "变化率", "变动", "差额", "差值", "比值"]


def predict(question: str, vec=None, clf=None):
    q = question.lower()
    # 规则优先：RANK
    for kw in RANK_KEYWORDS:
        if kw in q:
            return "RANK", 0.95
    # 规则优先：CALCULATE
    for kw in CALCULATE_KEYWORDS:
        if kw in q:
            return "CALCULATE", 0.90

    # TF-IDF fallback
    if vec is None or clf is None:
        vec, clf = load_model()
    X = vec.transform([question])
    label = clf.predict(X)[0]
    proba = clf.predict_proba(X)[0]
    confidence = float(max(proba))
    return label, confidence


def main():
    if len(sys.argv) < 2:
        print("用法: python predict_intent.py \"你的问题\"")
        return

    question = sys.argv[1]
    vec, clf = load_model()
    label, confidence = predict(question, vec, clf)

    print(f"问题: {question}")
    print(f"意图: {label}  (置信度: {confidence:.2%})")

    for l, p in zip(clf.classes_, clf.predict_proba(vec.transform([question]))[0]):
        print(f"  {l}: {p:.2%}")


if __name__ == "__main__":
    main()
