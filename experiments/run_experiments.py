"""实验二 对照实验与数据采集脚本。

运行：
    python experiments/run_experiments.py
产出：
    experiments/results/*.json   原始数据（供报告引用，保证可复现）
    experiments/figures/*.png    报告插图
所有随机过程均使用固定种子，结果可复现。
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
import time
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.astar import (HEURISTICS, GridMap, astar, manhattan, solve_maze,
                       solve_weighted)
from src.game_tree import (SearchStats, TreeNode, alpha_beta, build_problem3_tree,
                           minimax, order_children, static_value)
from src.treasure import (MAP, POSITIONS, TREASURES, VALUES, TreasureGame,
                          distance_matrix)

RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(RES, exist_ok=True)
os.makedirs(FIG, exist_ok=True)


def dump(name: str, obj) -> None:
    with open(os.path.join(RES, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# 随机地图生成
# --------------------------------------------------------------------------- #
def reachable(grid: Sequence[Sequence], s: Tuple[int, int], g: Tuple[int, int]) -> bool:
    n, m = len(grid), len(grid[0])
    seen = {s}
    q = deque([s])
    while q:
        r, c = q.popleft()
        if (r, c) == g:
            return True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < m and (nr, nc) not in seen \
                    and grid[nr][nc] not in ("X", "#"):
                seen.add((nr, nc))
                q.append((nr, nc))
    return False


def gen_maze(n: int, p: float, seed: int) -> Optional[List[List[str]]]:
    rng = random.Random(seed)
    grid = [["X" if rng.random() < p else "." for _ in range(n)] for _ in range(n)]
    grid[0][0], grid[n - 1][n - 1] = "S", "E"
    return grid if reachable(grid, (0, 0), (n - 1, n - 1)) else None


def gen_weighted(n: int, p: float, lo: int, hi: int, seed: int) -> Optional[List[List]]:
    rng = random.Random(seed)
    grid = [["X" if rng.random() < p else rng.randint(lo, hi) for _ in range(n)]
            for n_ in range(n)]
    grid[0][0], grid[n - 1][n - 1] = "S", "E"
    return grid if reachable(grid, (0, 0), (n - 1, n - 1)) else None


def gen_zero_cost(n: int, seed: int) -> Optional[List[List]]:
    """地面代价含 0 的地图（约 35% 的格子代价为 0），用于检验可采纳性。"""
    rng = random.Random(seed)
    grid = []
    for _ in range(n):
        row = []
        for _ in range(n):
            x = rng.random()
            if x < 0.10:
                row.append("X")
            elif x < 0.45:
                row.append(0)
            else:
                row.append(rng.randint(1, 9))
        grid.append(row)
    grid[0][0], grid[n - 1][n - 1] = "S", "E"
    return grid if reachable(grid, (0, 0), (n - 1, n - 1)) else None


def collect_maps(gen, need: int, limit: int = 400, **kw):
    out = []
    for seed in range(limit):
        g = gen(seed=seed, **kw)
        if g is not None:
            out.append(g)
        if len(out) >= need:
            break
    return out


# --------------------------------------------------------------------------- #
# 实验 1：题目一 —— 启发函数与搜索开销
# --------------------------------------------------------------------------- #
MAZE = [["S", ".", ".", "X", "."],
        [".", "X", ".", ".", "."],
        [".", "X", ".", "X", "."],
        [".", ".", ".", "X", "E"],
        ["X", "X", ".", ".", "."]]


def exp1() -> dict:
    single = {}
    for h in ("zero", "manhattan", "chebyshev", "euclidean"):
        r = solve_maze((0, 0), (3, 4), MAZE, heuristic=h, return_nodes=True)
        single[h] = {"cost": r.cost, "path_len": len(r.path),
                     "expanded": r.expanded, "generated": r.generated,
                     "max_open": r.max_open, "elapsed_ms": round(r.elapsed_ms, 4),
                     "path": r.path}

    sizes = [21, 41, 61, 81]
    scale = {}
    per_size = {}
    for n in sizes:
        maps = collect_maps(gen_maze, need=20, n=n, p=0.28)
        rows = {h: [] for h in ("zero", "manhattan", "chebyshev", "euclidean")}
        for g in maps:
            for h in rows:
                r = astar((0, 0), (n - 1, n - 1), GridMap(g), heuristic=h)
                rows[h].append(r.expanded)
        per_size[n] = {h: {"mean": round(statistics.mean(v), 1),
                           "median": statistics.median(v),
                           "max": max(v)} for h, v in rows.items()}
        scale[n] = {h: round(statistics.mean(v) / len(maps[0]) ** 2 * 100, 3)
                    for h, v in rows.items()}  # 扩展节点占空格百分比

    # 加权 A*：w>1 用最优性换速度
    maps81 = collect_maps(gen_maze, need=20, n=81, p=0.28)
    wastar = []
    for w in (1.0, 1.2, 1.5, 2.0, 3.0):
        nodes, ratios = [], []
        for g in maps81:
            base = astar((0, 0), (80, 80), GridMap(g), heuristic="manhattan")
            r = astar((0, 0), (80, 80), GridMap(g), heuristic="manhattan", weight=w)
            nodes.append(r.expanded)
            ratios.append(r.cost / base.cost)
        wastar.append({"w": w, "expanded": round(statistics.mean(nodes), 1),
                       "cost_ratio": round(statistics.mean(ratios), 4)})

    data = {"single": single, "per_size": per_size, "pct_expanded": scale,
            "weighted_astar": wastar}
    dump("exp1_maze.json", data)
    return data


# --------------------------------------------------------------------------- #
# 实验 2：f 值相同时的打破平局策略
# --------------------------------------------------------------------------- #
def exp2() -> dict:
    maps = collect_maps(gen_maze, need=20, n=81, p=0.28)
    out = {}
    for tb in ("none", "h", "g"):
        nodes, gens = [], []
        for g in maps:
            r = astar((0, 0), (80, 80), GridMap(g), heuristic="manhattan", tie_break=tb)
            nodes.append(r.expanded)
            gens.append(r.generated)
        out[tb] = {"expanded": round(statistics.mean(nodes), 1),
                   "generated": round(statistics.mean(gens), 1)}
    dump("exp2_tiebreak.json", out)
    return out


# --------------------------------------------------------------------------- #
# 实验 3：加权地形与启发函数可采纳性
# --------------------------------------------------------------------------- #
def exp3() -> dict:
    # (a) 题面用例的代价累计
    wg = [["S", 1, 1, 8, 1],
          [1, 8, 3, 1, 1],
          [1, 8, 1, 8, 1],
          [1, 1, 1, 8, 1],
          [8, 8, 1, 1, "E"]]
    r = solve_weighted((0, 0), (4, 4), wg, heuristic="manhattan", return_nodes=True)
    gm = GridMap(wg, weighted=True, goal_is_free=True)
    cum = {c: r.g_at_expand[c] for c in r.path}
    trace = [(c, gm.enter_cost(c), cum[c]) for c in r.path]

    single = {}
    for h in ("zero", "manhattan"):
        rr = solve_weighted((0, 0), (4, 4), wg, heuristic=h, return_nodes=True)
        single[h] = {"cost": rr.cost, "expanded": rr.expanded,
                     "max_open": rr.max_open, "path": rr.path}

    # (b) 随机加权地图：地形权 1..9（最小单步代价为 1，曼哈顿仍可采纳）
    maps = collect_maps(gen_weighted, need=20, n=41, p=0.15, lo=1, hi=9)
    rows = {"zero": [], "manhattan*1": []}
    for g in maps:
        gm2 = GridMap(g, weighted=True, goal_is_free=True)
        rows["zero"].append(astar((0, 0), (40, 40), gm2, heuristic="zero").expanded)
        rows["manhattan*1"].append(astar((0, 0), (40, 40), gm2, heuristic="manhattan",
                                        weight=1.0).expanded)
    part_b = {k: round(statistics.mean(v), 1) for k, v in rows.items()}

    # (c) 地形权 3..9：最小单步代价为 3。扫描启发缩放系数 k，寻找可采纳性边界
    maps3 = collect_maps(gen_weighted, need=20, n=41, p=0.15, lo=3, hi=9)
    sweep_c = []
    for k in (0.0, 1.0, 3.0, 4.5, 6.0):
        nodes, ratios, bad = [], [], 0
        for g in maps3:
            gm3 = GridMap(g, weighted=True, goal_is_free=True)
            base = astar((0, 0), (40, 40), gm3, heuristic="zero")
            h = "zero" if k == 0 else "manhattan"
            rr = astar((0, 0), (40, 40), gm3, heuristic=h, weight=k or 1.0)
            nodes.append(rr.expanded)
            ratios.append(rr.cost / base.cost)
            bad += 1 if rr.cost > base.cost + 1e-9 else 0
        sweep_c.append({"k": k, "expanded": round(statistics.mean(nodes), 1),
                        "cost_ratio": round(statistics.mean(ratios), 4),
                        "suboptimal_rate": round(bad / len(maps3), 3)})

    # (d) 含 0 代价格：曼哈顿不再可采纳，A* 可能返回次优解
    maps0 = collect_maps(gen_zero_cost, need=60, n=15)
    subopt, gaps, worst = 0, [], None
    for seed, g in enumerate(maps0):
        gm0 = GridMap(g, weighted=True, goal_is_free=True)
        best = astar((0, 0), (14, 14), gm0, heuristic="zero")
        got = astar((0, 0), (14, 14), gm0, heuristic="manhattan")
        if got.cost > best.cost + 1e-9:
            subopt += 1
            gaps.append(got.cost - best.cost)
            if worst is None or got.cost - best.cost > worst["gap"]:
                worst = {"index": seed, "gap": got.cost - best.cost,
                         "optimal_cost": best.cost, "found_cost": got.cost,
                         "optimal_path": best.path, "found_path": got.path,
                         "expanded_optimal": best.expanded,
                         "expanded_found": got.expanded}
    part_d = {"cases": len(maps0), "suboptimal": subopt,
              "rate": round(subopt / len(maps0), 3),
              "mean_gap": round(statistics.mean(gaps), 2) if gaps else 0.0,
              "max_gap": max(gaps) if gaps else 0,
              "worst_case": worst,
              "worst_map": next((g for g in maps0), None)}

    if part_d["worst_case"] is not None:
        # 复现最坏用例的地图（同一批地图中的第 index 个）
        part_d["worst_map"] = maps0[part_d["worst_case"]["index"]]

    data = {"trace": [[list(c), w, g] for c, w, g in trace], "single": single,
            "random_unit": part_b, "sweep_k": sweep_c, "zero_cost": part_d,
            "weighted_map": wg, "path": r.path}
    dump("exp3_weighted.json", data)
    return data


# --------------------------------------------------------------------------- #
# 实验 4：Alpha-Beta
# --------------------------------------------------------------------------- #
def exp4() -> dict:
    tree = build_problem3_tree()
    s_mm = SearchStats()
    v_mm = minimax(tree, True, s_mm)
    s_ab = SearchStats()
    v_ab = alpha_beta(tree, True, stats=s_ab)

    given = {"minimax": {"value": v_mm, "nodes": s_mm.node_visits,
                         "leaves": s_mm.leaf_evals},
             "alpha_beta_natural": {"value": v_ab, "nodes": s_ab.node_visits,
                                    "leaves": s_ab.leaf_evals,
                                    "prunes": s_ab.prunes,
                                    "cut": s_ab.cut_nodes}}

    # 不同子节点顺序
    orders = {}
    for strat in ("natural", "best_first", "worst_first", "random"):
        rng = random.Random(7)
        t = order_children(tree, strat, rng)
        st = SearchStats()
        val = alpha_beta(t, True, stats=st)
        orders[strat] = {"value": val, "nodes": st.node_visits,
                         "leaves": st.leaf_evals, "prunes": st.prunes,
                         "cut": st.cut_nodes}

    # 随机树：规模与顺序的影响
    rng_tree = random.Random(2026)

    def rand_tree(depth: int, b: int) -> TreeNode:
        if depth == 0:
            return TreeNode(value=rng_tree.randint(0, 99))
        return TreeNode(children=[rand_tree(depth - 1, b) for _ in range(b)])

    N = 60
    scale = []
    for depth in range(2, 8):
        nodes_mm, nodes_ab, prunes = [], [], []
        best_nodes = []
        for i in range(N):
            t = rand_tree(depth, 3)
            s1 = SearchStats(); minimax(t, True, s1)
            s2 = SearchStats(); alpha_beta(t, True, stats=s2)
            t3 = order_children(t, "best_first")
            s3 = SearchStats(); alpha_beta(t3, True, stats=s3)
            nodes_mm.append(s1.node_visits)
            nodes_ab.append(s2.node_visits)
            best_nodes.append(s3.node_visits)
            prunes.append(s2.prunes)
        scale.append({
            "depth": depth,
            "leaves": 3 ** depth,
            "minimax": round(statistics.mean(nodes_mm), 1),
            "ab_natural": round(statistics.mean(nodes_ab), 1),
            "ab_best_first": round(statistics.mean(best_nodes), 1),
            "saving_natural": round(1 - statistics.mean(nodes_ab) / statistics.mean(nodes_mm), 3),
            "saving_best": round(1 - statistics.mean(best_nodes) / statistics.mean(nodes_mm), 3),
            "mean_prunes": round(statistics.mean(prunes), 1),
        })

    # 分支因子固定的顺序对照
    order_stats = {}
    for strat in ("natural", "best_first", "worst_first", "random"):
        nodes, prunes = [], []
        rng2 = random.Random(99)
        for i in range(N):
            t = rand_tree(6, 3)
            t2 = order_children(t, strat, rng2)
            st = SearchStats()
            alpha_beta(t2, True, stats=st)
            nodes.append(st.node_visits)
            prunes.append(st.prunes)
        order_stats[strat] = {"nodes": round(statistics.mean(nodes), 1),
                             "prunes": round(statistics.mean(prunes), 1)}

    data = {"given": given, "orders_given": orders, "scaling": scale,
            "orders_random": order_stats}
    dump("exp4_alphabeta.json", data)
    return data


# --------------------------------------------------------------------------- #
# 实验 5：题目四
# --------------------------------------------------------------------------- #
def exp5() -> dict:
    dist, paths = distance_matrix()
    game = TreasureGame(dist)

    # 距离矩阵
    poi = ["A", "B", "T1", "T2", "T3", "T4"]
    matrix = [[dist[(a, b)] for b in poi] for a in poi]

    # 深度扫描
    sweep = []
    for H in (1, 2, 3, 4):
        row = {"H": H}
        for name, kw in (("minimax", dict(use_pruning=False)),
                         ("ab_natural", dict(use_pruning=True, order="natural")),
                         ("ab_gain", dict(use_pruning=True, order="gain"))):
            r = game.solve(H, **kw)
            row[name] = {"value": r["value"], "move": r["move"],
                         "nodes": r["nodes"], "prunes": r["prunes"]}
        sweep.append(row)

    # 首步各选择的博弈值（考察 H 对决策的影响）
    first_move = {}
    for H in (1, 2, 3, 4):
        vals = {}
        for t in TREASURES:
            g0 = game.gain("A", t)
            child = (POSITIONS[t], POSITIONS["B"], frozenset(set(TREASURES) - {t}),
                     0.0 + g0, 0.0, 1)
            v, _, _ = game._search(child, H - 1, -float("inf"), float("inf"), False, "natural")
            vals[t] = v
        first_move[H] = vals

    # 访问顺序对剪枝的影响（H=4）
    order_cmp = {}
    for order in ("natural", "gain", "gain_asc"):
        r = game.solve(4, use_pruning=False, order=order)
        r2 = game.solve(4, use_pruning=True, order=order)
        order_cmp[order] = {"minimax_nodes": r["nodes"], "ab_nodes": r2["nodes"],
                            "prunes": r2["prunes"], "value": r2["value"],
                            "move": r2["move"]}

    data = {"poi": poi, "matrix": matrix, "sweep": sweep, "first_move": first_move,
            "order_cmp": order_cmp,
            "pairs": {f"{a}-{b}": paths[(a, b)] for a in poi for b in poi if a != b}}
    dump("exp5_treasure.json", data)
    return data


# --------------------------------------------------------------------------- #
# 打印汇总
# --------------------------------------------------------------------------- #
def show(d1, d2, d3, d4, d5) -> None:
    print("\n[实验1] 题面迷宫")
    for h, v in d1["single"].items():
        print(f"  {h:<10} expanded={v['expanded']:>3}  generated={v['generated']:>3} "
              f"max_open={v['max_open']:>2} cost={v['cost']}")
    print("\n[实验1] 随机迷宫平均扩展节点数")
    print("   n     zero  manhattan chebyshev euclidean")
    for n, v in d1["per_size"].items():
        print(f"  {n:>3}  {v['zero']['mean']:>7} {v['manhattan']['mean']:>9} "
              f"{v['chebyshev']['mean']:>9} {v['euclidean']['mean']:>9}")
    print("\n[实验1] 加权 A*")
    for r in d1["weighted_astar"]:
        print(f"  w={r['w']:<4} expanded={r['expanded']:>8} cost_ratio={r['cost_ratio']}")

    print("\n[实验2] 平局策略")
    for k, v in d2.items():
        print(f"  {k:<6} expanded={v['expanded']:>8} generated={v['generated']:>8}")

    print("\n[实验3] 题面用例代价累计")
    for c, w, g in d3["trace"]:
        print(f"  {tuple(c)}  进入代价={w}  累计 g={g}")
    print("  single:", {k: (v["cost"], v["expanded"]) for k, v in d3["single"].items()})
    print("  random(1..9):", d3["random_unit"])
    print("  sweep_k:", d3["sweep_k"])
    print("  zero-cost:", d3["zero_cost"])

    print("\n[实验4] 题面树")
    print("  ", d4["given"])
    print("  orders:", {k: (v["nodes"], v["prunes"]) for k, v in d4["orders_given"].items()})
    for r in d4["scaling"]:
        print(f"  depth={r['depth']} leaves={r['leaves']:>4} mm={r['minimax']:>8} "
              f"ab={r['ab_natural']:>8} ab_best={r['ab_best_first']:>8} "
              f"saving={r['saving_natural']}/{r['saving_best']}")
    print("  orders_random:", d4["orders_random"])

    print("\n[实验5] 距离矩阵")
    for row in d5["matrix"]:
        print("  ", row)
    for r in d5["sweep"]:
        print(f"  H={r['H']} mm={r['minimax']} ab={r['ab_natural']} ab_gain={r['ab_gain']}")
    print("  first_move:", d5["first_move"])
    print("  order_cmp:", d5["order_cmp"])


if __name__ == "__main__":
    t0 = time.perf_counter()
    d1 = exp1()
    d2 = exp2()
    d3 = exp3()
    d4 = exp4()
    d5 = exp5()
    show(d1, d2, d3, d4, d5)
    print(f"\n总耗时 {time.perf_counter() - t0:.2f}s")
