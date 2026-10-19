"""A* 搜索算法实现（迷宫寻路 / 加权地形）。

设计要点见实验报告第 2 节：
  - 状态 state = (row, col)
  - g(n)    = 从起点到 n 的实际累计代价
  - h(n)    = 启发函数，默认曼哈顿距离
  - f(n)    = g(n) + h(n)，优先队列按 (f, h) 排序
  - 采用 "闭集 + 惰性删除" 的写法：允许同一节点多次入队，
    弹出时若已以更优 g 值扩展过则跳过。这样实现简单，且保证 h 可采纳时最优。
"""
from __future__ import annotations

import heapq
import itertools
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

Cell = Tuple[int, int]
Grid = Sequence[Sequence[object]]


# --------------------------------------------------------------------------- #
# 启发函数
# --------------------------------------------------------------------------- #
def manhattan(a: Cell, b: Cell) -> int:
    """4 邻域下的最优启发：|dr| + |dc|。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev(a: Cell, b: Cell) -> int:
    """切比雪夫距离：max(|dr|, |dc|)，同样可采纳但通常弱于曼哈顿。"""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def euclidean(a: Cell, b: Cell) -> int:
    """欧氏距离下取整：可采纳，但在整数代价下信息量不及曼哈顿。"""
    dr, dc = a[0] - b[0], a[1] - b[1]
    return int((dr * dr + dc * dc) ** 0.5)


def zero(a: Cell, b: Cell) -> int:
    """h = 0：退化为 Dijkstra / 一致代价搜索（UCS），作为对照组。"""
    return 0


HEURISTICS: Dict[str, Callable[[Cell, Cell], float]] = {
    "zero": zero,
    "manhattan": manhattan,
    "chebyshev": chebyshev,
    "euclidean": euclidean,
}


# --------------------------------------------------------------------------- #
# 地图解析
# --------------------------------------------------------------------------- #
class GridMap:
    """统一的栅格地图封装。

    同时支持两种题型：
      - 迷宫：'S'/'.'/'E' 可通过（进入代价 1），'X' 为障碍；
      - 加权地形：'S'/'E' 或数字 0-9，数字即进入该格的代价。
    """

    def __init__(self, grid: Grid, weighted: bool = False, goal_is_free: bool = True):
        self.raw = [list(row) for row in grid]
        self.weighted = weighted
        self.goal_is_free = goal_is_free
        if not self.raw or not self.raw[0]:
            raise ValueError("地图不能为空")
        self.n_rows = len(self.raw)
        self.n_cols = len(self.raw[0])
        if any(len(r) != self.n_cols for r in self.raw):
            raise ValueError("地图各行列数必须一致")

    # -- 基础属性 ------------------------------------------------------------
    def in_bounds(self, c: Cell) -> bool:
        return 0 <= c[0] < self.n_rows and 0 <= c[1] < self.n_cols

    def is_wall(self, c: Cell) -> bool:
        return self.raw[c[0]][c[1]] in ("X", "x", "#")

    def enter_cost(self, c: Cell) -> float:
        """进入格子 c 的代价。"""
        v = self.raw[c[0]][c[1]]
        if v in ("S", "s"):
            return 0.0
        if v in ("E", "e"):
            return 0.0 if self.goal_is_free else 1.0
        if isinstance(v, (int, float)):
            return float(v)
        return 1.0  # '.', 'T1' 等普通可通过格

    def min_enter_cost(self) -> float:
        """全图最小单步代价，用于构造可采纳的加权启发函数。"""
        costs = [
            self.enter_cost((r, c))
            for r in range(self.n_rows)
            for c in range(self.n_cols)
            if not self.is_wall((r, c)) and self.enter_cost((r, c)) > 0
        ]
        return min(costs) if costs else 1.0

    def neighbors(self, c: Cell) -> List[Cell]:
        r, col = c
        out = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):  # 上 下 左 右
            nxt = (r + dr, col + dc)
            if self.in_bounds(nxt) and not self.is_wall(nxt):
                out.append(nxt)
        return out


# --------------------------------------------------------------------------- #
# A* 主体
# --------------------------------------------------------------------------- #
class SearchResult:
    """一次搜索的完整记录，供实验分析使用。"""

    def __init__(self, path: List[Cell], cost: float):
        self.path = path
        self.cost = cost
        self.expanded = 0        # 从 OPEN 中弹出并真正扩展的节点数
        self.generated = 0       # 生成（入队）的节点数
        self.max_open = 0        # OPEN 表峰值
        self.elapsed_ms = 0.0
        self.expanded_order: List[Cell] = []   # 扩展顺序（可视化用）
        self.g_at_expand: Dict[Cell, float] = {}

    @property
    def found(self) -> bool:
        return bool(self.path)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"SearchResult(cost={self.cost}, expanded={self.expanded}, "
                f"generated={self.generated}, path_len={len(self.path)})")


def astar(
    start: Cell,
    goal: Cell,
    grid: GridMap,
    heuristic: str | Callable[[Cell, Cell], float] = "manhattan",
    weight: float = 1.0,
    tie_break: str = "h",
    record_path: bool = True,
) -> SearchResult:
    """在 grid 上运行 A*，返回 SearchResult。

    参数
    ----
    heuristic : 启发函数名或可调用对象
    weight    : 启发权重 w，w=1 为标准 A*；w>1 为加权 A*（可能非最优但更快）
    tie_break : f 值相同时的次序。'h' 优先扩展 h 小（更靠近终点）的节点，
                'g' 反向，'none' 按插入序（FIFO）。
    """
    h_fn = HEURISTICS[heuristic] if isinstance(heuristic, str) else heuristic

    def h(n: Cell) -> float:
        return weight * h_fn(n, goal)

    t0 = time.perf_counter()
    counter = itertools.count()  # 保证堆元素可比较且插入序稳定
    h0 = h(start)
    start_second = h0 if tie_break == "h" else (-h0 if tie_break == "g" else 0)

    open_heap = [(h0, start_second, next(counter), start)]
    g_score: Dict[Cell, float] = {start: 0.0}
    parent: Dict[Cell, Optional[Cell]] = {start: None}
    closed: set[Cell] = set()

    res = SearchResult([], -1)
    res.max_open = 1

    while open_heap:
        f, _, _, cur = heapq.heappop(open_heap)

        # 惰性删除：同一节点可能多次入队，已扩展过的旧条目直接丢弃
        if cur in closed:
            continue
        closed.add(cur)
        res.expanded += 1
        res.expanded_order.append(cur)
        res.g_at_expand[cur] = g_score[cur]
        res.max_open = max(res.max_open, len(open_heap))

        if cur == goal:
            res.cost = g_score[cur]
            if record_path:
                path = []
                node: Optional[Cell] = cur
                while node is not None:
                    path.append(node)
                    node = parent[node]
                res.path = path[::-1]
            res.elapsed_ms = (time.perf_counter() - t0) * 1000
            return res

        for nxt in grid.neighbors(cur):
            tentative = g_score[cur] + grid.enter_cost(nxt)
            if tentative < g_score.get(nxt, float("inf")) - 1e-12:
                g_score[nxt] = tentative
                parent[nxt] = cur
                hn = h(nxt)
                if tie_break == "h":
                    key = (tentative + hn, hn, next(counter))
                elif tie_break == "g":
                    key = (tentative + hn, -hn, next(counter))
                else:
                    key = (tentative + hn, 0, next(counter))
                heapq.heappush(open_heap, (key[0], key[1], key[2], nxt))
                res.generated += 1

    res.cost = -1
    res.elapsed_ms = (time.perf_counter() - t0) * 1000
    return res


def dijkstra(start: Cell, goal: Cell, grid: GridMap) -> SearchResult:
    """h=0 的对照组。"""
    return astar(start, goal, grid, heuristic="zero")


# --------------------------------------------------------------------------- #
# 便捷函数（对应题目一、二的接口）
# --------------------------------------------------------------------------- #
def solve_maze(
    start: Cell,
    goal: Cell,
    grid: Grid,
    heuristic: str = "manhattan",
    return_nodes: bool = False,
):
    """题目一：无解返回 []，否则返回坐标序列。"""
    gm = GridMap(grid, weighted=False)
    res = astar(start, goal, gm, heuristic=heuristic)
    if return_nodes:
        return res
    return res.path


def solve_weighted(
    start: Cell,
    goal: Cell,
    grid: Grid,
    heuristic: str = "manhattan",
    return_nodes: bool = False,
):
    """题目二：返回最小总代价，无解返回 -1。"""
    gm = GridMap(grid, weighted=True, goal_is_free=True)
    # 地形权值可能大于 1，因此把曼哈顿距离按最小单步代价缩放，保持可采纳
    scale = gm.min_enter_cost()
    w = scale if scale > 1 else 1.0
    res = astar(start, goal, gm, heuristic=heuristic, weight=w)
    if return_nodes:
        return res
    return int(res.cost) if res.found else -1
