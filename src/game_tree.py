"""极大极小 + Alpha-Beta 剪枝（题目三、题目四共用）。

节点定义与题面一致：
    class TreeNode:
        value     叶子节点得分
        children  非叶子节点子列表

为便于统计搜索开销，所有函数都可以返回
    (值, 访问的叶节点数, 访问的全部节点数, 剪枝次数)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


class TreeNode:
    def __init__(self, value: Optional[float] = None,
                 children: Optional[Sequence["TreeNode"]] = None):
        self.value = value
        self.children = list(children) if children is not None else []

    # -- 便于调试 ------------------------------------------------------------
    @property
    def is_leaf(self) -> bool:
        return not self.children

    def __repr__(self) -> str:  # pragma: no cover
        if self.is_leaf:
            return f"Leaf({self.value})"
        return f"Node({len(self.children)} children)"

    # -- 序列化 / 反序列化（配合题面的 JSON 输入） ---------------------------
    def to_dict(self) -> dict:
        if self.is_leaf:
            return {"value": self.value}
        return {"children": [c.to_dict() for c in self.children]}

    @staticmethod
    def from_dict(d: dict) -> "TreeNode":
        if "children" in d and d["children"] is not None:
            node = TreeNode(children=[TreeNode.from_dict(c) for c in d["children"]])
        else:
            node = TreeNode(value=d.get("value"))
        if "is_maximizing_player" in d:
            node.is_maximizing = bool(d["is_maximizing_player"])
        return node


@dataclass
class SearchStats:
    """搜索开销统计。"""
    node_visits: int = 0     # 访问（进入）的节点总数，含内部节点
    leaf_evals: int = 0      # 评估的叶节点数
    prunes: int = 0          # 发生的剪枝次数（被整枝跳过的分支数）
    cut_nodes: int = 0       # 因剪枝而未访问的节点估计数
    visited_ids: list = field(default_factory=list)   # 访问顺序（id）
    prune_ids: list = field(default_factory=list)     # 发生剪枝的节点（id）


# --------------------------------------------------------------------------- #
# 纯 Minimax（无剪枝），作为 Alpha-Beta 的对照
# --------------------------------------------------------------------------- #
def minimax(node: TreeNode, is_max: bool, stats: Optional[SearchStats] = None) -> float:
    if stats is None:
        stats = SearchStats()
    stats.node_visits += 1
    stats.visited_ids.append(id(node))
    if node.is_leaf:
        stats.leaf_evals += 1
        return node.value

    if is_max:
        best = float("-inf")
        for ch in node.children:
            best = max(best, minimax(ch, False, stats))
        return best
    else:
        best = float("inf")
        for ch in node.children:
            best = min(best, minimax(ch, True, stats))
        return best


# --------------------------------------------------------------------------- #
# Alpha-Beta 剪枝
# --------------------------------------------------------------------------- #
def alpha_beta(
    node: TreeNode,
    is_max: bool,
    alpha: float = float("-inf"),
    beta: float = float("inf"),
    stats: Optional[SearchStats] = None,
) -> float:
    """返回该子树对 MAX 玩家的价值。

    剪枝条件：
      - MAX 节点：某子节点返回值 v >= beta，则父 MIN 已有更小选择，后续兄弟不可能被选中，剪枝；
      - MIN 节点：某子节点返回值 v <= alpha，同理剪枝。
    """
    if stats is None:
        stats = SearchStats()
    stats.node_visits += 1
    stats.visited_ids.append(id(node))

    if node.is_leaf:
        stats.leaf_evals += 1
        return node.value

    if is_max:
        value = float("-inf")
        for i, ch in enumerate(node.children):
            value = max(value, alpha_beta(ch, False, alpha, beta, stats))
            alpha = max(alpha, value)
            if value >= beta:
                stats.prunes += 1
                stats.prune_ids.append(id(node.children[i]))
                stats.cut_nodes += _count_nodes(node.children[i + 1:])
                break
        return value
    else:
        value = float("inf")
        for i, ch in enumerate(node.children):
            value = min(value, alpha_beta(ch, True, alpha, beta, stats))
            beta = min(beta, value)
            if value <= alpha:
                stats.prunes += 1
                stats.prune_ids.append(id(node.children[i]))
                stats.cut_nodes += _count_nodes(node.children[i + 1:])
                break
        return value


def _count_nodes(nodes: Sequence[TreeNode]) -> int:
    return sum(1 + _count_inner(n) for n in nodes)


def _count_inner(node: TreeNode) -> int:
    return sum(1 + _count_inner(c) for c in node.children)


# --------------------------------------------------------------------------- #
# 子节点排序：Alpha-Beta 的效率高度依赖 "好分支优先"
# --------------------------------------------------------------------------- #
def order_children(node: TreeNode, strategy: str = "natural",
                   rng: Optional[random.Random] = None,
                   is_max: bool = True) -> TreeNode:
    """返回一棵按 strategy 重排了子节点顺序的新树（不改动原树）。

    strategy:
      natural     保持题面从左到右
      best_first  按子树的静态评估值"对当前玩家最有利"优先
      worst_first 反向
      random      随机打乱
    """
    if node.is_leaf:
        return TreeNode(value=node.value)
    kids = [order_children(c, strategy, rng, not is_max) for c in node.children]
    if strategy == "best_first":
        kids.sort(key=lambda c: static_value(c, not is_max), reverse=is_max)
    elif strategy == "worst_first":
        kids.sort(key=lambda c: static_value(c, not is_max), reverse=not is_max)
    elif strategy == "random":
        (rng or random).shuffle(kids)
    out = TreeNode(children=kids)
    if hasattr(node, "is_maximizing"):
        out.is_maximizing = node.is_maximizing
    return out


def static_value(node: TreeNode, is_max: bool = True) -> float:
    """静态评估：按层级交替取 max/min（只用于排序，不必最优）。"""
    if node.is_leaf:
        return node.value
    vals = [static_value(c, not is_max) for c in node.children]
    return max(vals) if is_max else min(vals)


# --------------------------------------------------------------------------- #
# 便捷入口：题目三
# --------------------------------------------------------------------------- #
def best_score(root: TreeNode, use_pruning: bool = True) -> float:
    return alpha_beta(root, True, stats=SearchStats()) if use_pruning \
        else minimax(root, True, stats=SearchStats())


def build_problem3_tree() -> TreeNode:
    """题目三测试用例的树结构。

    题面文字描述为 3 层，但 JSON 与构建示例中 min2 复用了 max2，
    形成 DAG。为忠实于 "从左到右评估" 的树语义，这里按树来构建：
        root(MAX) -> min1(MIN) -> max1(3,5), max2(6,9)
                  -> min2(MIN) -> max3(6,9), max4(1,2)
    其 Minimax 值为 max(min(5,9), min(9,2)) = max(5,2) = 5，与预期输出一致。
    """
    max1 = TreeNode(children=[TreeNode(value=3), TreeNode(value=5)])
    max2 = TreeNode(children=[TreeNode(value=6), TreeNode(value=9)])
    max3 = TreeNode(children=[TreeNode(value=6), TreeNode(value=9)])
    max4 = TreeNode(children=[TreeNode(value=1), TreeNode(value=2)])
    min1 = TreeNode(children=[max1, max2])
    min2 = TreeNode(children=[max3, max4])
    return TreeNode(children=[min1, min2])
