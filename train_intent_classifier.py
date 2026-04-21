# -*- coding: utf-8 -*-
"""
意图分类器训练脚本
支持双路径（根目录 /data/intent_train_new.csv 或 /data/意图分类/intent_train_new.csv）
自动检测训练数据位置

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


def load_data(csv_path: str):
    """加载 CSV 训练数据"""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    X = [r["question"] for r in rows]
    y = [r["label"] for r in rows]
    return X, y


def train(X, y):
    """训练 TF-IDF + LogisticRegression 模型"""
    print(f"Training on {len(X)} samples, {len(set(y))} classes...")

    # TF-IDF 向量化
    vec = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    Xv = vec.fit_transform(X)
    print(f"  Vectorized: {Xv.shape}")

    # 5折交叉验证
    lr = LogisticRegression(
        max_iter=500,
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        multi_class="multinomial",
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(lr, Xv, y, cv=cv, scoring="f1_macro")
    print(f"  5-fold CV F1: {scores.mean():.4f} ± {scores.std():.4f}")

    # 全量训练
    t0 = time.time()
    lr.fit(Xv, y)
    print(f"  Training time: {time.time()-t0:.1f}s")

    # 在验证集上报告详细指标
    lr_val = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced")
    for fold_idx, (tr_idx, val_idx) in enumerate(cv.split(Xv, y)):
        lr_val.fit(Xv[tr_idx], y[tr_idx])
        preds = lr_val.predict(Xv[val_idx])
        labels_true = [y[i] for i in val_idx]
        print(f"\n  Fold {fold_idx+1} report:")
        print(classification_report(labels_true, preds, digits=4))

    return vec, lr


def save_model(vec, clf, X, y):
    """保存模型到文件"""
    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(vec, f)
    with open(os.path.join(MODEL_DIR, "logistic_regression.pkl"), "wb") as f:
        pickle.dump(clf, f)

    meta = {
        "labels": sorted(set(y)),
        "cv_f1": round(float(scores.mean()), 4),
        "cv_std": round(float(scores.std()), 4),
        "n_samples": len(X),
        "feature_dim": Xv.shape[1] if "Xv" in dir() else 0,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n  Saved to {MODEL_DIR}")


def main():
    # 双路径查找
    paths = [
        os.path.join(BASE, "data", "intent_train_new.csv"),
        os.path.join(BASE, "data", "意图分类", "intent_train_new.csv"),
    ]
    data_path = None
    for p in paths:
        if os.path.exists(p):
            data_path = p
            break

    if data_path is None:
        print(f"[ERROR] 训练数据不存在，尝试路径:")
        for p in paths:
            print(f"  - {p}")
        sys.exit(1)

    print(f"[Data] {data_path}")
    X, y = load_data(data_path)
    vec, clf = train(X, y)

    # 保存
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(vec, f)
    with open(os.path.join(MODEL_DIR, "logistic_regression.pkl"), "wb") as f:
        pickle.dump(clf, f)

    # 计算最终 CV 分数（重新计算用于元信息）
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    Xv = vec.transform(X)
    lr_meta = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced")
    scores = cross_val_score(lr_meta, Xv, y, cv=cv, scoring="f1_macro")

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

    print(f"\nTraining complete!")
    print(f"  CV F1 = {meta['cv_f1']} ± {meta['cv_std']}")
    print(f"  Labels: {meta['labels']}")
    print(f"  Model dir: {MODEL_DIR}")


if __name__ == "__main__":
    main()
