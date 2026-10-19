# 实验二：搜索算法（A\* 与 Alpha-Beta 剪枝）

当代人工智能实验课 · 实验二

GitHub 仓库：**https://github.com/zechun115/qhf.git**（本实验全部代码位于 **homework2** 分支）

## 一、环境与运行方式

- Python 3.13（核心代码无第三方依赖，仅标准库；图表与报告生成需要 `matplotlib / reportlab`）
- 所有随机实验使用固定种子，结果可完全复现

```bash
# 运行四道题的标准解答与自检（输出与题面测试用例逐一比对）
python main.py

# 运行全部对照实验（写入 experiments/results/*.json）
python experiments/run_experiments.py

# 重新生成报告全部插图（写入 experiments/figures/*.png）
python experiments/make_figures.py
```

## 二、文件结构

```
├── main.py                      # 四道题入口：题目一 ~ 题目四的标准输出 + 自检
├── src/
│   ├── astar.py                 # A*（迷宫 / 加权地形通用），4 种启发函数 + 平局策略 + 加权 A*
│   ├── game_tree.py             # Minimax、Alpha-Beta（含访问统计、子节点重排）
│   └── treasure.py              # 题目四：距离矩阵、博弈状态、Minimax / Alpha-Beta 求解
├── experiments/
│   ├── run_experiments.py       # 实验 E1~E7：数据采集（随机种子固定）
│   ├── make_figures.py          # 报告插图生成
│   ├── make_report_short.py     # 提交版实验报告 PDF 生成（≤5 页）
│   ├── results/*.json           # 原始实验数据
│   └── figures/*.png            # 报告插图
└── 实验二_实验报告_邱浩峰_10245501462.pdf   # 提交版报告（4 页，开头附本仓库链接）
```

## 三、四道题的接口与结果

| 题目 | 函数 | 输出 | 题面预期 |
| --- | --- | --- | --- |
| 一 迷宫寻路 | `solve_maze(start, goal, grid)` | 坐标序列，无解返回 `[]` | 8 点路径 ✅ |
| 二 加权地形 | `solve_weighted(start, goal, grid)` | 最小总代价，无解返回 `-1` | 7 ✅ |
| 三 博弈树 | `best_score(root)` / `alpha_beta` | MAX 视角最佳得分 | 5 ✅ |
| 四 宝藏分配 | `TreasureGame.alpha_beta(H)` | `{"best_target", "best_value"}` | H=2: T2/-1；H=4: T3/3 ✅ |

题目四的距离矩阵（A\* 求得，行=起点，列=终点）：

|     | A  | B  | T1 | T2 | T3 | T4 |
| --- | -- | -- | -- | -- | -- | -- |
| A   | 0  | 12 | 10 | 4  | 8  | 8  |
| B   | 12 | 0  | 8  | 8  | 4  | 10 |
| T1  | 10 | 8  | 0  | 6  | 6  | 12 |
| T2  | 4  | 8  | 6  | 0  | 6  | 6  |
| T3  | 8  | 4  | 6  | 6  | 0  | 6  |
| T4  | 8  | 10 | 12 | 6  | 6  | 0  |

## 四、实现要点

1. **A\***：状态 `(row, col)`；`f = g + h`，二叉堆优先队列；闭集 + 惰性删除；支持
   `h=0 / 曼哈顿 / 切比雪夫 / 欧氏`、f 值平局策略（`h / g / FIFO`）与加权 A\*（`h = w·h`）。
2. **加权地形**：进入格子的代价 = 地形权值，终点 E 按 0 计；启发函数按全图最小单步代价
   缩放以保持可采纳性。
3. **Alpha-Beta**：MAX 节点 `v ≥ β` 剪枝、MIN 节点 `v ≤ α` 剪枝；统计访问节点数、
   叶子评估数、剪枝次数与被跳过的节点数，支持四种子节点访问顺序。
4. **题目四状态**：`(pos_a, pos_b, remaining, score_a, score_b, player)`；
   `Gain = V − d(·,·)`，深度 H 层后以 `U = Score_A − Score_B` 作为评价值。
