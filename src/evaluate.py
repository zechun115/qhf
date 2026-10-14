"""模型评估工具。

实验规范 5/5：指标要与任务目标一致，除总体数字外还要观察各类别表现。
本模块统一输出 accuracy / macro-F1 / weighted-F1、各类别 P-R-F1、混淆矩阵，
并记录训练与预测耗时，用于「性能—复杂度」权衡分析。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


@dataclass
class EvalResult:
    """一次「训练 + 验证评估」的完整记录。"""

    model: str
    params: dict
    params_str: str
    train_seconds: float
    predict_seconds: float
    accuracy: float
    macro_f1: float
    weighted_f1: float
    per_class: dict = field(default_factory=dict)
    confusion: list | None = None
    y_pred: np.ndarray | None = None

    def to_row(self) -> dict:
        return {
            "model": self.model,
            "params": self.params_str,
            "train_seconds": round(self.train_seconds, 3),
            "predict_seconds": round(self.predict_seconds, 4),
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "weighted_f1": round(self.weighted_f1, 4),
        }


def evaluate_model(
    model,
    X_train,
    y_train,
    X_val,
    y_val,
    model_name: str,
    params: dict | None = None,
    params_str: str = "",
    keep_confusion: bool = False,
) -> EvalResult:
    """训练模型并在验证集上评估，返回结构化结果。"""
    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    y_pred = model.predict(X_val)
    predict_seconds = time.perf_counter() - t1

    p, r, f1, support = precision_recall_fscore_support(
        y_val, y_pred, average=None, labels=list(range(10)), zero_division=0
    )
    per_class = {
        int(c): {
            "precision": round(float(p[c]), 4),
            "recall": round(float(r[c]), 4),
            "f1": round(float(f1[c]), 4),
            "support": int(support[c]),
        }
        for c in range(len(p))
    }

    return EvalResult(
        model=model_name,
        params=params or {},
        params_str=params_str,
        train_seconds=round(train_seconds, 3),
        predict_seconds=round(predict_seconds, 4),
        accuracy=float(accuracy_score(y_val, y_pred)),
        macro_f1=float(f1_score(y_val, y_pred, average="macro")),
        weighted_f1=float(f1_score(y_val, y_pred, average="weighted")),
        per_class=per_class,
        confusion=confusion_matrix(y_val, y_pred).tolist() if keep_confusion else None,
        y_pred=y_pred,
    )


def text_report(y_val, y_pred) -> str:
    return classification_report(y_val, y_pred, digits=4, zero_division=0)


def summarize_errors(y_val, y_pred, X_val: list[str], top_k: int = 8) -> dict:
    """误差分析：给出最容易被混淆的类别对，以及若干被误判的样例片段。"""
    cm = confusion_matrix(y_val, y_pred, labels=list(range(10)))
    off_diag = cm.copy()
    np.fill_diagonal(off_diag, 0)
    pairs = []
    flat = np.dstack(np.unravel_index(np.argsort(off_diag.ravel())[::-1], off_diag.shape))[0]
    for true_c, pred_c in flat[:top_k]:
        if off_diag[true_c, pred_c] == 0:
            break
        pairs.append({
            "true": int(true_c),
            "pred": int(pred_c),
            "count": int(off_diag[true_c, pred_c]),
            "rate_of_true_class": round(
                float(off_diag[true_c, pred_c] / max(cm[true_c].sum(), 1)), 4
            ),
        })

    examples = []
    wrong_idx = np.where(y_val != y_pred)[0]
    for i in wrong_idx[:top_k]:
        examples.append({
            "index": int(i),
            "true": int(y_val[i]),
            "pred": int(y_pred[i]),
            "snippet": " ".join(str(X_val[i]).split())[:180],
        })
    return {"top_confusions": pairs, "error_examples": examples}
