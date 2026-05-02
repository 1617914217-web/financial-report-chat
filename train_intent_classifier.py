# -*- coding: utf-8 -*-
"""
意图分类器训练脚本
TF-IDF + LogisticRegression，5类意图：
  QUERY_SINGLE / QUERY_MULTI / CALCULATE / COMPARE / RANK

输出: models/intent_classifier/
  - tfidf_vectorizer.pkl
  - logistic_regression.pkl
  - model_meta.json
"""
import os, sys, json, pickle, csv, time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "models", "intent_classifier")
DATA_PATH = os.path.join(BASE, "data", "intent_train.csv")


def load_data(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    X = [enhance_features(r["question"]) for r in rows]
    y = [r["label"] for r in rows]
    return X, y


def enhance_features(text: str) -> str:
    """特征工程：添加意图指示词作为额外特征"""
    features = [text]
    
    # CALCULATE指示词
    calc_indicators = ['计算', '公式', '怎么算', '等于多少', '占比', '比率', '比例', '除以', '乘以']
    if any(w in text for w in calc_indicators):
        features.append("__CALC__")
    
    # RANK指示词
    rank_indicators = ['排名', '前', '后', '第几', '最高', '最低', '最多', '最少', 'top', '排序']
    if any(w in text for w in rank_indicators):
        features.append("__RANK__")
    
    # COMPARE指示词
    compare_indicators = ['对比', '比较', 'vs', '和', '与', '同期', '同比', '环比']
    if any(w in text for w in compare_indicators):
        features.append("__COMPARE__")
    
    # QUERY_MULTI指示词
    multi_indicators = ['、', '和', '与', '分别', '各']
    # 检查是否有多个科目或多个公司
    if text.count('、') >= 1 or '分别' in text or '各' in text:
        # 排除COMPARE（已经处理了对比词）
        if "__COMPARE__" not in features:
            features.append("__MULTI__")
    
    return " ".join(features)


def train(X, y):
    print(f"训练数据: {len(X)} 条, {len(set(y))} 类")

    vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 3),
                          min_df=2, sublinear_tf=True)
    Xv = vec.fit_transform(X)
    print(f"  向量化: {Xv.shape}")

    lr = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced",
                            solver="lbfgs")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(lr, Xv, y, cv=cv, scoring="f1_macro")
    print(f"  5折 CV F1: {scores.mean():.4f} +/- {scores.std():.4f}")

    # 最终全量训练
    lr.fit(Xv, y)

    # 验证集详细报告
    lr_val = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced")
    y_list = list(y)
    for fold_idx, (tr_idx, val_idx) in enumerate(cv.split(Xv, y)):
        lr_val.fit(Xv[tr_idx], [y_list[i] for i in tr_idx])
        preds = lr_val.predict(Xv[val_idx])
        print(f"\n  Fold {fold_idx+1}:")
        print(classification_report([y_list[i] for i in val_idx], preds, digits=4))

    return vec, lr


def save_model(vec, clf, X, y):
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(vec, f)
    with open(os.path.join(MODEL_DIR, "logistic_regression.pkl"), "wb") as f:
        pickle.dump(clf, f)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    Xv = vec.transform(X)
    scores = cross_val_score(
        LogisticRegression(max_iter=500, C=1.0, class_weight="balanced"),
        Xv, y, cv=cv, scoring="f1_macro"
    )

    meta = {
        "labels": sorted(set(y)),
        "cv_f1": round(float(scores.mean()), 4),
        "cv_std": round(float(scores.std()), 4),
        "n_samples": len(X),
        "feature_dim": Xv.shape[1],
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n  模型已保存: {MODEL_DIR}")
    print(f"  CV F1 = {meta['cv_f1']} +/- {meta['cv_std']}")
    print(f"  标签: {meta['labels']}")


if __name__ == "__main__":
    if not os.path.exists(DATA_PATH):
        print(f"[ERROR] 训练数据不存在: {DATA_PATH}")
        sys.exit(1)

    X, y = load_data(DATA_PATH)
    vec, clf = train(X, y)
    save_model(vec, clf, X, y)
