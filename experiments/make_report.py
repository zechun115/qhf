"""生成实验报告 PDF（reportlab）。

运行：python experiments/make_report.py
输出：实验二_实验报告_邱浩峰_10245501462.pdf（项目根目录）
"""
from __future__ import annotations

import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle, PageBreak)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
OUT = os.path.join(ROOT, "实验二_实验报告_邱浩峰_10245501462.pdf")

pdfmetrics.registerFont(TTFont("MSYH", "C:/Windows/Fonts/msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-B", "C:/Windows/Fonts/msyhbd.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("MONO", "C:/Windows/Fonts/consola.ttf"))

INK = colors.HexColor("#222222")
BLUE = colors.HexColor("#1F3864")
ACC = colors.HexColor("#2E5A88")
LIGHT = colors.HexColor("#DCE9F7")
SAND = colors.HexColor("#F6E3C5")
GRID = colors.HexColor("#BFBFBF")
MUT = colors.HexColor("#595959")

S = {
    "body": ParagraphStyle("body", fontName="MSYH", fontSize=10.3, leading=17.5,
                           alignment=TA_JUSTIFY, textColor=INK, wordWrap="CJK",
                           spaceAfter=6, firstLineIndent=21),
    "body0": ParagraphStyle("body0", fontName="MSYH", fontSize=10.3, leading=17.5,
                            alignment=TA_JUSTIFY, textColor=INK, wordWrap="CJK",
                            spaceAfter=6),
    "h1": ParagraphStyle("h1", fontName="MSYH-B", fontSize=15, leading=22,
                         textColor=BLUE, spaceBefore=16, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="MSYH-B", fontSize=12, leading=18,
                         textColor=ACC, spaceBefore=12, spaceAfter=6),
    "cap": ParagraphStyle("cap", fontName="MSYH", fontSize=9, leading=13,
                          alignment=TA_CENTER, textColor=MUT, spaceBefore=3,
                          spaceAfter=10),
    "code": ParagraphStyle("code", fontName="MONO", fontSize=8.6, leading=12.5,
                           textColor=INK, backColor=colors.HexColor("#F5F6F8"),
                           borderPadding=6, leftIndent=6, rightIndent=6,
                           spaceBefore=4, spaceAfter=8),
    "bullet": ParagraphStyle("bullet", fontName="MSYH", fontSize=10.3, leading=17,
                             textColor=INK, spaceAfter=4, leftIndent=18,
                             bulletIndent=6, wordWrap="CJK"),
    "cover_t": ParagraphStyle("cover_t", fontName="MSYH-B", fontSize=24, leading=34,
                              alignment=TA_CENTER, textColor=BLUE),
    "cover_s": ParagraphStyle("cover_s", fontName="MSYH", fontSize=13, leading=22,
                              alignment=TA_CENTER, textColor=MUT),
}


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return json.load(f)


class Report:
    def __init__(self, path):
        self.story = []
        self.fig_n = 0
        self.tab_n = 0
        doc = BaseDocTemplate(path, pagesize=A4,
                              leftMargin=2.1 * cm, rightMargin=2.1 * cm,
                              topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                              title="实验二：搜索算法 实验报告",
                              author="邱浩峰 10245501462")
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

        def on_page(canv, doc_):
            canv.saveState()
            if doc_.page > 1:
                canv.setFont("MSYH", 8.2)
                canv.setFillColor(MUT)
                canv.drawString(doc_.leftMargin, A4[1] - 1.45 * cm,
                                "当代人工智能实验课 · 实验二：搜索算法")
                canv.drawRightString(A4[0] - doc_.rightMargin, A4[1] - 1.45 * cm,
                                     "邱浩峰  10245501462")
                canv.setStrokeColor(GRID)
                canv.setLineWidth(0.6)
                canv.line(doc_.leftMargin, A4[1] - 1.6 * cm,
                          A4[0] - doc_.rightMargin, A4[1] - 1.6 * cm)
            canv.setFont("MSYH", 8.5)
            canv.setFillColor(MUT)
            canv.drawCentredString(A4[0] / 2, 1.15 * cm, f"- {doc_.page} -")
            canv.restoreState()

        doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
        self.doc = doc

    # -- 快捷方法 ------------------------------------------------------------
    def h1(self, text):
        self.story.append(Paragraph(text, S["h1"]))

    def h2(self, text):
        self.story.append(Paragraph(text, S["h2"]))

    def p(self, text, style="body"):
        self.story.append(Paragraph(text, S[style]))

    def bullets(self, items):
        for it in items:
            self.story.append(Paragraph(it, S["bullet"], bulletText="•"))

    @staticmethod
    def _cjk_fallback(line: str) -> str:
        """Consolas 无中文字形：把非 ASCII 片段切换到雅黑。"""
        import re
        out, buf, mode = [], [], None
        for ch in line:
            cur = "cjk" if ord(ch) > 127 else "asc"
            if cur != mode and buf:
                seg = "".join(buf)
                out.append(f'<font name="MSYH">{seg}</font>' if mode == "cjk" else seg)
                buf = []
            mode = cur
            buf.append(ch)
        if buf:
            seg = "".join(buf)
            out.append(f'<font name="MSYH">{seg}</font>' if mode == "cjk" else seg)
        return "".join(out)

    def code(self, text):
        html = "<br/>".join(self._cjk_fallback(line.replace(" ", "&nbsp;"))
                            for line in text.split("\n"))
        self.story.append(Paragraph(html, S["code"]))

    def fig(self, name, caption, width=16.2):
        self.fig_n += 1
        img = Image(os.path.join(FIG, name))
        ratio = img.imageHeight / img.imageWidth
        img.drawWidth = width * cm
        img.drawHeight = width * cm * ratio
        img.hAlign = "CENTER"
        self.story.append(img)
        self.story.append(Paragraph(f"图 {self.fig_n}  {caption}", S["cap"]))
        return self.fig_n

    def tab(self, header, rows, caption, col_widths=None, align="CENTER",
            font_size=8.8, highlight_rows=()):
        self.tab_n += 1
        data = [header] + rows
        t = Table(data, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
        style = [
            ("FONT", (0, 0), (-1, 0), "MSYH-B", font_size),
            ("FONT", (0, 1), (-1, -1), "MSYH", font_size),
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("TEXTCOLOR", (0, 0), (-1, 0), BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), align),
            ("TOPPADDING", (0, 0), (-1, -1), 3.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFD")]),
        ]
        for r in highlight_rows:
            style.append(("BACKGROUND", (0, r + 1), (-1, r + 1), SAND))
        t.setStyle(TableStyle(style))
        self.story.append(t)
        self.story.append(Paragraph(f"表 {self.tab_n}  {caption}", S["cap"]))
        return self.tab_n

    def build(self):
        self.doc.build(self.story)


# =========================================================================== #
d1 = load("exp1_maze.json")
d2 = load("exp2_tiebreak.json")
d3 = load("exp3_weighted.json")
d4 = load("exp4_alphabeta.json")
d5 = load("exp5_treasure.json")
d6 = load("exp6_extension.json")

r = Report(OUT)

# --------------------------------------------------------------------------- #
# 封面
# --------------------------------------------------------------------------- #
r.story.append(Spacer(1, 3.4 * cm))
r.story.append(Paragraph("当代人工智能实验课", S["cover_s"]))
r.story.append(Spacer(1, 0.4 * cm))
r.story.append(Paragraph("实验二：搜索算法", S["cover_t"]))
r.story.append(Spacer(1, 0.3 * cm))
r.story.append(Paragraph("A* 最短路径 · Alpha-Beta 剪枝 · 综合博弈", S["cover_s"]))
r.story.append(Spacer(1, 2.6 * cm))
r.story.append(Paragraph(
    "姓名：邱浩峰　　学号：10245501462<br/><br/>2026 年 10 月 19 日", S["cover_s"]))
r.story.append(Spacer(1, 1.8 * cm))

overview = [
    ["题目", "算法", "题面预期输出", "本实现输出", "一致"],
    ["一 迷宫寻路", "A*（曼哈顿）", "8 点坐标序列", "8 点坐标序列", "是"],
    ["二 加权地形", "A*（代价加权）", "7", "7", "是"],
    ["三 博弈树", "Alpha-Beta 剪枝", "5", "5", "是"],
    ["四 宝藏分配 H=2", "A* + Minimax/α-β", "T2，-1", "T2，-1", "是"],
    ["四 宝藏分配 H=4", "A* + Minimax/α-β", "T3，3", "T3，3", "是"],
]
r.tab(["题目", "核心算法", "题面预期", "本实现输出", "一致"], overview[1:],
      "四道题目的运行结果与题面测试用例逐项比对（main.py 自动自检）",
      col_widths=[3.4 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm, 1.6 * cm])
r.story.append(PageBreak())

# --------------------------------------------------------------------------- #
# 1 实验目标
# --------------------------------------------------------------------------- #
r.h1("1  实验目标与总体说明")
r.p("本次实验围绕两类经典搜索算法展开：一是 A* 最优路径搜索，要求在栅格地图上分别处理"
    "单位代价（题目一）与加权地形（题目二）两种情形；二是博弈树搜索，要求实现 Minimax 与 "
    "Alpha-Beta 剪枝（题目三），并在“宝藏分配”综合题（题目四）中将 A* 与博弈搜索结合，"
    "求竞争环境下 MAX 玩家的最优首步。")
r.p("在完成给定测试用例的基础上，本报告的重点放在对照实验与结果分析上：围绕启发函数强度、"
    "f 值平局策略、启发函数可采纳性边界、子节点访问顺序、搜索深度与缓存策略共设计了 7 组"
    "对照实验，全部实验使用固定随机种子（可复现），数据由 experiments/run_experiments.py "
    "自动采集并保存为 JSON。所有代码、数据与插图的组织方式见附录 A。")

# --------------------------------------------------------------------------- #
# 2 算法设计
# --------------------------------------------------------------------------- #
r.h1("2  算法设计与实验设置")

r.h2("2.1  A* 搜索")
r.p("A* 的搜索状态为格子坐标 state = (row, col)。对每个状态维护三个量："
    "g(n) 为起点到 n 的实际累计代价，h(n) 为启发函数（估计 n 到终点的剩余代价下界），"
    "f(n) = g(n) + h(n) 为优先级。算法使用二叉堆实现的 OPEN 优先队列按 f 值出队，"
    "并用闭集（closed set）记录已扩展状态；同一状态允许重复入队，弹出时若发现已扩展过则"
    "直接丢弃（惰性删除），这种写法省去了堆内的 decrease-key 操作，实现简单且不破坏最优性。")
r.code(
"OPEN ← {(h(s), s)};  g[s] ← 0;  closed ← ∅\n"
"while OPEN 非空:\n"
"    n ← OPEN.pop_min()            # 按 (f, tie-break) 出队\n"
"    if n ∈ closed: continue       # 惰性删除旧条目\n"
"    closed ← closed ∪ {n};  expanded++\n"
"    if n = goal: 回溯 parent 得到路径; return\n"
"    for m ∈ neighbors(n):\n"
"        g' ← g[n] + cost(n→m)     # 进入 m 的地形代价\n"
"        if g' < g[m]: g[m] ← g'; parent[m] ← n; push (g'+h(m), m)")
r.p("四邻域移动，每步代价为“进入目标格”的代价：题目一中所有可通行格代价为 1；题目二中"
    "数字格按其权值计，S 格不产生代价，终点 E 按题面规定记 0（“最后一步没有代价”）。"
    "启发函数默认使用曼哈顿距离 |Δr| + |Δc|，它在 4 邻域、单步代价 ≥ 1 的地图上是剩余代价的"
    "下界（可采纳），且相邻格间 |h(n)−h(n′)| ≤ 1 ≤ 步代价（一致性），因此第一个被弹出的目标"
    "状态即最优解。此外实现中支持 h = 0（退化为 Dijkstra）、切比雪夫、欧氏三种对照启发函数、"
    "f 值相同时的三种平局策略，以及加权 A*（f = g + w·h，w &gt; 1 用最优性换速度）。")

r.h2("2.2  Minimax 与 Alpha-Beta 剪枝")
r.p("博弈树节点与题面一致：叶子节点持有评估值 value，内部节点持有子节点列表 children，"
    "根节点为 MAX 玩家。Minimax 自底向上回传数值：MAX 层取子节点最大值，MIN 层取最小值，"
    "评估顺序严格从左到右。Alpha-Beta 在 Minimax 递归过程中维护窗口 (α, β)：α 是 MAX 在"
    "当前路径上已能保证的下界，β 是 MIN 已能保证的上界。")
r.bullets([
    "<b>MAX 节点：</b>某子节点回传值 v 使 v ≥ β 时，父 MIN 节点存在取值 ≤ β 的替代选择，"
    "本分支后续兄弟不可能再被选中，触发剪枝；",
    "<b>MIN 节点：</b>某子节点回传值 v 使 v ≤ α 时，对称地剪去后续兄弟；",
    "剪枝只影响搜索开销，不改变根节点价值——报告中所有对照实验均验证了这一点。"])
r.p("为了量化开销，实现统计四个指标：访问节点总数、叶子评估数、剪枝触发次数，以及被剪枝"
    "实际跳过的节点数。此外提供四种子节点访问顺序：题面自然顺序、按子树静态评估值的“最优"
    "优先/最差优先”排序与随机顺序，用于考察访问顺序对剪枝效率的影响（见第 5.3 节）。")

r.h2("2.3  题目四的博弈状态建模")
r.p("题目四将两类算法结合：先用 A* 计算关键点两两之间的最小移动代价矩阵，再在博弈层做"
    "极小极大搜索。博弈状态设计为六元组：")
r.code("state = (pos_a, pos_b, remaining, score_a, score_b, player)\n"
       "  pos_a / pos_b : 双方当前坐标\n"
       "  remaining     : 未被夺取的宝藏集合\n"
       "  score_a/b     : 双方累计收益（Gain 之和）\n"
       "  player        : 0 = 轮到 A(MAX)，1 = 轮到 B(MIN)")
r.p("状态转移：当前玩家从 remaining 中选宝藏 Ti，收益增加 Gain = V_i − d(pos, Ti)，"
    "位置更新为 Ti，remaining 移除 Ti。到达深度 H 或宝藏取完时，以 U = Score_A − Score_B "
    "作为评价值。A 用 Alpha-Beta 最大化 U，B 最小化 U。由于距离矩阵与地图静态无关"
    "（经过其他宝藏不自动收集、玩家互不阻挡），24 对点对的 A* 结果可以预计算并复用。")

r.h2("2.4  实验设置与可复现性")
r.bullets([
    "运行环境：Windows 11 + Python 3.13.12，仅使用标准库，未使用第三方加速；",
    "随机迷宫/加权地图：固定种子生成，障碍率 28%（迷宫）与 15%（加权地形），每档规模 20 张；"
    "随机博弈树：分支因子 3、深度 2–7，每档 60 棵；",
    "时间指标受机器状态影响较大，报告以“访问/扩展节点数”为主要开销度量，时间仅作辅助；",
    "复现方式：依次运行 main.py、experiments/run_experiments.py、experiments/make_figures.py、"
    "experiments/make_report.py（见附录 A）。"])

# --------------------------------------------------------------------------- #
# 3 题目一
# --------------------------------------------------------------------------- #
r.h1("3  题目一：迷宫寻路")

r.h2("3.1  结果与最短路径的形成过程")
r.p("对题面 5×5 迷宫，A*（曼哈顿启发）返回 8 点坐标序列 (0,0)→(0,1)→(0,2)→(1,2)→(1,3)→"
    "(1,4)→(2,4)→(3,4)，共 7 步、代价 6，与预期输出一致；对“起点被障碍封死”的构造用例"
    "返回空列表。图 1 直观展示了搜索过程：格内数字为扩展次序，红色为最终路径。"
    "曼哈顿版本几乎沿一条“准直线”推进——它始终优先扩展 f 值最小、也就是“已走代价 + "
    "至少还需步数”最小的格子；而 h=0 版本（Dijkstra）按“已走代价”层层扩散，"
    "在障碍周围形成了明显的波前，直到代价预算耗尽才触及终点。")
r.fig("fig1_maze.png", "题面迷宫上 h=0 与曼哈顿启发函数的搜索过程对比（格内数字为扩展次序）", width=15.6)

r.h2("3.2  对照实验一：启发函数强度")
single = d1["single"]
rows = []
name_map = [("zero", "h = 0（Dijkstra）"), ("manhattan", "曼哈顿"),
            ("chebyshev", "切比雪夫"), ("euclidean", "欧氏（取整）")]
for k, label in name_map:
    v = single[k]
    rows.append([label, v["expanded"], v["generated"], v["max_open"], int(v["cost"])])
r.tab(["启发函数", "扩展节点", "生成节点", "OPEN 峰值", "路径代价"], rows,
      "题面 5×5 迷宫：四种启发函数的开销对比（最优代价均为 6）")

psize = d1["per_size"]
rows = []
for n in ["21", "41", "61", "81"]:
    row = [f"{n}×{n}"]
    for k in ("zero", "manhattan", "chebyshev", "euclidean"):
        row.append(f"{psize[n][k]['mean']:,.0f}")
    rows.append(row)
r.tab(["规模", "h = 0", "曼哈顿", "切比雪夫", "欧氏"], rows,
      "随机迷宫（障碍率 28%，每档 20 张）：平均扩展节点数")

r.fig("fig2_heuristic.png", "启发函数强度对搜索开销的影响：(a) 绝对扩展数，(b) 占可通行格比例，(c) 加权 A* 权衡",
      width=16.4)
r.p("<b>分析：</b>三种距离启发函数中，曼哈顿距离是 4 邻域下最紧的下界——剩余步数恰好等于"
    "曼哈顿距离（无障碍时取等号），因此它对“这个格子离终点还有多远”的估计最准确，"
    "f 值的排序能力最强。切比雪夫与欧氏（取整）都只是曼哈顿的下界（max(|Δr|,|Δc|) ≤ "
    "|Δr|+|Δc|），信息量更弱，搜索行为介于 Dijkstra 与曼哈顿之间。图 2(b) 显示，规模越大"
    "这种差距越被放大：81×81 地图上曼哈顿平均只需探索约 14% 的可通行格，而 h=0 需要约 70%"
    "——后者本质上要淹没整个“代价 &lt; 最优代价”的等高线区域才能确认最短路径。")
r.p("一个值得注意的细节：在 5×5 的小迷宫上切比雪夫反而比曼哈顿少扩展 2 个节点（12 对 14）。"
    "小地图上启发函数的“区分度”噪声很大，个别节点的入队次序就能改变扩展数量，"
    "这说明<b>评估启发函数必须在大规模统计下进行，单例对比不可靠</b>。")

r.h2("3.3  对照实验二：f 值平局策略")
rows = [[lbl, f"{d2[k]['expanded']:,.0f}", f"{d2[k]['generated']:,.0f}"]
        for k, lbl in [("none", "FIFO（按入队次序）"), ("h", "平局取 h 小（更深）"),
                       ("g", "平局取 h 大（更浅）")]]
r.tab(["平局策略", "平均扩展节点", "平均生成节点"], rows,
      "81×81 随机迷宫（20 张）：f 值相同时的三种出队次序")
r.fig("fig4_tie_k.png", "(a) 平局策略对比；(b) 启发缩放系数 k 的可采纳性边界实验（详见 4.3 节）", width=16.4)
r.p("<b>分析：</b>同样是最优解，仅仅改变 f 值相同节点的出队次序，扩展节点数就相差一倍以上"
    "（981 对 2000）。平局取 h 小意味着在同样“预算”的节点中优先推进离终点最近的，"
    "搜索带更窄；平局取 h 大则优先回头扩展浅层节点，接近广度优先，波前最宽。"
    "这解释了为什么优先队列的次序键设计成 (f, h) 而非单独的 f——这是零成本的工程优化。")

r.h2("3.4  拓展：加权 A* 的速度—最优性权衡")
rows = [[f"w = {x['w']}", f"{x['expanded']:,.0f}", f"×{x['cost_ratio']:.3f}"]
        for x in d1["weighted_astar"]]
r.tab(["启发权重 w", "平均扩展节点", "路径代价 / 最优代价"], rows,
      "加权 A*（h = w·曼哈顿，81×81 随机迷宫，20 张平均）")
r.p("把启发函数整体乘以 w &gt; 1 会破坏可采纳性，但可以换取速度。实测 w=1.2 即可将扩展节点"
    "从 981 降到 380（约 2.6 倍），而平均路径代价仅膨胀 2.4%；w 增大到 3 后节点数趋于平缓"
    "（304），代价膨胀到 22%。这说明<b>启发权重是一个“次优度预算”旋钮</b>："
    "在实时性要求高、对 2%~5% 的路径次优可以接受的场景（如游戏寻路）中非常实用；"
    "而在要求严格最优的场合必须保持 w = 1。")

# --------------------------------------------------------------------------- #
# 4 题目二
# --------------------------------------------------------------------------- #
r.h1("4  题目二：加权地形")

r.h2("4.1  结果与代价累计过程")
r.p("题面用例的最优路径为 (0,0)→(1,0)→(2,0)→(3,0)→(3,1)→(3,2)→(4,2)→(4,3)→(4,4)，"
    "总代价 7，与预期一致。表 6 逐步列出代价累计：前 8 步每进入一个数字格累加其权值，"
    "最后一步进入 E 按题面规定记 0。这条路径宁可绕行全部代价 1 的“平原”，"
    "也不穿过中部的 8/3 高价地形——直线穿越 (0,0)→(0,4)→(4,4) 的代价高达 2+1+1+1+1+1 = "
    "7 之外还有 8 的高价格，实际约 14，是最优解的两倍。")
trace = d3["trace"]
rows = [[f"({c[0]},{c[1]})", f"{w:.0f}", f"{g:.0f}"] for c, w, g in trace]
r.tab(["路径格 (row,col)", "进入代价", "累计 g"], rows,
      "最优路径的代价累计过程（E 的进入代价按 0 计）")
r.fig("fig3_weighted.png", "题面用例：(a) 最优路径与地形代价热力图；(b) 每步的 g 值累计", width=15.8)

r.h2("4.2  曼哈顿启发函数还是可采纳的吗？")
r.p("<b>结论：在“所有可通行格代价 ≥ 1、E 记 0”的前提下，曼哈顿距离仍然是可采纳且一致的"
    "启发函数。</b>理由：从任意格 n 到终点至少要走 |Δr|+|Δc| 步（几何下界），而每步代价"
    "至少为 1，故真实剩余代价 ≥ 曼哈顿距离，h 从不高估；终点本身 h=0 亦成立（E 记 0 只会让"
    "真实代价更小，不破坏下界性质）。又因相邻格 h 差 ≤ 1 ≤ 最小步代价，一致性也满足。")
r.p("但“可采纳”不等于“有效”。在权值 1–9 的随机加权地图（41×41，20 张）上，h=0 平均扩展 "
    f"{d3['random_unit']['zero']:,.0f} 个节点，曼哈顿也只降到 {d3['random_unit']['manhattan*1']:,.0f}——"
    "几乎毫无帮助。原因在于：真实路径代价约为步数 × 平均权值 5，而 h 只按 1/步估计，"
    "启发项在 f 中占比太小，搜索排序几乎退化为 Dijkstra。"
    "<b>启发函数的价值取决于它刻画真实代价结构的能力，而不只是地图尺寸。</b>"
    "一个直接的改进是：用全图最小单步代价 c_min 缩放，即 h = c_min × 曼哈顿，"
    "它仍可采纳（每步真实代价 ≥ c_min）且更贴近真实量级。")

r.h2("4.3  对照实验三：可采纳性边界在哪里")
rows = [[f"k = {x['k']:g}", f"{x['expanded']:,.0f}", f"×{x['cost_ratio']:.4f}",
         f"{x['suboptimal_rate']*100:.0f}%"] for x in d3["sweep_k"]]
r.tab(["缩放系数 k", "平均扩展节点", "代价 / 最优", "返回次优解比例"], rows,
      "地形权值 3–9 的 41×41 随机地图（20 张）：h = k·曼哈顿 的扫描实验")
r.p("在最小单步代价为 3 的地图上，k=3 是理论上保持可采纳的上限。实验结果与理论精确吻合："
    "k ≤ 3 时 20 张地图全部返回最优解；k 一旦越过下界（4.5、6），次优比例立即跳升到 55% "
    "和 100%，代价膨胀至 1.0033 与 1.067 倍，而扩展节点数从约 1400 骤降到 111——"
    "<b>可采纳性边界就是“速度换最优性”的悬崖</b>，越界一步，效率数量级提升，"
    "正确性立刻失守。工程上若允许有界误差，这是和 3.4 节加权 A* 等价的另一个旋钮。")
r.fig("fig4_tie_k.png", "（引用）(b) k 扫描：蓝色为扩展节点数（对数轴），红色为次优解比例", width=13.5)

r.h2("4.4  拓展：0 代价格会让曼哈顿失效——构造性反例")
zc = d3["zero_cost"]
r.p("若地图中存在代价为 0 的格子，上述论证全部失效：真实剩余代价可能小于剩余步数，"
    "曼哈顿开始<b>高估</b>，A* 失去最优性保证。在 60 张含 35% 零代价格的 15×15 随机地图上，"
    f"A*（曼哈顿）在 {zc['suboptimal']} 张（{zc['rate']*100:.1f}%）上返回了次优解，"
    f"平均代价差 {zc['mean_gap']}，最大 {zc['max_gap']:.0f}。最严重的用例中，"
    f"最优代价为 {zc['worst_case']['optimal_cost']:.0f}，A* 实际返回 "
    f"{zc['worst_case']['found_cost']:.0f}（差 {zc['worst_case']['gap']:.0f}，"
    "误差 28.6%），且它扩展的节点数（83）反而比求出最优解的 Dijkstra（152）更少——"
    "<b>不可采纳的启发函数不仅牺牲最优性，还会制造“搜索很快”的假象</b>，"
    "因为它系统地引导搜索偏离真正廉价的区域。")
r.tab(["指标", "Dijkstra（h=0）", "A*（曼哈顿，已不可采纳）"],
      [["返回路径代价", f"{zc['worst_case']['optimal_cost']:.0f}（最优）",
        f"{zc['worst_case']['found_cost']:.0f}（次优）"],
       ["扩展节点数", f"{zc['worst_case']['expanded_optimal']}",
        f"{zc['worst_case']['expanded_found']}"]],
      "最坏用例（15×15，35% 零代价格）：曼哈顿高估导致次优且“更快”的假象")

# --------------------------------------------------------------------------- #
# 5 题目三
# --------------------------------------------------------------------------- #
r.h1("5  题目三：极大极小博弈树的 Alpha-Beta 剪枝")

r.h2("5.1  结果与数值回传")
g = d4["given"]
r.p(f"对题面树，Minimax 与 Alpha-Beta（自然顺序）都返回 5，与预期一致。Minimax 访问全部 "
    f"{g['minimax']['nodes']} 个节点、评估 {g['minimax']['leaves']} 个叶子；"
    f"Alpha-Beta 只访问 {g['alpha_beta_natural']['nodes']} 个节点、评估 "
    f"{g['alpha_beta_natural']['leaves']} 个叶子。图 6 按真实执行顺序还原了回传与剪枝过程：")
r.fig("fig5_tree.png", "题面博弈树的 α-β 搜索：矩形内为节点回传值，灰色圆为被剪枝的叶子", width=15.2)
r.p("<b>剪枝依据（结合图中实例）：</b>① 根（MAX）处理完左子树后 α=5；② 左 MIN 节点处理完"
    "第一个 MAX 子节点（值 5）后 β=5，其第二个 MAX 子节点拿到窗口 (5, ∞)，评估叶子 6 得 "
    "6 ≥ β=5，父 MIN 已有更优的 5，叶子 9 被剪去（该 MAX 节点回传 6，这只是其真实值 9 的"
    "下界，不影响父层比较）；③ 右 MIN 节点回传 2 ≤ α=5，根节点不再可能被改善——"
    "但它已是最后一个孩子，无兄弟可剪。全树仅剪掉 1 个叶子，"
    "<b>这说明小树上剪枝机会有限，α-β 的收益必须在大树上观察</b>（见 5.3 节）。"
    "另注意被剪枝的 MAX 节点回传的是“≥ 真实值”的截断值，父层 MIN 取 min 时依然正确，"
    "这正是窗口不变量保证的性质。")

og = d4["orders_given"]
rows = [[lbl, str(og[k]["nodes"]), str(og[k]["leaves"]), str(og[k]["prunes"]),
         str(og[k]["cut"])] for k, lbl in
        [("natural", "自然顺序"), ("best_first", "最优优先"),
         ("worst_first", "最差优先"), ("random", "随机")]]
r.tab(["子节点顺序", "访问节点", "评估叶子", "剪枝触发", "实际跳过节点"], rows,
      "题面树：四种访问顺序（根价值恒为 5）")

r.h2("5.2  对照实验四：访问顺序决定剪枝效率")
o = d4["orders_random"]
rows = [[{"natural": "自然顺序", "best_first": "最优优先", "worst_first": "最差优先",
          "random": "随机"}[k], f"{v['nodes']:,.0f}", f"{v['prunes']:,.0f}"]
        for k, v in o.items()]
r.tab(["子节点顺序", "平均访问节点", "平均剪枝触发次数"], rows,
      "随机博弈树（深度 6、分支 3，60 棵平均）")
r.fig("fig6_ab.png", "Alpha-Beta 的规模效应与顺序敏感性：(a) 节点开销；(b) 相对 Minimax 的节省比例",
      width=16.2)
r.p("<b>分析：</b>三个现象值得展开。第一，最优优先排序把访问节点从 Minimax 的 1093 压到 "
    "125（深度 6），节省 88.6%，深度 7 时节省 92.9%——接近理论极限：完美排序下 α-β 只需"
    "评估约 O(b^(d/2)) 个叶子，本实验 b_eff 的实测值（表 12）与之趋势一致。第二，"
    "<b>“最差优先”剪枝触发次数最多（149.5 次）却最慢（992 节点）</b>：它每次都在树的"
    "深层剪掉很小的子树，而最优优先虽然触发次数少（46 次），但每次剪枝都发生在浅层、"
    "整枝跳过大子树。<b>剪枝的价值在“剪在哪”，不在“剪几次”</b>。第三，随机顺序与自然顺序"
    "几乎相同（412 对 416），说明自然顺序本身在随机树上也接近“随机”，"
    "不主动排序就享受不到 α-β 的理论收益。")
eb = d6["effective_branching"]
rows = [[f"d = {x['depth']}", str(x["leaves"]), f"{x['b_eff_minimax']:.2f}",
         f"{x['b_eff_ab']:.2f}", f"{x['b_eff_ab_best']:.2f}"] for x in eb]
r.tab(["深度", "叶子总数", "Minimax b_eff", "α-β 自然 b_eff", "α-β 最优排序 b_eff"], rows,
      "有效分支因子 b_eff（用访问节点数开 d 次方估计）")

# --------------------------------------------------------------------------- #
# 6 题目四
# --------------------------------------------------------------------------- #
r.h1("6  题目四：竞争环境下的宝藏分配")

r.h2("6.1  距离矩阵与状态设计")
r.p("对 A、B、T1–T4 六个关键点两两运行 A*（加权重叠地形 + 障碍 X），得到 6×6 最小移动"
    "代价矩阵（表 13、图 8a）。由于路径代价等于所进入格子的权值之和、且起点格不计代价，"
    "矩阵沿对角线对称，这也交叉验证了 A* 实现的正确性。几个关键数字主导了整局博弈："
    "A 离 T2 只有 4（全场最短），B 离 T3 只有 4，而 T4 远离一切（B→T4 为 10，T1→T4 达 12），"
    "却是 7 分的宝藏——谁最后被迫去取 T4，谁就要亏 5 分。")
poi = d5["poi"]
rows = [[poi[i]] + [f"{v:.0f}" for v in d5["matrix"][i]] for i in range(len(poi))]
r.tab(["起点＼终点"] + poi, rows, "A* 求得的 6×6 最小移动代价矩阵")

r.h2("6.2  H=2 与 H=4 的结果")
sw = {x["H"]: x for x in d5["sweep"]}
r.p("用 Minimax 与 Alpha-Beta 分别在深度 H=2、H=4 求解（两者结果完全一致，"
    "验证了剪枝不改变决策）：<b>H=2 时 A 的最优首步是 T2，最优收益差 U = −1；H=4 时变为 "
    "T3，U = 3</b>，均与题面预期输出一致。H=4 的最优对抗线为：A 取 T3（收益 −1）→ "
    "B 取 T1（+1）→ A 取 T2（0）→ B 被迫取 T4（−5），U = (−1+0) − (1−5) = 3。")
rows = []
for H in (2, 4):
    x = sw[H]
    rows.append([f"H = {H}",
                 f"{x['minimax']['move']}（U={x['minimax']['value']:.0f}）",
                 f"{x['ab_natural']['move']}（U={x['ab_natural']['value']:.0f}）",
                 f"{x['ab_natural']['nodes']} / {x['ab_natural']['prunes']}",
                 f"{x['ab_gain']['nodes']} / {x['ab_gain']['prunes']}"])
r.tab(["深度", "Minimax 首步", "α-β 首步", "α-β 节点/剪枝(自然)", "α-β 节点/剪枝(收益排序)"], rows,
      "两种算法、两种顺序在 H=2 / H=4 下的决策与开销")
r.fig("fig7_treasure.png", "题目四：(a) 距离矩阵；(b) H=4 最优对抗路线（蓝=A，红=B）", width=16.6)

r.h2("6.3  深度如何改变决策：弃子与奇偶性")
fm = d5["first_move"]
rows = [[f"H = {H}"] + [f"{fm[str(H)][t]:.0f}" for t in ("T1", "T2", "T3", "T4")]
        for H in (1, 2, 3, 4)]
r.tab(["深度", "首步 T1", "首步 T2", "首步 T3", "首步 T4"], rows,
      "以各宝藏为首步时的博弈值 U（正=A 优）", highlight_rows=(1, 3))
r.fig("fig8_treasure_h.png", "题目四：(a) 各深度的搜索开销；(b) 首步价值随深度的变化", width=16.2)
r.p("<b>为什么浅层与深层给出不同答案？</b>逐层拆解首步价值（表 15）：")
r.bullets([
    "<b>H=1（只看自己一步）：</b>T2 收益 6−4=2 最高，纯贪心选择；",
    "<b>H=2（A 一步 + B 一步）：</b>A 取 T2 后，B 从原地取 T3 收益 7−4=3，U=2−3=−1；"
    "此时 T2 仍是最不差的选择（其余首步 U ≤ −2）；",
    "<b>H=4（整局）：</b>T3 首步以 −1 的“弃子”开局，但换来两重好处——A 第二手能就近"
    "收获 T2（收益 0），而 B 的第二手被逼到 T1→T4，进入代价 12、收益 −5。"
    "U 提升到 3，比 T2 首步（U=1）高 2 分。"])
r.p("更深一层的观察是<b>深度奇偶性</b>：H 为偶数时最后一手是 B（对手），评价中包含"
    "“对手被迫收拾残局”的效应；H 为奇数时最后一手是 A 自己。因此 U 值不能跨深度直接比较"
    "（H=3 时 T2 首步 U=2，H=4 时 T3 首步 U=3），但同一深度内的排序是可靠的。"
    "这提示在实践中：<b>搜索深度必须与决策回合结构匹配</b>，偶数深度才能让 MAX 看到"
    "对手的完整应对。")

r.h2("6.4  搜索开销与工程优化")
gi = d6["gain_impl"]
rows = [["无缓存（每次收益现算 A*）", "80 次调用", f"{gi['naive']['time_ms']:.1f} ms", "1×"],
        ["按需计算 + 字典缓存", "24 次独立 A*", f"{gi['on_demand_cache']['time_ms']:.1f} ms",
         f"{gi['naive']['time_ms']/gi['on_demand_cache']['time_ms']:.0f}×"],
        ["预计算距离矩阵", "24 次独立 A*", f"{gi['precomputed']['time_ms']:.1f} ms",
         f"{gi['naive']['time_ms']/gi['precomputed']['time_ms']:.0f}×"]]
r.tab(["距离查询实现", "A* 调用", "H=4 完整求解耗时", "加速比"], rows,
      "题目四：距离缓存策略对照（含 α-β 与收益排序，结果均为 T3/U=3）")
r.p("H=4 时博弈搜索要计算 80 次收益，若每次都现场跑 A* 需要 5.6 ms；注意到状态中位置只会在 "
    "6 个关键点之间变化，把 24 对点对预计算成矩阵后降到 0.1 ms（约 56 倍）。"
    "结合收益排序的 α-β（37 节点，比自然顺序再省 21%），整题求解进入亚毫秒级。"
    "若地图或宝藏数增大，还可以进一步做状态转置缓存（同一 remaining 集合与双方位置的"
    "置换对称），但本局状态空间只有 4!×36 量级，缓存收益已足够。")

# --------------------------------------------------------------------------- #
# 7 拓展汇总
# --------------------------------------------------------------------------- #
r.h1("7  自设对照实验与拓展小结")
r.p("除各题内嵌的对照实验外，报告共完成 7 组系统性实验，汇总如下：")
rows = [
    ["E1 启发函数强度", "曼哈顿 vs h=0/切比雪夫/欧氏", "81×81 上曼哈顿仅探索 14% 可通行格，h=0 需 70%"],
    ["E2 平局策略", "(f,h) / (f,−h) / FIFO", "h 小优先比 h 大优先少扩展 51%"],
    ["E3 加权 A*", "w = 1~3", "w=1.2：节点 −61%，代价仅 +2.4%"],
    ["E4 可采纳性边界", "k = 0~6（min 代价=3）", "k≤3 全部最优；k=6 时 100% 次优但节点 −92%"],
    ["E5 零代价反例", "35% 零代价格 ×60 图", "46.7% 次优，最大代价差 8，且“扩展更少”假象"],
    ["E6 访问顺序", "4 种顺序 × 60 随机树", "最优优先节省 88.6%；最差优先剪枝次数最多却最慢"],
    ["E7 距离缓存", "无缓存/按需/预计算", "预计算使 H=4 求解从 5.6ms 降至 0.1ms"],
]
r.tab(["实验", "设置", "关键结论"], rows,
      "拓展实验一览（详细数据见对应章节）", col_widths=[3.2 * cm, 4.4 * cm, 8.2 * cm],
      align="LEFT")
r.p("这些实验共同的线索是：<b>搜索算法的工程表现由“信息质量”决定</b>——启发函数对真实代价"
    "结构的贴合程度（E1/E3/E4）、节点访问顺序对剪枝位置的塑造（E6）、以及把不变量"
    "（距离矩阵）从搜索循环中提出来的能力（E7）。三者都不改变算法的正确性框架，"
    "却带来数量级的性能差异。")

# --------------------------------------------------------------------------- #
# 8 总结
# --------------------------------------------------------------------------- #
r.h1("8  总结与思考")
r.p("本实验完整实现了 A*（含加权地形、四种启发函数、平局策略与加权变体）、Minimax 与 "
    "Alpha-Beta 剪枝，并在四道题目的全部给定测试用例上取得与预期一致的结果；"
    "在此之上通过 7 组对照实验量化了各设计决策的影响。三点主要收获：")
r.bullets([
    "<b>最优性来自可采纳性，速度来自紧致性。</b>曼哈顿距离在单位代价地图上是“恰好正确”的"
    "下界，而在加权地形上虽然仍可采纳、却因过于保守而退化为 Dijkstra；用最小单步代价缩放"
    "可以恢复部分效率，越过下界则立刻以次优为代价。可采纳性边界（4.3 节的 k=3）是可以被"
    "实验精确验证的理论预测。",
    "<b>剪枝效率由访问顺序决定。</b>同样的 α-β，最优优先排序在深度 7 的随机树上节省 93% "
    "的节点，最差优先反而几乎不省——剪枝要发生在浅层、整枝剪掉才有价值。"
    "这也解释了实际博弈引擎中“走法排序”为何是与搜索深度并列的核心技术。",
    "<b>博弈搜索的决策依赖深度与奇偶性。</b>题目四中 H=2 的贪心解（T2）与 H=4 的整局最优解"
    "（T3）不同：深层搜索能发现“弃子换先手”的策略，让对手被迫承担负收益。"
    "评价函数的绝对值不能跨深度比较，但同一深度内的相对排序支撑决策。"])
r.p("可能的后续方向：把加权 A* 与实时约束结合（如 Anytime Repairing A*）；在更大的宝藏"
    "博弈上引入转置表与迭代加深，观察 α-β 与记忆化叠加的收益；以及把访问顺序从静态评估"
    "升级为上一轮迭代的最佳走法（PV 排序）。")

# --------------------------------------------------------------------------- #
# 附录
# --------------------------------------------------------------------------- #
r.h1("附录 A  代码结构与复现方式")
r.code(
"实验二_搜索算法/\n"
"├── main.py                       # 四道题入口，自动比对题面预期输出\n"
"├── src/\n"
"│   ├── astar.py                  # A*：4 种启发 + 3 种平局策略 + 加权 A*\n"
"│   ├── game_tree.py              # Minimax / Alpha-Beta + 顺序重排 + 访问统计\n"
"│   └── treasure.py               # 题目四：距离矩阵 + 博弈状态 + 求解器\n"
"├── experiments/\n"
"│   ├── run_experiments.py        # E1~E7 数据采集（固定随机种子）\n"
"│   ├── make_figures.py           # 报告全部插图\n"
"│   ├── make_report.py            # 本报告 PDF 的生成脚本\n"
"│   ├── results/*.json            # 原始实验数据\n"
"│   └── figures/*.png\n"
"└── README.md")
r.p("复现步骤：① python main.py —— 输出四题结果并与预期自检；"
    "② python experiments/run_experiments.py —— 生成 results/*.json（约 10 秒）；"
    "③ python experiments/make_figures.py 与 make_report.py —— 重新生成插图与本报告。"
    "所有随机过程种子固定，任何机器上的数值结果与图表均一致。")

r.build()
print("report written:", OUT)
