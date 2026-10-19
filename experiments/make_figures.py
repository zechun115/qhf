"""根据实验结果生成报告插图（一次性脚本）。"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"
plt.rcParams["axes.edgecolor"] = "#BFBFBF"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["font.size"] = 10

C_BLUE = "#2E5A88"
C_RED = "#C0504D"
C_GREEN = "#6E9B3D"
C_GRAY = "#808080"
C_PURPLE = "#8064A2"
C_TEAL = "#2F9BA6"
C_SAND = "#C9A227"


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return json.load(f)


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


# --------------------------------------------------------------------------- #
# 图 1：迷宫搜索过程（h=0 vs 曼哈顿）
# --------------------------------------------------------------------------- #
def fig_maze():
    sys.path.insert(0, os.path.dirname(HERE))
    from src.astar import solve_maze

    maze = [["S", ".", ".", "X", "."],
            [".", "X", ".", ".", "."],
            [".", "X", ".", "X", "."],
            [".", ".", ".", "X", "E"],
            ["X", "X", ".", ".", "."]]
    res = {h: solve_maze((0, 0), (3, 4), maze, heuristic=h, return_nodes=True)
           for h in ("zero", "manhattan")}

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.3))
    for ax, (name, label) in zip(axes, [("zero", "h=0（Dijkstra）"), ("manhattan", "h=曼哈顿距离")]):
        r = res[name]
        n, m = len(maze), len(maze[0])
        ax.set_xlim(-0.5, m - 0.5)
        ax.set_ylim(n - 0.5, -0.5)
        ax.set_aspect("equal")
        ax.axis("off")
        for i in range(n):
            for j in range(m):
                ch = maze[i][j]
                face = "#4D4D4D" if ch == "X" else "#FFFFFF"
                if ch == "S":
                    face = "#DCE9F7"
                elif ch == "E":
                    face = "#F6E3C5"
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=face,
                                       edgecolor="#BFBFBF", lw=0.8, zorder=1))
                if ch == "X":
                    ax.text(j, i, "×", ha="center", va="center", color="#E8E8E8",
                            fontsize=13, zorder=2)
                elif ch in "SE":
                    ax.text(j, i, ch, ha="center", va="center", color=C_BLUE if ch == "S" else C_SAND,
                            fontsize=14, fontweight="bold", zorder=4)
        # 扩展顺序
        order = {cell: k + 1 for k, cell in enumerate(r.expanded_order)}
        for (i, j), k in order.items():
            if maze[i][j] in "SE":
                continue
            ax.text(j - 0.28, i - 0.28, str(k), ha="left", va="top", fontsize=6.5,
                    color="#9AA7B4", zorder=2)
        # 路径
        path = r.path
        for a, b in zip(path[:-1], path[1:]):
            ax.add_patch(FancyArrowPatch((a[1], a[0]), (b[1], b[0]),
                                         arrowstyle="-|>", mutation_scale=11,
                                         color=C_RED, lw=2.0, shrinkA=6, shrinkB=6, zorder=5))
        for (i, j) in path:
            ax.add_patch(Rectangle((j - 0.42, i - 0.42), 0.84, 0.84, fill=False,
                                   edgecolor=C_RED, lw=1.4, zorder=3))
        ax.set_title(f"{label}\n扩展节点 {r.expanded} 个，路径代价 {int(r.cost)}",
                     fontsize=10.5, color="#333333")
    fig.suptitle("题目一：同一迷宫的两种启发函数搜索过程（格内数字为扩展次序）",
                 fontsize=11.5, color="#222222")
    fig.tight_layout()
    save(fig, "fig1_maze.png")


# --------------------------------------------------------------------------- #
# 图 2：启发函数随规模的搜索开销
# --------------------------------------------------------------------------- #
def fig_heuristic():
    d = load("exp1_maze.json")
    sizes = sorted(int(k) for k in d["per_size"])
    names = [("zero", "h=0", C_GRAY), ("chebyshev", "切比雪夫", C_PURPLE),
             ("euclidean", "欧氏（取整）", C_TEAL), ("manhattan", "曼哈顿", C_BLUE)]

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    ax = axes[0]
    for key, label, color in names:
        ys = [d["per_size"][str(n)][key]["mean"] for n in sizes]
        ax.plot(sizes, ys, "o-", color=color, label=label, lw=1.8, ms=4.5)
    ax.set_yscale("log")
    ax.set_xlabel("地图边长 n（障碍率 28%，每档 20 张随机图）")
    ax.set_ylabel("平均扩展节点数（对数轴）")
    ax.set_title("(a) 扩展节点数随规模增长", fontsize=10.5)
    ax.grid(alpha=0.25, ls=":")
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    for key, label, color in names:
        ys = [d["pct_expanded"][str(n)][key] for n in sizes]
        ax.plot(sizes, ys, "o-", color=color, label=label, lw=1.8, ms=4.5)
    ax.set_xlabel("地图边长 n")
    ax.set_ylabel("扩展节点占可通行格比例（%）")
    ax.set_title("(b) 归一化搜索开销", fontsize=10.5)
    ax.grid(alpha=0.25, ls=":")
    ax.set_ylim(0, None)

    ax = axes[2]
    ws = [r["w"] for r in d["weighted_astar"]]
    nodes = [r["expanded"] for r in d["weighted_astar"]]
    ratio = [r["cost_ratio"] for r in d["weighted_astar"]]
    b = ax.bar([str(w) for w in ws], nodes, color=C_BLUE, width=0.6)
    ax.set_xlabel("启发权重 w（h = w·曼哈顿）")
    ax.set_ylabel("平均扩展节点数", color=C_BLUE)
    ax.tick_params(axis="y", labelcolor=C_BLUE)
    ax.set_title("(c) 加权 A*：速度与最优性的权衡", fontsize=10.5)
    for rect, r in zip(b, ratio):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 12,
                f"×{r:.3f}", ha="center", fontsize=8, color="#333333")
    ax2 = ax.twinx()
    ax2.plot(range(len(ws)), ratio, "o--", color=C_RED, lw=1.6, ms=4)
    ax2.set_ylabel("路径代价 / 最优代价", color=C_RED)
    ax2.tick_params(axis="y", labelcolor=C_RED)
    ax2.set_ylim(0.99, max(ratio) * 1.06)
    ax2.spines["top"].set_visible(False)
    ax.grid(alpha=0.2, ls=":")
    fig.suptitle("题目一：启发函数强度对搜索开销的影响（81×81 随机迷宫，20 张平均）",
                 fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig2_heuristic.png")


# --------------------------------------------------------------------------- #
# 图 3：加权地形路径与代价累计
# --------------------------------------------------------------------------- #
def fig_weighted():
    d = load("exp3_weighted.json")
    grid = d["weighted_map"]
    path = [tuple(p) for p in d["path"]]
    trace = {tuple(p): (w, g) for p, w, g in d["trace"]}

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6),
                             gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    n, m = len(grid), len(grid[0])
    ax.set_xlim(-0.5, m - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.axis("off")
    for i in range(n):
        for j in range(m):
            v = grid[i][j]
            if v == "S":
                face, txt = "#DCE9F7", "S"
            elif v == "E":
                face, txt = "#F6E3C5", "E"
            else:
                iv = int(v)
                alpha = min(0.15 + iv / 12, 0.85)
                face = plt.cm.Reds(alpha)
                txt = str(iv)
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=face,
                                   edgecolor="#FFFFFF", lw=1.2))
            ax.text(j, i, txt, ha="center", va="center", fontsize=10,
                    color="#222222" if v not in ("S", "E") else "#222222",
                    fontweight="bold" if v in ("S", "E") else "normal")
    for a, b in zip(path[:-1], path[1:]):
        ax.add_patch(FancyArrowPatch((a[1], a[0]), (b[1], b[0]), arrowstyle="-|>",
                                     mutation_scale=12, color=C_BLUE, lw=2.2,
                                     shrinkA=10, shrinkB=10, zorder=5))
    ax.set_title("(a) 最优路径：累计代价最小的绕行", fontsize=10.5)

    ax = axes[1]
    xs = list(range(len(path)))
    gs = [trace[c][1] for c in path]
    ax.step(xs, gs, where="post", color=C_BLUE, lw=2)
    ax.fill_between(xs, gs, step="post", color=C_BLUE, alpha=0.12)
    labels = [f"({r},{c})" for r, c in path]
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=60, fontsize=7.5)
    ax.set_ylabel("累计代价 g")
    ax.set_title("(b) 每一步的 g 值累计过程", fontsize=10.5)
    ax.grid(alpha=0.25, ls=":", axis="y")
    for x, y in zip(xs, gs):
        ax.plot([x], [y], "o", color=C_BLUE, ms=3.5)
    ax.set_ylim(0, max(gs) * 1.15)
    ax.annotate("进入 E 的代价记为 0\n总代价 = 7", xy=(xs[-1], gs[-1]),
                xytext=(xs[-1] - 3.2, gs[-1] - 2.2), fontsize=9, color=C_RED,
                arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.1))
    fig.suptitle("题目二：加权地形的最小代价路径（题面用例，代价 7）", fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig3_weighted.png")


# --------------------------------------------------------------------------- #
# 图 4：平局策略与可采纳性实验
# --------------------------------------------------------------------------- #
def fig_tie_and_k():
    d2 = load("exp2_tiebreak.json")
    d3 = load("exp3_weighted.json")

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 3.9))
    ax = axes[0]
    keys = ["none", "h", "g"]
    labels = ["FIFO\n（按入队次序）", "平局取 h 小\n（更深、靠近终点）", "平局取 h 大\n（更浅、远离终点）"]
    vals = [d2[k]["expanded"] for k in keys]
    bars = ax.bar(labels, vals, color=[C_GRAY, C_BLUE, C_RED], width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 40, f"{v:.0f}", ha="center", fontsize=9.5)
    ax.set_ylabel("平均扩展节点数")
    ax.set_title("(a) f 值相同时的次序对开销的影响（81×81）", fontsize=10.5)
    ax.grid(alpha=0.2, ls=":", axis="y")
    ax.set_ylim(0, max(vals) * 1.18)

    ax = axes[1]
    ks = [r["k"] for r in d3["sweep_k"]]
    nodes = [r["expanded"] for r in d3["sweep_k"]]
    bad = [r["suboptimal_rate"] * 100 for r in d3["sweep_k"]]
    ax.plot(ks, nodes, "o-", color=C_BLUE, lw=1.9, label="平均扩展节点数")
    ax.set_xlabel("启发缩放系数 k（h = k·曼哈顿，地图最小单步代价 = 3）")
    ax.set_ylabel("平均扩展节点数", color=C_BLUE)
    ax.tick_params(axis="y", labelcolor=C_BLUE)
    ax.set_yscale("log")
    ax.axvline(3, color=C_GREEN, ls="--", lw=1.2)
    ax.text(3.08, max(nodes) * 0.6, "可采纳性边界\nk = 最小单步代价", color=C_GREEN, fontsize=8.5)
    ax2 = ax.twinx()
    ax2.plot(ks, bad, "s--", color=C_RED, lw=1.6, ms=5, label="次优解比例")
    ax2.set_ylabel("返回次优解的比例（%）", color=C_RED)
    ax2.tick_params(axis="y", labelcolor=C_RED)
    ax2.set_ylim(-3, 105)
    ax2.spines["top"].set_visible(False)
    ax.set_title("(b) 启发强度与可采纳性：k 越过下界即失去最优性", fontsize=10.5)
    ax.grid(alpha=0.2, ls=":")
    fig.suptitle("题目一/二：平局策略与启发函数可采纳性实验", fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig4_tie_k.png")


# --------------------------------------------------------------------------- #
# 图 5：题目三博弈树与数值回传
# --------------------------------------------------------------------------- #
def fig_tree():
    sys.path.insert(0, os.path.dirname(HERE))
    from src.game_tree import (alpha_beta, build_problem3_tree, SearchStats,
                               static_value)

    root = build_problem3_tree()
    st = SearchStats()
    alpha_beta(root, True, stats=st)
    visited = set(st.visited_ids)

    # 布局：叶子从左到右排布，内部节点取子节点中点
    pos = {}
    order = []

    def assign(node, depth):
        if node.is_leaf:
            order.append(node)
            pos[id(node)] = (len(order) - 1, -depth)
            return pos[id(node)][0]
        xs = [assign(c, depth + 1) for c in node.children]
        pos[id(node)] = (sum(xs) / len(xs), -depth)
        return pos[id(node)][0]

    assign(root, 0)
    depth_max = max(-y for _, y in pos.values())

    fig, ax = plt.subplots(figsize=(10.2, 4.6))
    ax.axis("off")
    ab_val = {}       # alpha-beta 实际回传值
    cut_note = {}     # 被剪节点说明

    def draw_pruned(node, is_max, depth, px, py):
        """绘制因剪枝而未访问的子树（灰色虚线）。"""
        x, y = pos[id(node)]
        ax.annotate("", xy=(x, y + 0.10), xytext=(px, py - 0.10),
                    arrowprops=dict(arrowstyle="-", lw=1.2, color="#C9C9C9",
                                    linestyle=(0, (3, 3))))
        if node.is_leaf:
            ax.add_patch(plt.Circle((x, y), 0.26, facecolor="#F2F2F2",
                                    edgecolor="#BFBFBF", lw=1.2, zorder=3))
            ax.text(x, y, str(node.value), ha="center", va="center", fontsize=9.5,
                    color="#9E9E9E", zorder=4)
            ax.text(x, y - 0.46, "剪枝", ha="center", fontsize=7.5, color=C_RED)
            return
        v = static_value(node, is_max)
        ax.add_patch(Rectangle((x - 0.30, y - 0.22), 0.60, 0.44, facecolor="#F2F2F2",
                               edgecolor="#BFBFBF", lw=1.1, linestyle="--", zorder=3))
        ax.text(x, y + 0.02, f"{v:g}", ha="center", va="center", fontsize=9.5,
                color="#9E9E9E", zorder=4)
        ax.text(x, y - 0.34, "MAX" if is_max else "MIN", ha="center", fontsize=7.2,
                color="#BFBFBF")
        for c in node.children:
            draw_pruned(c, not is_max, depth + 1, x, y)

    def draw(node, is_max, depth, alpha, beta):
        """按 alpha-beta 的真实执行过程绘制：被剪枝的子树按实际返回值标注。"""
        x, y = pos[id(node)]
        if node.is_leaf:
            evaluated = id(node) in visited
            face = "#FFFFFF" if evaluated else "#F2F2F2"
            ax.add_patch(plt.Circle((x, y), 0.26, facecolor=face,
                                    edgecolor="#4D4D4D" if evaluated else "#BFBFBF",
                                    lw=1.2, zorder=3))
            ax.text(x, y, str(node.value), ha="center", va="center", fontsize=9.5,
                    color="#222222" if evaluated else "#9E9E9E", zorder=4)
            if not evaluated:
                ax.text(x, y - 0.44, "剪枝", ha="center", fontsize=7.5, color=C_RED)
            return node.value

        if is_max:
            value, a = float("-inf"), alpha
            for i, c in enumerate(node.children):
                cx, cy = pos[id(c)]
                v = draw(c, not is_max, depth + 1, a, beta)
                value = max(value, v)
                a = max(a, value)
                evaluated = id(c) in visited
                ax.annotate("", xy=(cx, cy + 0.10), xytext=(x, y - 0.10),
                            arrowprops=dict(arrowstyle="-", lw=1.4,
                                            color="#4D4D4D" if evaluated else "#D0D0D0",
                                            linestyle="-" if evaluated else (0, (3, 3))))
                if value >= beta:
                    for rest in node.children[i + 1:]:
                        draw_pruned(rest, not is_max, depth + 1, x, y)
                    break
            v_out = value
        else:
            value, b = float("inf"), beta
            for i, c in enumerate(node.children):
                cx, cy = pos[id(c)]
                v = draw(c, not is_max, depth + 1, alpha, b)
                value = min(value, v)
                b = min(b, value)
                evaluated = id(c) in visited
                ax.annotate("", xy=(cx, cy + 0.10), xytext=(x, y - 0.10),
                            arrowprops=dict(arrowstyle="-", lw=1.4,
                                            color="#4D4D4D" if evaluated else "#D0D0D0",
                                            linestyle="-" if evaluated else (0, (3, 3))))
                if value <= alpha:
                    for rest in node.children[i + 1:]:
                        draw_pruned(rest, not is_max, depth + 1, x, y)
                    break
            v_out = value

        face = "#DCE9F7" if is_max else "#F6E3C5"
        ax.add_patch(Rectangle((x - 0.30, y - 0.22), 0.60, 0.44, facecolor=face,
                               edgecolor=C_BLUE if is_max else C_SAND, lw=1.3, zorder=3))
        ax.text(x, y + 0.02, f"{v_out:g}", ha="center", va="center", fontsize=9.5,
                fontweight="bold", color="#1F3864" if is_max else "#7F6000", zorder=4)
        ax.text(x, y - 0.34, "MAX" if is_max else "MIN", ha="center", fontsize=7.2,
                color=C_BLUE if is_max else C_SAND)
        ab_val[id(node)] = v_out
        return v_out

    draw(root, True, 0, float("-inf"), float("inf"))
    ax.set_xlim(-0.9, len(order) - 0.1)
    ax.set_ylim(-depth_max - 0.9, 0.7)
    ax.text(-0.7, 0.55, "自然顺序下共访问 14 个节点、评估 7 个叶子：max2 处因 6 ≥ β=5 剪去叶子 9；"
                        "min2 回传 2 ≤ α=5 在根处触发剪枝（其后已无兄弟）", fontsize=8.8, color="#333333")
    ax.set_title("题目三：博弈树的 α-β 剪枝与数值回传（矩形=MAX/MIN，圆=叶子，虚线=被剪枝）",
                 fontsize=11, pad=14)
    fig.tight_layout()
    save(fig, "fig5_tree.png")


# --------------------------------------------------------------------------- #
# 图 6：Alpha-Beta 规模效应与访问顺序
# --------------------------------------------------------------------------- #
def fig_ab_scaling():
    d = load("exp4_alphabeta.json")
    s = d["scaling"]
    depths = [r["depth"] for r in s]
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.0))

    ax = axes[0]
    ax.plot(depths, [r["minimax"] for r in s], "o-", color=C_RED, label="Minimax", lw=1.9)
    ax.plot(depths, [r["ab_natural"] for r in s], "s-", color=C_BLUE,
            label="α-β（自然顺序）", lw=1.9)
    ax.plot(depths, [r["ab_best_first"] for r in s], "^-", color=C_GREEN,
            label="α-β（最优优先排序）", lw=1.9)
    ax.set_yscale("log")
    ax.set_xlabel("树的深度（分支因子 3）")
    ax.set_ylabel("平均访问节点数（对数轴）")
    ax.set_title("(a) 三种搜索的节点开销", fontsize=10.5)
    ax.grid(alpha=0.25, ls=":")
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    w = 0.36
    xs = np.arange(len(depths))
    ax.bar(xs - w / 2, [r["saving_natural"] * 100 for r in s], w, color=C_BLUE,
           label="α-β（自然顺序）")
    ax.bar(xs + w / 2, [r["saving_best"] * 100 for r in s], w, color=C_GREEN,
           label="α-β（最优优先排序）")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"d={x}" for x in depths])
    ax.set_xlabel("树的深度")
    ax.set_ylabel("相对 Minimax 节省的节点比例（%）")
    ax.set_title("(b) 剪枝带来的开销节省", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.2, ls=":", axis="y")
    ax.set_ylim(0, 100)

    o = d["orders_random"]
    txt = ("随机树（深度 6、分支 3，60 棵平均）不同访问顺序：\n"
           + "  ".join(f"{ {'natural':'自然','best_first':'最优优先','worst_first':'最差优先','random':'随机'}[k]} {v['nodes']:.0f}"
                        for k, v in o.items()))
    fig.text(0.5, -0.06, txt, ha="center", fontsize=8.8, color="#333333")
    fig.suptitle("题目三：Alpha-Beta 的规模效应与子节点顺序敏感性", fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig6_ab.png")


# --------------------------------------------------------------------------- #
# 图 7：题目四距离矩阵与最优对抗路径
# --------------------------------------------------------------------------- #
def fig_treasure():
    d = load("exp5_treasure.json")
    poi = d["poi"]
    mat = np.array(d["matrix"], dtype=float)

    sys.path.insert(0, os.path.dirname(HERE))
    from src.treasure import MAP, POSITIONS

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.9),
                             gridspec_kw={"width_ratios": [1, 1.12]})

    ax = axes[0]
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(len(poi)))
    ax.set_xticklabels(poi)
    ax.set_yticks(range(len(poi)))
    ax.set_yticklabels(poi)
    for i in range(len(poi)):
        for j in range(len(poi)):
            ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center",
                    fontsize=9.5, color="white" if mat[i, j] > mat.max() * 0.55 else "#222222")
    ax.set_title("(a) A* 求得的 6×6 最小移动代价矩阵", fontsize=10.5)
    ax.set_xlabel("终点"); ax.set_ylabel("起点")
    fig.colorbar(im, ax=ax, shrink=0.82, label="最小移动代价")

    ax = axes[1]
    n, m = len(MAP), len(MAP[0])
    ax.set_xlim(-0.5, m - 0.5); ax.set_ylim(n - 0.5, -0.5)
    ax.set_aspect("equal"); ax.axis("off")
    for i in range(n):
        for j in range(m):
            v = MAP[i][j]
            if v == "X":
                face, txt, col = "#4D4D4D", "", "#FFFFFF"
            elif v in ("A", "B"):
                face, txt, col = "#DCE9F7" if v == "A" else "#F7DEDC", v, C_BLUE if v == "A" else C_RED
            elif isinstance(v, str) and v.startswith("T"):
                face, txt, col = "#FFF2CC", v, "#7F6000"
            else:
                face = plt.cm.Greens(min(0.10 + int(v) / 14, 0.55))
                txt, col = str(v), "#222222"
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=face,
                                   edgecolor="white", lw=1.2))
            if txt:
                ax.text(j, i, txt, ha="center", va="center", fontsize=8.2,
                        color=col, fontweight="bold" if txt in ("A", "B") or txt.startswith("T") else "normal")
    pairs = d["pairs"]
    legs = [("A", "T3", C_BLUE, "-", "第 1 回合：A 取 T3"),
            ("T3", "T1", C_RED, "--", "第 2 回合：B 取 T1"),
            ("T1", "T2", C_BLUE, "-", "第 3 回合：A 取 T2"),
            ("T2", "T4", C_RED, "--", "第 4 回合：B 取 T4")]
    for a, b, color, ls, label in legs:
        path = [tuple(p) for p in pairs[f"{a}-{b}"]]
        xs = [p[1] for p in path]
        ys = [p[0] for p in path]
        ax.plot(xs, ys, ls, color=color, lw=2.4, alpha=0.9, label=label,
                solid_capstyle="round")
        ax.plot(xs[-1], ys[-1], "o", color=color, ms=5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2,
              frameon=False, fontsize=8.4)
    ax.set_title("(b) 深度 H=4 时的最优对抗路线（U=3）", fontsize=10.5)
    fig.suptitle("题目四：距离矩阵与博弈最优走法", fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig7_treasure.png")


# --------------------------------------------------------------------------- #
# 图 8：题目四不同深度的决策与开销
# --------------------------------------------------------------------------- #
def fig_treasure_h():
    d = load("exp5_treasure.json")
    sweep = d["sweep"]
    Hs = [r["H"] for r in sweep]

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.0))
    ax = axes[0]
    xs = np.arange(len(Hs))
    w = 0.26
    series = [("minimax", "Minimax", C_RED), ("ab_natural", "α-β（自然）", C_BLUE),
              ("ab_gain", "α-β（收益排序）", C_GREEN)]
    for k, (key, label, color) in enumerate(series):
        vals = [r[key]["nodes"] for r in sweep]
        bars = ax.bar(xs + (k - 1) * w, vals, w, color=color, label=label)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2, str(v), ha="center", fontsize=7.6)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"H={h}" for h in Hs])
    ax.set_ylabel("搜索访问的节点数")
    ax.set_title("(a) 三种搜索在四个深度下的节点开销", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8.6)
    ax.grid(alpha=0.2, ls=":", axis="y")
    ax.set_ylim(0, max(r["minimax"]["nodes"] for r in sweep) * 1.2)

    ax = axes[1]
    treasures = ["T1", "T2", "T3", "T4"]
    colors = [C_GRAY, C_BLUE, C_GREEN, C_PURPLE]
    for t, color in zip(treasures, colors):
        ys = [d["first_move"][str(h)][t] for h in Hs]
        ax.plot(Hs, ys, "o-", color=color, label=t, lw=1.9)
        ax.annotate(f"{ys[-1]:.0f}", (Hs[-1], ys[-1]), textcoords="offset points",
                    xytext=(6, 0), fontsize=8.5, color=color)
    ax.axhline(0, color="#BFBFBF", lw=0.8)
    ax.set_xticks(Hs)
    ax.set_xlabel("搜索深度 H")
    ax.set_ylabel("以该宝藏为首步时的博弈值 U")
    ax.set_title("(b) 首步选择的价值随深度变化", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="lower left")
    ax.grid(alpha=0.25, ls=":")
    fig.suptitle("题目四：搜索深度对决策与开销的影响（H=2 选 T2，H=4 选 T3）",
                 fontsize=11.5)
    fig.tight_layout()
    save(fig, "fig8_treasure_h.png")


if __name__ == "__main__":
    fig_maze()
    fig_heuristic()
    fig_weighted()
    fig_tie_and_k()
    fig_tree()
    fig_ab_scaling()
    fig_treasure()
    fig_treasure_h()
