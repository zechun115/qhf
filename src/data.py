"""数据加载与划分。

对应实验规范 2/5：
- 训练集用于拟合模型参数与一切预处理统计量；
- 验证集用于选择方案与超参数；
- 测试集（此处为无标签集）只在方案锁定后使用一次。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .utils import DATA_DIR, SEED


@dataclass
class DataBundle:
    """一次实验所需的全部数据。"""

    X_train: list[str]
    y_train: np.ndarray
    X_val: list[str]
    y_val: np.ndarray
    X_test: list[str]          # 无标签测试集（仅用于最终预测）
    train_df: pd.DataFrame
    test_df: pd.DataFrame


def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    """读取原始 CSV，不做任何清洗。"""
    train_df = pd.read_csv(DATA_DIR / "train_data.csv")
    test_df = pd.read_csv(DATA_DIR / "test_data_unlabeled.csv")
    # 缺失值检查：文本缺失会直接破坏向量化，这里做保护性填充
    train_df["text"] = train_df["text"].fillna("").astype(str)
    test_df["text"] = test_df["text"].fillna("").astype(str)
    return train_df, test_df


def split_train_val(
    train_df: pd.DataFrame,
    val_size: float = 0.2,
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按类别分层划分训练/验证集。

    因为本题 10 个类别样本量基本均衡，分层划分可以保证验证集各类别比例与
    训练集一致，避免因随机划分造成评估波动。
    """
    tr, va = train_test_split(
        train_df,
        test_size=val_size,
        random_state=seed,
        stratify=train_df["target"],
        shuffle=True,
    )
    return tr.reset_index(drop=True), va.reset_index(drop=True)


def build_dataset(val_size: float = 0.2, seed: int = SEED) -> DataBundle:
    """构建标准数据包。"""
    train_df, test_df = load_raw()
    tr, va = split_train_val(train_df, val_size=val_size, seed=seed)
    return DataBundle(
        X_train=tr["text"].tolist(),
        y_train=tr["target"].to_numpy(),
        X_val=va["text"].tolist(),
        y_val=va["target"].to_numpy(),
        X_test=test_df["text"].tolist(),
        train_df=tr,
        test_df=test_df,
    )


def describe(train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    """数据探索摘要（写入报告与日志）。"""
    dist = train_df["target"].value_counts().sort_index()
    return {
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_classes": int(train_df["target"].nunique()),
        "class_counts": {int(k): int(v) for k, v in dist.items()},
        "class_ratio_max_min": round(float(dist.max() / dist.min()), 4),
        "dup_text_train": int(train_df["text"].duplicated().sum()),
        "text_len_mean": round(float(train_df["text"].str.len().mean()), 1),
        "text_len_median": int(train_df["text"].str.len().median()),
        "text_len_max": int(train_df["text"].str.len().max()),
        "text_len_p95": int(train_df["text"].str.len().quantile(0.95)),
    }
