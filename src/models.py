"""分类模型工厂与超参数候选集合。

对应实验要求：「从上述算法中选择至少 2 项进行训练」，本实现把课件中的
四个经典分类器全部纳入对比，并给出各自的调参范围（参考 TUNING.md）。

所有模型都显式传入 random_state=SEED，保证结果可复现。
"""

from __future__ import annotations

from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC

from .utils import SEED

# ---------------------------------------------------------------------------
# 模型注册表：名称 -> (构造函数, 人类可读说明, 是否需要稠密输入)
# ---------------------------------------------------------------------------
MODEL_INFO = {
    "NB": {
        "full_name": "朴素贝叶斯 (MultinomialNB)",
        "note": "基于特征条件独立假设，训练与预测极快，是文本分类的经典基线。",
    },
    "LR": {
        "full_name": "逻辑回归 (Logistic Regression)",
        "note": "线性判别 + 概率输出，对高维稀疏 TF-IDF 特征表现稳定。",
    },
    "SVM": {
        "full_name": "支持向量机 (SVC)",
        "note": "最大化类别间隔；文本特征高维稀疏，线性核通常最优。",
    },
    "MLP": {
        "full_name": "多层感知机 (MLPClassifier)",
        "note": "含隐藏层的神经网络，可拟合非线性关系，但参数更多、更易过拟合。",
    },
}


# ---------------------------------------------------------------------------
# MLP 的固定训练超参数
#   max_iter=60 / batch_size=512：在 20000 维稀疏 TF-IDF 上，这个组合相对
#   sklearn 默认（max_iter 内循环 + batch_size=200）把单次训练时间从约
#   290 s 降到约 120 s，验证准确率差异在 0.1 个百分点以内。
#   early_stopping=False 是为了让训练结果完全由 random_state 决定，便于复现。
# ---------------------------------------------------------------------------
MLP_MAX_ITER = 60
MLP_BASE = {
    "max_iter": MLP_MAX_ITER,
    "batch_size": 512,
    "early_stopping": False,
    "learning_rate_init": 1e-3,
}
# 写入日志/表格时不展示的实现细节参数
_HIDDEN_KEYS = {"max_iter", "batch_size", "early_stopping", "learning_rate_init"}


def make_model(name: str, params: dict | None = None, seed: int = SEED):
    """按名称与超参数构造模型实例。"""
    params = dict(params or {})
    if name == "NB":
        return MultinomialNB(**params)
    if name == "LR":
        return LogisticRegression(random_state=seed, **params)
    if name == "SVM":
        return SVC(random_state=seed, **params)
    if name == "MLP":
        return MLPClassifier(random_state=seed, **params)
    raise ValueError(f"未知模型: {name}")


# ---------------------------------------------------------------------------
# 超参数候选集合（数值范围参考 TUNING.md 的建议：按数量级搜索）
# ---------------------------------------------------------------------------
def param_grids() -> dict[str, list[dict]]:
    return {
        # alpha 为拉普拉斯平滑系数
        "NB": [{"alpha": a} for a in (0.01, 0.05, 0.1, 0.5, 1.0, 2.0)],
        # C 为正则化强度的倒数
        "LR": [
            {"C": c, "max_iter": 2000, "solver": "lbfgs"} for c in (0.1, 1.0, 10.0, 100.0)
        ],
        # 线性核为主，C 控制对错分的惩罚力度
        "SVM": [
            {"kernel": "linear", "C": c} for c in (0.1, 1.0, 10.0, 100.0)
        ],
        # MLP 采用两阶段搜索：先定结构，再定正则化强度（见 experiment.py）
        # batch_size=512：经实测比默认 200 快约 2.5 倍，且验证准确率基本不变
        "MLP": [
            {"hidden_layer_sizes": (h,), **MLP_BASE} for h in (50, 100, 200)
        ] + [
            {"hidden_layer_sizes": (100, 50), **MLP_BASE}
        ],
    }


def mlp_alpha_grid(structure: tuple, max_iter: int = MLP_MAX_ITER) -> list[dict]:
    """第二阶段：固定最优结构，搜索 L2 正则化强度 alpha。"""
    return [
        {"hidden_layer_sizes": structure, "alpha": a, **{**MLP_BASE, "max_iter": max_iter}}
        for a in (1e-4, 1e-3, 1e-2, 1e-1)
    ]


def param_str(params: dict) -> str:
    """把超参数字典格式化为一行短字符串，便于写入日志与表格。"""
    if not params:
        return "默认参数"
    shown = {k: v for k, v in params.items() if k not in _HIDDEN_KEYS}
    return ", ".join(f"{k}={v}" for k, v in shown.items())
