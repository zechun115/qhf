"""题目四：竞争环境下的宝藏分配。

状态建模：
    state = (pos_a, pos_b, remaining, score_a, score_b, player)
  - pos_a / pos_b : 双方当前坐标
  - remaining     : 尚未被夺取的宝藏集合（frozenset）
  - score_a/b     : 双方累计收益（Gain 之和）
  - player        : 0 表示轮到 A(MAX)，1 表示轮到 B(MIN)

状态转移：当前玩家从 remaining 中选一个宝藏 Ti，
    收益 += V_i - d(pos, Ti)，位置更新为 Ti，remaining 去掉 Ti。

终止：剩余宝藏为空，或达到搜索深度 H；以 U = score_a - score_b 作为评价值。
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Tuple

from .astar import GridMap, astar

Cell = Tuple[int, int]

# --------------------------------------------------------------------------- #
# 题面地图（7 x 7）
#   A  (0,0)    B  (6,6)
#   T1 (0,6)=9  T2 (2,2)=6  T3 (4,4)=7  T4 (6,0)=7
#   'X' 障碍，数字为进入代价，A/B/T 格代价为 1
# --------------------------------------------------------------------------- #
MAP: List[List[str]] = [
    ["A", 1, 1, "X", 2, 1, "T1"],
    [1, "X", 6, "X", 1, "X", 1],
    [1, 1, "T2", 1, 1, 1, 1],
    ["X", 1, "X", 8, "X", 1, "X"],
    [1, 1, 1, 1, "T3", 1, 1],
    [1, "X", 9, "X", 1, "X", 1],
    ["T4", 1, 1, "X", 1, 1, "B"],
]

POSITIONS: Dict[str, Cell] = {
    "A": (0, 0),
    "B": (6, 6),
    "T1": (0, 6),
    "T2": (2, 2),
    "T3": (4, 4),
    "T4": (6, 0),
}
VALUES: Dict[str, int] = {"T1": 9, "T2": 6, "T3": 7, "T4": 7}
TREASURES: Tuple[str, ...] = ("T1", "T2", "T3", "T4")
POIS: Tuple[str, ...] = ("A", "B", "T1", "T2", "T3", "T4")


def build_grid() -> GridMap:
    """把 'T1'/'T2' 等标记还原为代价 1 的普通格。"""
    grid = [["." if isinstance(v, str) and v.startswith("T") else v for v in row]
            for row in MAP]
    return GridMap(grid, weighted=True, goal_is_free=False)


def distance_matrix(heuristic: str = "manhattan"):
    """用 A* 计算 6 个关键点两两之间的最小移动代价及其路径。"""
    gm = build_grid()
    dist: Dict[Tuple[str, str], float] = {}
    paths: Dict[Tuple[str, str], List[Cell]] = {}
    for a, b in itertools.product(POIS, repeat=2):
        if a == b:
            dist[(a, b)] = 0
            paths[(a, b)] = [POSITIONS[a]]
            continue
        res = astar(POSITIONS[a], POSITIONS[b], gm, heuristic=heuristic,
                    weight=gm.min_enter_cost())
        dist[(a, b)] = res.cost
        paths[(a, b)] = res.path
    return dist, paths


# --------------------------------------------------------------------------- #
# 博弈树搜索
# --------------------------------------------------------------------------- #
class TreasureGame:
    """A(MAX) 与 B(MIN) 交替取宝的四回合博弈。"""

    def __init__(self, dist: Dict[Tuple[str, str], float], reward: Dict[str, int] = None):
        self.dist = dist
        self.reward = reward or VALUES
        self.counters: Dict[str, int] = {}
        self.pos_name = {v: k for k, v in POSITIONS.items()}  # 坐标 -> 点名

    # -- 工具 ---------------------------------------------------------------
    def gain(self, pos, t: str) -> float:
        name = pos if isinstance(pos, str) else self.pos_name[pos]
        return self.reward[t] - self.dist[(name, t)]

    def _reset(self) -> None:
        self.counters = {"nodes": 0, "leaves": 0, "prunes": 0, "cut": 0}

    def _candidates(self, state, order: str) -> List[str]:
        pos_a, pos_b, remaining, _, _, player = state
        pos = pos_a if player == 0 else pos_b
        cands = sorted(remaining)
        if order == "gain":
            cands.sort(key=lambda t: self.gain(pos, t), reverse=True)
        elif order == "gain_asc":
            cands.sort(key=lambda t: self.gain(pos, t))
        return cands

    # -- 对外接口 -----------------------------------------------------------
    def solve(self, depth: int, use_pruning: bool = False,
              order: str = "natural") -> dict:
        """返回 {'value','move','pv','nodes','leaves','prunes','cut'}。

        depth : 搜索层数 H（1 层 = 当前玩家走一步）
        order : 候选顺序；'natural' 按 T1..T4，'gain' 按即时收益降序，
                'gain_asc' 升序
        """
        self._reset()
        start = (POSITIONS["A"], POSITIONS["B"], frozenset(TREASURES), 0.0, 0.0, 0)
        value, move, pv = self._search(start, depth, -float("inf"), float("inf"),
                                       use_pruning, order)
        return {"value": value, "move": move, "pv": pv, **self.counters}

    def alpha_beta(self, depth: int, order: str = "natural") -> dict:
        return self.solve(depth, use_pruning=True, order=order)

    def minimax(self, depth: int, order: str = "natural") -> dict:
        return self.solve(depth, use_pruning=False, order=order)

    # -- 核心递归 -----------------------------------------------------------
    def _search(self, state, depth: int, alpha: float, beta: float,
                use_pruning: bool, order: str):
        pos_a, pos_b, remaining, sa, sb, player = state
        self.counters["nodes"] += 1

        # 终止：深度耗尽或宝藏取完
        if depth == 0 or not remaining:
            self.counters["leaves"] += 1
            return sa - sb, None, []

        cands = self._candidates(state, order)
        maximizing = (player == 0)
        best_val = -float("inf") if maximizing else float("inf")
        best_move, best_pv = None, []

        for i, t in enumerate(cands):
            pos = pos_a if player == 0 else pos_b
            g = self.gain(pos, t)
            if maximizing:
                child = (POSITIONS[t], pos_b, remaining - {t}, sa + g, sb, 1)
            else:
                child = (pos_a, POSITIONS[t], remaining - {t}, sa, sb + g, 0)

            v, _, pv = self._search(child, depth - 1, alpha, beta, use_pruning, order)

            improved = (v > best_val) if maximizing else (v < best_val)
            if improved:
                best_val, best_move = v, t
                best_pv = [(player, t, g)] + pv

            if maximizing:
                alpha = max(alpha, best_val)
                if use_pruning and best_val >= beta:
                    self.counters["prunes"] += 1
                    self.counters["cut"] += self._subtree_size(len(cands) - i - 1, depth - 1)
                    break
            else:
                beta = min(beta, best_val)
                if use_pruning and best_val <= alpha:
                    self.counters["prunes"] += 1
                    self.counters["cut"] += self._subtree_size(len(cands) - i - 1, depth - 1)
                    break

        return best_val, best_move, best_pv

    @staticmethod
    def _subtree_size(n_siblings: int, depth: int) -> int:
        """被剪枝跳过的节点数估算（按每层最多 n 个候选展开）。"""
        if n_siblings <= 0:
            return 0
        total, frontier = 0, n_siblings
        for _ in range(max(1, depth)):
            total += frontier
            frontier *= max(1, n_siblings)
        return total


def pretty_matrix(dist: Dict[Tuple[str, str], float]) -> str:
    lines = ["      " + "".join(f"{p:>6}" for p in POIS)]
    for a in POIS:
        lines.append(f"{a:>5} " + "".join(f"{dist[(a, b)]:>6.0f}" for b in POIS))
    return "\n".join(lines)
