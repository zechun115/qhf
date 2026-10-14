"""实验图表生成。

所有图均保存到 results/figures/，供实验报告直接引用。
"""

from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from .utils import FIGURES_DIR

# ---------------------------------------------------------------------------
# 全局样式
# ---------------------------------------------------------------------------
_CJK_CANDIDATES = ["Microsoft YaHei", "SimHei", "DengXian", "SimSun", "DejaVu Sans"]


def _setup_style() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [f for f in _CJK_CANDIDATES if f in available] or ["DejaVu Sans"]
    plt.rcParams.update({
        "font.sans-serif": chosen,
        "axes.unicode_minus": False,
        "figure.dpi": 160,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#94a3b8",
        "text.color": "#0f172a",
        "axes.labelcolor": "#0f172a",
        "xtick.color": "#334155",
        "ytick.color": "#334155",
    })


BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#059669"
AMBER = "#d97706"
PURPLE = "#7c3aed"
SLATE = "#64748b"
MODEL_COLORS = {"NB": AMBER, "LR": BLUE, "SVM": GREEN, "MLP": PURPLE}


def _save(fig, name: str) -> str:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# 图 1：类别分布
# ---------------------------------------------------------------------------
def plot_class_distribution(class_counts: dict, name: str = "fig1_class_distribution") -> str:
    _setup_style()
    labels = sorted(int(k) for k in class_counts)
    values = [class_counts[str(k)] if str(k) in class_counts else class_counts[k]
              for k in labels]

    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    bars = ax.bar(labels, values, color=BLUE, width=0.62, zorder=3)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + 6, str(v),
                ha="center", va="bottom", fontsize=7.5, color="#334155")
    ax.axhline(np.mean(values), color=RED, ls="--", lw=1.1, zorder=4,
               label=f"均值 {np.mean(values):.0f}")
    ax.set_xlabel("类别编号")
    ax.set_ylabel("样本数")
    ax.set_title("图 1  训练集类别分布（10 类基本均衡）", fontweight="bold")
    ax.set_ylim(0, max(values) * 1.24)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 2：预处理消融
