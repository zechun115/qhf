"""文本特征工程：TF-IDF 向量化。

实验规范 3/5：涉及词表与 IDF 的统计量只能从训练集学习。因此本模块中
`build_features` **只用 X_train 调用 fit_transform**，验证集与测试集一律
只做 transform。这也意味着任何评估都不会出现词表泄露。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class TfidfConfig:
    """TF-IDF 的可调配置。"""

    max_features: int = 20000      # 词表上限（文本向量维度）
    ngram_range: tuple = (1, 1)    # 1=unigram；(1,2)=加入 bigram
    min_df: int = 2                # 至少在 2 篇文档中出现，抑制噪声词
    max_df: float = 0.9            # 出现在 >90% 文档中的词信息量低
    sublinear_tf: bool = True      # 用 1+log(tf) 抑制长文档的词频优势
    use_idf: bool = True           # 逆文档频率加权
    stop_words: str | None = None  # 停用词已在预处理阶段处理
    name: str = "tfidf"

    def build(self) -> TfidfVectorizer:
        return TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=self.min_df,
            max_df=self.max_df,
            sublinear_tf=self.sublinear_tf,
            use_idf=self.use_idf,
            stop_words=self.stop_words,
            lowercase=False,   # 预处理已完成小写化，此处避免重复
            token_pattern=r"(?u)\b\w\w+\b",
        )

    def describe(self) -> str:
        ng = "1-gram" if self.ngram_range == (1, 1) else f"{self.ngram_range[0]}-{self.ngram_range[1]}-gram"
        return (
            f"max_features={self.max_features}, ngram={ng}, min_df={self.min_df}, "
            f"max_df={self.max_df}, sublinear_tf={self.sublinear_tf}, use_idf={self.use_idf}"
        )


@dataclass
class FeatureBundle:
    X_train: object
    X_val: object
    X_test: object
    vectorizer: TfidfVectorizer
    n_features: int
    fit_seconds: float


def build_features(
    X_train: list[str],
    X_val: list[str],
    X_test: list[str],
    cfg: TfidfConfig,
) -> FeatureBundle:
    """在训练集上拟合 TF-IDF，并把同一变换应用到验证集与测试集。"""
    import time

    t0 = time.perf_counter()
    vectorizer = cfg.build()
    X_train_vec = vectorizer.fit_transform(X_train)   # 只在这里 fit
    X_val_vec = vectorizer.transform(X_val)
    X_test_vec = vectorizer.transform(X_test)
    fit_seconds = time.perf_counter() - t0
    return FeatureBundle(
        X_train=X_train_vec,
        X_val=X_val_vec,
        X_test=X_test_vec,
        vectorizer=vectorizer,
        n_features=int(X_train_vec.shape[1]),
        fit_seconds=round(fit_seconds, 3),
    )


def preset_feature_configs() -> dict[str, TfidfConfig]:
    """候选特征配置（用于消融实验 B，控制单一变量）。"""
    base = dict(max_features=20000, ngram_range=(1, 1), min_df=2,
                max_df=0.9, sublinear_tf=True, use_idf=True)
    return {
        "F0_binary词频": TfidfConfig(**{**base, "use_idf": False, "sublinear_tf": False,
                                        "name": "F0_binary词频"}),
        "F1_TF-IDF(sublinear)": TfidfConfig(**{**base, "name": "F1_TF-IDF(sublinear)"}),
        "F2_词表5k": TfidfConfig(**{**base, "max_features": 5000, "name": "F2_词表5k"}),
        "F3_词表50k": TfidfConfig(**{**base, "max_features": 50000, "name": "F3_词表50k"}),
        "F4_加入bigram": TfidfConfig(**{**base, "ngram_range": (1, 2), "name": "F4_加入bigram"}),
        "F5_min_df=1": TfidfConfig(**{**base, "min_df": 1, "name": "F5_min_df=1"}),
    }


def top_terms_by_class(
    vectorizer: TfidfVectorizer,
    X_train_vec,
    y_train: np.ndarray,
    n_classes: int = 10,
    top_k: int = 8,
) -> dict[int, list[str]]:
    """按类别统计平均 TF-IDF 最高的词，用于解释模型「看到了什么」。"""
    vocab = np.array(vectorizer.get_feature_names_out())
    result: dict[int, list[str]] = {}
    for c in range(n_classes):
        mask = y_train == c
        if mask.sum() == 0:
            continue
        mean_tfidf = np.asarray(X_train_vec[mask].mean(axis=0)).ravel()
        idx = np.argsort(mean_tfidf)[::-1][:top_k]
        result[c] = [str(vocab[i]) for i in idx]
    return result
