"""实验二 主入口：四道题的完整解答与自检。

运行：
    python main.py
输出：
    每题的标准输出 + 与预期结果的比对
"""
from __future__ import annotations

import json
import sys

from src.astar import solve_maze, solve_weighted
from src.game_tree import TreeNode, alpha_beta, best_score, build_problem3_tree, minimax
from src.treasure import TreasureGame, distance_matrix, pretty_matrix


def hr(title: str) -> None:
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


# --------------------------------------------------------------------------- #
# 题目一：迷宫寻路
# --------------------------------------------------------------------------- #
MAZE = [
    ["S", ".", ".", "X", "."],
    [".", "X", ".", ".", "."],
    [".", "X", ".", "X", "."],
    [".", ".", ".", "X", "E"],
    ["X", "X", ".", ".", "."],
]


def problem1():
    hr("题目一：迷宫寻路（A* + 曼哈顿距离）")
    path = solve_maze((0, 0), (3, 4), MAZE, heuristic="manhattan")
    print("输出：", path)
    expect = [(0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (1, 4), (2, 4), (3, 4)]
    print("预期：", expect)
    print("路径长度（步数）：", len(path) - 1 if path else 0)
    print("结果一致：", path == expect)

    # 无解用例
    print("无解用例 ->", solve_maze((0, 0), (0, 4), [["S", "X", ".", ".", "E"]]))
    return path


# --------------------------------------------------------------------------- #
# 题目二：加权地形
# --------------------------------------------------------------------------- #
WEIGHTED = [
    ["S", 1, 1, 8, 1],
    [1, 8, 3, 1, 1],
    [1, 8, 1, 8, 1],
    [1, 1, 1, 8, 1],
    [8, 8, 1, 1, "E"],
]


def problem2():
    hr("题目二：加权地形（进入代价 + A*）")
    cost = solve_weighted((0, 0), (4, 4), WEIGHTED, heuristic="manhattan")
    print("输出：", cost)
    print("预期： 7")
    print("结果一致：", cost == 7)
    return cost


# --------------------------------------------------------------------------- #
# 题目三：Alpha-Beta
# --------------------------------------------------------------------------- #
PROBLEM3_JSON = {
    "tree_structure": {
        "is_maximizing_player": True,
        "children": [
            {
                "is_maximizing_player": False,
                "children": [
                    {"is_maximizing_player": True,
                     "children": [{"value": 3}, {"value": 5}]},
                    {"is_maximizing_player": True,
                     "children": [{"value": 6}, {"value": 9}]},
                ],
            },
            {
                "is_maximizing_player": False,
                "children": [
                    {"is_maximizing_player": True,
                     "children": [{"value": 6}, {"value": 9}]},
                    {"is_maximizing_player": True,
                     "children": [{"value": 1}, {"value": 2}]},
                ],
            },
        ],
    }
}


def problem3():
    hr("题目三：极大极小博弈树（Alpha-Beta 剪枝）")
    tree = build_problem3_tree()
    v_ab = best_score(tree, use_pruning=True)
    v_mm = best_score(tree, use_pruning=False)
    print("Alpha-Beta 输出：", int(v_ab) if float(v_ab).is_integer() else v_ab)
    print("Minimax   输出：", int(v_mm) if float(v_mm).is_integer() else v_mm)
    print("预期： 5")
    print("结果一致：", v_ab == 5 and v_mm == 5)

    # 同时给出题面 JSON 的等价解析结果，说明输入格式兼容
    node = TreeNode.from_dict(PROBLEM3_JSON["tree_structure"])
    print("由 JSON 构造的树求得：", alpha_beta(node, True))
    return v_ab


# --------------------------------------------------------------------------- #
# 题目四：宝藏分配
# --------------------------------------------------------------------------- #
def problem4():
    hr("题目四：竞争环境下的宝藏分配（A* + Alpha-Beta）")
    dist, paths = distance_matrix()
    print("6x6 最小移动代价矩阵（A / B / T1..T4）：")
    print(pretty_matrix(dist))

    game = TreasureGame(dist)
    for H, expect in ((2, {"best_target": "T2", "best_value": -1}),
                      (4, {"best_target": "T3", "best_value": 3})):
        res_mm = game.minimax(H)
        res_ab = game.alpha_beta(H)
        out = {"best_target": res_ab["move"], "best_value": int(res_ab["value"])}
        print(f"\nH = {H}")
        print("  Minimax   :", {"best_target": res_mm["move"],
                                "best_value": int(res_mm["value"])},
              f"(节点 {res_mm['nodes']})")
        print("  Alpha-Beta:", out, f"(节点 {res_ab['nodes']}, 剪枝 {res_ab['prunes']} 次)")
        print("  预期      :", expect, " 一致：", out == expect)
        pv = " -> ".join(("A" if p == 0 else "B") + "取" + t for p, t, _ in res_ab["pv"])
        print("  最优对抗线:", pv)

    return dist, paths


def main() -> None:
    problem1()
    problem2()
    problem3()
    problem4()
    hr("全部题目运行完毕")


if __name__ == "__main__":
    main()