# ---------------------------------------------------------------------------
def plot_preprocess_ablation(rows: list[dict], name: str = "fig2_preprocess_ablation") -> str:
    _setup_style()
    names = [r["name"] for r in rows]
    acc = [r["accuracy"] for r in rows]
    f1 = [r["macro_f1"] for r in rows]
    x = np.arange(len(names))
    w = 0.38

    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    b1 = ax.bar(x - w / 2, acc, w, label="验证准确率", color=BLUE, zorder=3)
    b2 = ax.bar(x + w / 2, f1, w, label="Macro-F1", color="#93c5fd", zorder=3)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.004,
                    f"{b.get_height():.3f}", ha="center", va="bottom", fontsize=7, color="#334155")
    best = int(np.argmax(acc))
    lo, hi = min(min(acc), min(f1)) - 0.06, max(acc) + 0.035
    ax.set_ylim(lo, hi)
    ax.axvspan(best - 0.5, best + 0.5, color=RED, alpha=0.07, zorder=0)
    ax.annotate("最优", xy=(best, hi), xytext=(best, hi - (hi - lo) * 0.015),
                ha="center", va="top", fontsize=7.5, color=RED, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=18, ha="right", fontsize=7.5)
    ax.set_ylabel("验证集得分")
    ax.set_title("图 2  文本预处理消融：清洗步骤的边际贡献", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 3：TF-IDF 特征配置对比
# ---------------------------------------------------------------------------
def plot_feature_ablation(rows: list[dict], name: str = "fig3_feature_ablation") -> str:
    _setup_style()
    names = [r["name"] for r in rows]
    acc = [r["accuracy"] for r in rows]
    dims = [r["n_features"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.7),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    order = np.argsort(acc)[::-1]
    s_names = [names[i] for i in order]
    s_acc = [acc[i] for i in order]

    bars = ax1.barh(range(len(s_names))[::-1], s_acc, color=BLUE, height=0.6, zorder=3)
    for i, b in enumerate(bars):
        ax1.text(b.get_width() + 0.0015, b.get_y() + b.get_height() / 2,
                 f"{b.get_width():.4f}", va="center", fontsize=7.5, color="#334155")
    ax1.set_yticks(range(len(s_names))[::-1])
    ax1.set_yticklabels(s_names, fontsize=7.5)
    ax1.set_xlim(min(s_acc) - 0.012, max(s_acc) + 0.012)
    ax1.set_xlabel("验证准确率")
    ax1.set_title("(a) 特征配置排名", fontsize=9)
    ax1.grid(axis="y", alpha=0)

    ax2.scatter(dims, acc, s=42, color=RED, zorder=3)
    for n, d, a in zip(names, dims, acc):
        ax2.annotate(n.split("_")[0], (d, a), textcoords="offset points",
                     xytext=(0, 6), ha="center", fontsize=7, color="#334155")
    ax2.set_xlabel("词表维度（特征数）")
    ax2.set_ylabel("验证准确率")
    ax2.set_title("(b) 维度 vs 性能", fontsize=9)
    fig.suptitle("图 3  TF-IDF 特征表示消融", fontweight="bold", y=1.03, fontsize=10)
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 4：各模型超参数敏感性
# ---------------------------------------------------------------------------
def plot_param_curves(curves: dict, name: str = "fig4_param_curves") -> str:
    """curves: {模型名: [(x轴标签, 验证准确率), ...]}；可选 {'split_at': int}
    表示在第 k 个点之后是第二阶段搜索（用竖直虚线分开）。"""
    _setup_style()
    fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.5))
    for ax, (model, points) in zip(axes, curves.items()):
        labels = [p[0] for p in points]
        ys = [p[1] for p in points]
        color = MODEL_COLORS.get(model, BLUE)
        ax.plot(range(len(ys)), ys, marker="o", ms=4.2, lw=1.5, color=color, zorder=3)
        best = int(np.argmax(ys))
        ax.scatter([best], [ys[best]], s=64, facecolor="none",
                   edgecolor=RED, lw=1.4, zorder=4)
        ax.annotate(f"{ys[best]:.4f}", (best, ys[best]), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=7, color=RED)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=6.4, rotation=32, ha="right")
        lo, hi = min(ys), max(ys)
        pad = max((hi - lo) * 0.30, 0.004)
        ax.set_ylim(lo - pad, hi + pad * 1.7)
        if len(ys) > 5:  # 两阶段搜索：画一条分界线（前 4 个为结构搜索）
            ax.axvline(3.5, color=SLATE, ls=":", lw=1, zorder=2)
            ax.text(3.6, hi + pad * 1.35, "阶段②", fontsize=6.2, color=SLATE,
                    va="top", ha="left")
        ax.set_title(model, fontsize=9, fontweight="bold")
        ax.set_xlabel("超参数取值", fontsize=7.5)
        ax.tick_params(axis="y", labelsize=7)
    axes[0].set_ylabel("验证准确率", fontsize=8)
    fig.suptitle("图 4  各模型超参数敏感性（红圈为最优取值）", fontweight="bold", y=1.05, fontsize=10)
    fig.tight_layout()
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 5：混淆矩阵
# ---------------------------------------------------------------------------
def plot_confusion_matrix(cm, name: str = "fig5_confusion_matrix",
                          title: str = "图 6  最优模型混淆矩阵（验证集）") -> str:
    _setup_style()
    cm = np.asarray(cm, dtype=float)
    norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)

    fig, ax = plt.subplots(figsize=(4.9, 4.2))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(10)); ax.set_yticks(range(10))
    ax.set_xticklabels(range(10), fontsize=7.5); ax.set_yticklabels(range(10), fontsize=7.5)
    ax.set_xlabel("预测类别"); ax.set_ylabel("真实类别")
    ax.grid(False)
    for i in range(10):
        for j in range(10):
            if norm[i, j] >= 0.01:
                ax.text(j, i, f"{norm[i, j]:.2f}", ha="center", va="center", fontsize=6.2,
                        color="white" if norm[i, j] > 0.55 else "#0f172a")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.ax.tick_params(labelsize=7)
    cb.set_label("行归一化比例", fontsize=7.5)
    ax.set_title(title, fontweight="bold", fontsize=9.5)
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 6：模型综合对比（性能 vs 训练成本）
# ---------------------------------------------------------------------------
def plot_model_comparison(rows: list[dict], name: str = "fig6_model_comparison") -> str:
    _setup_style()
    models = [r["model"] for r in rows]
    acc = [r["accuracy"] for r in rows]
    t = [max(r["train_seconds"], 1e-3) for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.6),
                                   gridspec_kw={"width_ratios": [1, 1.15]})
    bars = ax1.bar(models, acc, color=[MODEL_COLORS.get(m, BLUE) for m in models],
                   width=0.55, zorder=3)
    for b in bars:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.004,
                 f"{b.get_height():.4f}", ha="center", va="bottom", fontsize=7.5, color="#334155")
    ax1.set_ylim(min(acc) - 0.05, max(acc) + 0.035)
    ax1.set_ylabel("验证准确率")
    ax1.set_title("(a) 各模型最优验证准确率", fontsize=9)

    for m, ti, a in zip(models, t, acc):
        ax2.scatter(ti, a, s=58, color=MODEL_COLORS.get(m, BLUE), zorder=3, label=m)
        ax2.annotate(m, (ti, a), textcoords="offset points", xytext=(7, -2),
                     fontsize=7.5, color="#334155")
    ax2.set_xscale("log")
    ax2.set_xlabel("单次训练耗时 / 秒（对数轴）")
    ax2.set_ylabel("验证准确率")
    ax2.set_title("(b) 性能—训练成本权衡", fontsize=9)
    fig.suptitle("图 5  四个分类器的性能与计算代价对比", fontweight="bold", y=1.04, fontsize=10)
    fig.tight_layout()
    return _save(fig, name)


# ---------------------------------------------------------------------------
# 图 7：类别级 F1
# ---------------------------------------------------------------------------
def plot_per_class_f1(per_class: dict, model_name: str,
                      name: str = "fig7_per_class_f1") -> str:
    _setup_style()
    labels = sorted(int(k) for k in per_class)
    f1 = [per_class[str(k)]["f1"] if str(k) in per_class else per_class[k]["f1"] for k in labels]

    fig, ax = plt.subplots(figsize=(6.4, 2.2))
    colors = [RED if v < 0.85 else BLUE for v in f1]
    bars = ax.bar([str(l) for l in labels], f1, color=colors, width=0.6, zorder=3)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.006,
                f"{b.get_height():.3f}", ha="center", va="bottom", fontsize=7, color="#334155")
    ax.axhline(np.mean(f1), color=SLATE, ls="--", lw=1, label=f"均值 {np.mean(f1):.3f}")
    ax.set_ylim(min(f1) - 0.09, 1.03)
    ax.set_xlabel("类别编号"); ax.set_ylabel("F1")
    ax.set_title(f"图 7  {model_name} 各类别 F1（红色为低于 0.85 的弱类别）", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, name)
