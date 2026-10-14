"""生成实验报告 HTML，并用 Edge 无头模式打印为 PDF（紧凑 2 页版）。

用法：
    python report/build_report.py --name 邱浩峰 --sid 10245501462
    python report/build_report.py --html-only

版式为 A4、限 2 页（同时也满足课程「不超过 5 页」的要求）；
正文第一行即 GitHub 仓库链接（作业要求）。
另有 4 页详版：report/_archive/报告_4页详版.pdf（由 build_report_5page.py 生成）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import FIGURES_DIR, METRICS_DIR, REPORT_DIR  # noqa: E402

REPO_URL = "https://github.com/zechun115/qhf"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def load(name: str) -> dict:
    with open(METRICS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def fig_uri(name: str) -> str:
    return (FIGURES_DIR / f"{name}.png").as_uri()


CSS = """
@page { size: A4; margin: 10mm 11mm 9mm 11mm; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
  font-size: 7.9pt; line-height: 1.40; color: #16202e;
}
.repo-line {
  display: flex; align-items: center; gap: 6px;
  background: #0f172a; color: #fff; padding: 4px 9px; border-radius: 4px;
  font-size: 8.2pt; margin-bottom: 6px;
}
.repo-line .tag { background: #2563eb; border-radius: 3px; padding: 1px 5px;
  font-size: 7pt; font-weight: 600; letter-spacing: .4px; }
.repo-line a { color: #7dd3fc; text-decoration: none; font-weight: 600;
  font-family: Consolas, monospace; }
h1 { font-size: 13.5pt; margin: 1px 0 2px; color: #0b1220; letter-spacing: .2px; }
h2 {
  font-size: 9.2pt; margin: 8px 0 4px; padding: 1px 0 1px 7px;
  border-left: 3px solid #2563eb; color: #0b1220; page-break-after: avoid;
}
h3 { font-size: 8.4pt; margin: 6px 0 2px; color: #1e3a8a; page-break-after: avoid; }
p { margin: 0 0 4px; text-align: justify; }
b, strong { color: #0b1220; }
.meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 7.4pt;
  color: #475569; margin-bottom: 5px; }
.meta span b { color: #16202e; }
.abstract {
  background: #f1f5f9; border-left: 3px solid #64748b; border-radius: 3px;
  padding: 5px 8px; margin: 4px 0 3px; font-size: 7.8pt;
}
.callout {
  background: #eff6ff; border-left: 3px solid #2563eb; border-radius: 3px;
  padding: 4px 8px; margin: 4px 0; font-size: 7.6pt;
}
.callout.warn { background: #fff7ed; border-left-color: #d97706; }
.callout .ct { font-weight: 700; color: #1d4ed8; margin-right: 3px; }
.callout.warn .ct { color: #b45309; }
table { width: 100%; border-collapse: collapse; font-size: 7.1pt; margin: 3px 0 4px; }
th { background: #1e293b; color: #fff; font-weight: 600; padding: 2.5px 4px;
  text-align: center; }
td { padding: 2.2px 4px; border-bottom: 1px solid #e2e8f0; text-align: center; }
tr:nth-child(even) td { background: #f8fafc; }
td.l { text-align: left; }
tr.best td { background: #eff6ff; font-weight: 700; color: #1d4ed8; }
.figrow { display: flex; gap: 7px; margin: 3px 0 4px; page-break-inside: avoid; }
.figrow img { width: 100%; border: 1px solid #e2e8f0; border-radius: 3px; }
.figrow.half > div { flex: 1; }
.figrow.full img { width: 82%; display: block; margin: 0 auto; }
ul, ol { margin: 1px 0 4px 14px; padding: 0; }
li { margin-bottom: 1px; }
code { font-family: Consolas, "Courier New", monospace; font-size: 7.1pt;
  background: #f1f5f9; padding: 0 2px; border-radius: 2px; }
.hl { color: #1d4ed8; font-weight: 700; }
.neg { color: #b91c1c; font-weight: 700; }
.footnote { font-size: 6.7pt; color: #64748b; border-top: 1px solid #e2e8f0;
  padding-top: 3px; margin-top: 5px; }
"""


def table(headers, rows, left_cols=(), best_row=None):
    out = ["<table><thead><tr>"]
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for i, r in enumerate(rows):
        cls = ' class="best"' if best_row is not None and i == best_row else ""
        cells = "".join(
            f'<td class="l">{c}</td>' if j in left_cols else f"<td>{c}</td>"
            for j, c in enumerate(r)
        )
        out.append(f"<tr{cls}>{cells}</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def build_html(student_name: str = "", student_id: str = "") -> str:
    ds = load("dataset_summary.json")
    pre = load("preprocess_ablation.json")
    feat = load("feature_ablation.json")
    tune = load("model_tuning.json")
    cv = load("cv_results.json")
    diag = load("best_model_diagnostics.json")
    final = load("final_model.json")
    summary = load("experiment_summary.json")

    n_train, n_val, n_test = ds["n_train_split"], ds["n_val"], ds["n_test"]

    # ---------------- 预处理消融表 ----------------
    pre_rows = [[r["name"].split("_", 1)[0], r["name"].split("_", 1)[1],
                 f"{r['avg_tokens']:.0f}", f"{r['accuracy']:.4f}", f"{r['macro_f1']:.4f}"]
                for r in pre["rows"]]
    pre_best = max(range(len(pre_rows)), key=lambda i: float(pre_rows[i][3]))

    # ---------------- 特征消融表 ----------------
    feat_rows = [[r["name"].split("_", 1)[0], r["name"].split("_", 1)[1],
                  f"{r['n_features']:,}", f"{r['accuracy']:.4f}", f"{r['macro_f1']:.4f}"]
                 for r in feat["rows"]]
    feat_best = max(range(len(feat_rows)), key=lambda i: float(feat_rows[i][3]))

    # ---------------- 模型主表 ----------------
    model_rows, best_idx, best_key = [], 0, (-1, -1)
    for i, m in enumerate(["NB", "LR", "SVM", "MLP"]):
        b, c = tune["best"][m], cv[m]
        if (b["accuracy"], b["macro_f1"]) > best_key:
            best_key, best_idx = (b["accuracy"], b["macro_f1"]), i
        model_rows.append([m, b["params"], f"{b['accuracy']:.4f}", f"{b['macro_f1']:.4f}",
                           f"{c['cv_accuracy_mean']:.4f}±{c['cv_accuracy_std']:.4f}",
                           f"{b['train_seconds']:.1f}s"])

    # ---------------- 类别级表现 ----------------
    pc = diag["per_class"]
    pc_rows = [[c, f"{v['f1']:.3f}", v["support"]] for c, v in pc.items()]
    worst = min(pc_rows, key=lambda r: float(r[1]))
    confusions = diag["error_analysis"]["top_confusions"][:3]
    conf_txt = "、".join(f"{e['true']}→{e['pred']}（{e['count']}）" for e in confusions)

    # MLP 两阶段调参关键数字
    mlp_main = {r["params"]: r["accuracy"] for r in tune["rows"]
                if r["model"] == "MLP" and r["grid_stage"] == "主网格"}
    mlp_h50 = next(v for k, v in mlp_main.items() if "(50,)" in k)
    mlp_h200 = next(v for k, v in mlp_main.items() if "(200,)" in k)
    mlp_h100 = next(v for k, v in mlp_main.items()
                    if k.startswith("hidden_layer_sizes=(100,)"))
    mlp_best = tune["best"]["MLP"]["accuracy"]
    mlp_alpha_best = tune["best"]["MLP"]["params"]

    sel_model = summary["selected_model"]
    sel_params = summary["selected_params"]
    sel_acc, sel_f1 = summary["validation_accuracy"], summary["validation_macro_f1"]
    fin_acc, fin_f1 = diag["accuracy"], diag["macro_f1"]
    cv_sel = cv[sel_model]
    speed_ratio = tune["best"]["MLP"]["train_seconds"] / max(
        tune["best"][sel_model]["train_seconds"], 0.01)

    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>实验一报告</title>
<style>{CSS}</style></head><body>

<div class="repo-line"><span class="tag">GitHub</span>
  <span>代码仓库：</span><a href="{REPO_URL}">{REPO_URL}</a>
  <span style="opacity:.75">（全部代码 / 数据 / 结果 / 图表 / 本报告）</span></div>

<h1>当代人工智能实验一：新闻组文本 10 分类</h1>
<div class="meta">
  <span><b>姓名</b>：{student_name or '（待填写）'}</span>
  <span><b>学号</b>：{student_id or '（待填写）'}</span>
  <span><b>随机种子</b>：42</span>
  <span><b>环境</b>：Python 3.13 / scikit-learn 1.9 / Windows 11</span>
</div>

<div class="abstract"><b>摘要</b>　在 7,368 条 / 10 类新闻组文本上，按「分层 8:2 划分 →
预处理消融 → 特征消融 → 四模型调参 → 交叉验证 → 预测」的固定流程，<b>只以验证集指标</b>做全部选择。
最有价值的发现是一个反直觉结论：<b>清洗并非越多越好</b>——最轻量归一化（0.9342）显著优于
「去邮件头 + 去引用 + 去停用词」的完整清洗（0.9159），因为引用行与邮件头本身携带主题线索。
最终按事先设定的规则锁定 <b>{sel_model}（{sel_params}）</b>，验证准确率
<span class="hl">{sel_acc:.4f}</span>、Macro-F1 <span class="hl">{sel_f1:.4f}</span>，
5 折交叉验证 <b>{cv_sel['cv_accuracy_mean']:.4f} ± {cv_sel['cv_accuracy_std']:.4f}</b>，
并对无标签测试集输出 2,457 条预测。</div>

<h2>1　问题与假设</h2>
<p>任务是把新闻组帖子分到 10 个主题类。本实验把三个<b>可被数据证伪</b>的问题作为主线，
每个假设都配一个只改单一因素的对照：</p>
<ul>
<li><b>H1（预处理）</b>：邮件头、引用回复、停用词属于噪声，清洗后应提升泛化性能；</li>
<li><b>H2（特征表示）</b>：IDF 加权与更大词表能提升性能，bigram 能补充短语级线索；</li>
<li><b>H3（模型选择）</b>：TF-IDF 特征高度稀疏（稀疏度 99.7%），线性模型应不逊于 MLP，
且训练代价低得多。</li>
</ul>
<p>评价指标为验证集<b>准确率</b>与 <b>Macro-F1</b>（类别均衡，二者接近；后者用于确认没有类别被
系统性牺牲）。所有选择只看验证集，测试集全程封存。</p>

<h2>2　数据与实验设置</h2>
<p>训练集 {ds['n_train']} 条、无标签测试集 {n_test} 条、{ds['n_classes']} 类，每类
{min(ds['class_counts'].values())}–{max(ds['class_counts'].values())} 条，基本均衡；
文本中位数长度 {ds['text_len_median']} 字符，含大量邮件头、引用与签名。按 8:2
<b>分层</b>划分为训练 {n_train} 条 / 验证 {n_val} 条（分层使各类比例一致，降低单次划分的偶然性）。
流程为五个阶段，每阶段只改一个因素：<b>①</b>划分 → <b>②</b>预处理消融 → <b>③</b>特征消融 →
<b>④</b>四模型网格搜索 → <b>⑤</b>5 折交叉验证确认 → 锁定 → 训练集 + 验证集重训 → 预测测试集。<b>防泄露</b>三要点：
TF-IDF 词表与 IDF <b>只在训练集 fit</b>，验证/测试仅 transform；测试集不参与任何统计量估计与
模型选择；清洗规则均为无参数的确定性规则，三个子集共用同一函数。</p>

<h2>3　结果与分析</h2>
<h3>3.1　预处理消融：清洗并非越多越好（H1 被否定）</h3>
{table(["方案", "清洗内容", "平均词数", "验证准确率", "Macro-F1"], pre_rows,
       left_cols=(1,), best_row=pre_best)}
<div class="callout warn"><span class="ct">反直觉发现</span>
最轻量的 C1（小写化 + 去标点数字）最优（{pre['rows'][pre_best]['accuracy']:.4f}）；
而增加去引用（C3，<span class="neg">{(pre['rows'][1]['accuracy'] - pre['rows'][3]['accuracy']):+.4f}</span>）
或去停用词 + 词长过滤（C4，{pre['rows'][4]['accuracy']:.4f}）反而下降。回看原文可解释原因：
<b>被引用的上一封帖子与当前主题高度相关</b>，引用行是重要判别线索，「Re:」后的主题词同理；
停用词在 TF-IDF 中已被 IDF 压低，删除只损失了少量高频锚点。<b>结论：预处理决策必须由验证集裁定。</b></div>

<h3>3.2　特征表示消融：IDF 是支柱，bigram 反而有害（H2 部分成立）</h3>
{table(["方案", "配置变化", "维度", "验证准确率", "Macro-F1"], feat_rows,
       left_cols=(1,), best_row=feat_best)}
<p>去掉 IDF 退化为纯词频（F0）后准确率骤降
<span class="neg">{(feat['rows'][1]['accuracy'] - feat['rows'][0]['accuracy']):+.4f}</span>，
说明<b>逆文档频率加权是该表示的支柱</b>：新闻组里 "writes" "article" 等高频套话必须被压低。
词表从 5k 扩到 32k 带来 +{(feat['rows'][3]['accuracy'] - feat['rows'][2]['accuracy']):.4f}，
说明低频实词（专有名词等）仍有判别力；而加入 bigram（F4）反而下降
{(feat['rows'][1]['accuracy'] - feat['rows'][4]['accuracy']):+.4f}——在固定 20k 维度预算下，
bigram 挤占了单词特征的空间并进一步稀疏化矩阵。</p>

<h3>3.3　模型调参：线性模型以 1/{speed_ratio:.0f} 的代价追平 MLP（H3 基本成立）</h3>
{table(["模型", "最优超参数", "验证准确率", "Macro-F1", "5 折交叉验证", "单次训练"],
       model_rows, left_cols=(1,), best_row=best_idx)}
<ul>
<li><b>NB</b>：对平滑系数 α 敏感，α=0.1 最优，继续增大显著退化（过强平滑稀释了判别性词的证据）；</li>
<li><b>LR</b>：C 从 0.1 → 100 单调上升，说明该任务上<b>弱正则化更有利</b>——高维稀疏特征本身已具约束力；</li>
<li><b>SVM</b>：线性核对 C 几乎不敏感（0.9294–0.9328），验证了「文本线性可分性好」；RBF 核更慢且无收益；</li>
<li><b>MLP</b>：固定 α=1e-3 时隐藏层 50 → 200 几乎无变化（{mlp_h50:.4f} → {mlp_h200:.4f}）；
真正收益来自<b>加大 L2 正则化</b>——α 提高到 0.1 时达 {mlp_best:.4f}，说明过拟合才是主要矛盾。</li>
</ul>
<div class="figrow full"><div><img src="{fig_uri('fig4_param_curves')}"></div></div>

<h3>3.4　最终方案、稳定性与误差分析</h3>
<p>按「验证准确率最优、0.3% 容差内取复杂度更低者」的规则，最终锁定
<b>{sel_model}（{sel_params}）</b>：在训练集 + 验证集（{final['n_final_train']:,} 条）重训后预测
测试集，输出 {final['n_test']:,} 条结果（<code>predictions.csv</code>，单列无表头，与测试集行序一一对应），
预测类别分布 {final['prediction_distribution']}，与训练分布一致，未出现类别坍缩。
最优模型验证集准确率 <b>{fin_acc:.4f}</b>、Macro-F1 <b>{fin_f1:.4f}</b>、
weighted-F1 <b>{diag['weighted_f1']:.4f}</b>；10 类中 F1 最低的是类别 {worst[0]}（{worst[1]}），
主要混淆对为 {conf_txt}。逐条检查误判样本可见，混淆集中在<b>语义相邻的主题</b>上
（如硬件讨论 vs 操作系统讨论），这类边界样本连人类读者也需上下文才能判断，属任务本身的模糊地带。</p>
<div class="figrow half">
<div><img src="{fig_uri('fig6_model_comparison')}"></div>
<div><img src="{fig_uri('fig5_confusion_matrix')}"></div></div>

<h2>4　结论与局限</h2>
<p><b>结论</b>　① 预处理强度与性能<b>并非单调关系</b>，轻量归一化最优，H1 这一直觉假设被数据否定，
说明预处理决策应交给验证集而不是经验；② IDF 加权是 TF-IDF 生效的关键，更大词表有稳定收益，
bigram 在固定维度预算下反而挤占有效特征；③ MLP 的最高验证准确率仅比 {sel_model} 高
{abs(mlp_best - sel_acc) * 100:.2f} 个百分点（{mlp_best:.4f} vs {sel_acc:.4f}），
交叉验证差异（{cv['MLP']['cv_accuracy_mean']:.4f} vs {cv_sel['cv_accuracy_mean']:.4f}）
也在一个标准差以内，而 {sel_model} 的训练代价只有 MLP 的 1/{speed_ratio:.0f}，
且 MLP 的提升主要来自加大正则化而非加大网络——据此按事先设定的规则选择 {sel_model}，支持了 H3。</p>
<p><b>局限</b>　① 保留邮件头与引用，本质上是利用了与主题强相关的元信息（发帖机构、被引帖子），
在同分布测试集上有效，但<b>跨域/真实场景</b>下未必可迁移，工程上应重新做消融；
② 测试集无标签，最终性能只能以验证集与交叉验证为代理，存在选择偏差；
③ 交叉验证波动 ±{cv_sel['cv_accuracy_std']:.4f}，表明单次划分的结论需谨慎外推；
④ 未尝试词向量 / 预训练模型表示，是后续最值得探索的方向。</p>

<h2>5　实验思考题</h2>
<p><b>Q1　为什么 SVM 和逻辑回归在该数据集上表现很好？</b>　TF-IDF 把文档映射到约 3 万维的稀疏空间，
维度数远大于样本数，不同主题的文档几乎总能被一个线性超平面分开（线性可分性好）；同时高维稀疏使核函数
计算代价急剧上升而收益有限，因此线性核 / 线性模型性价比最高。实验中线性 SVM 对 C 几乎不敏感
（0.9294–0.9328）正是这一点的直接证据；LR 与线性 SVM 的决策函数形式几乎一致（log 损失 vs hinge 损失），
因此表现接近。</p>
<p><b>Q2　MLP 能否通过加深加宽进一步提升？是否存在过拟合风险？</b>　本实验给出了直接证据：
固定 α=1e-3 时把隐藏层从 50 加宽到 200，验证准确率仅从 {mlp_h50:.4f} 变为 {mlp_h200:.4f}（不升反平）；
真正带来提升的是<b>加大 L2 正则化</b>——α 从 1e-3 提到 0.1，准确率由 {mlp_h100:.4f} 升到 {mlp_best:.4f}。
这说明瓶颈不是网络容量，而是<b>过拟合</b>：约 3 万维输入、200 个隐藏神经元意味着数百万参数，
而训练样本不足 6 千，模型足以记住训练集却无法泛化。要真正提升 MLP，更有效的是<b>降低输入维度</b>
（LSA / 词向量替代稀疏 TF-IDF）、加强正则化或早停，而非单纯加深加宽。</p>
<p><b>Q3　除 TF-IDF 外还有哪些文本表示方法？</b>　① 词袋模型（CountVectorizer）：只统计词频，
本实验 F0 已证明其弱于 TF-IDF；② 主题模型（LSA / LDA）：把文档投影到低维主题空间，可降维去噪；
③ 静态词向量（Word2Vec / GloVe + 平均池化）：引入语义相似性，缓解稀疏问题；
④ 上下文相关表示（BERT 等预训练模型）：当前效果最好，能理解语序与多义词，是本任务最值得尝试的下一步。</p>

<div class="footnote">全部代码、数据、指标（<code>results/metrics/*.json|csv</code>）、
图表（<code>results/figures/*.png</code>）与运行日志（<code>results/logs/</code>）均随仓库提交；
复现命令：<code>pip install -r requirements.txt &amp;&amp; python main.py</code>（约 40 分钟）。
另有 4 页详版 <code>report/_archive/报告_4页详版.pdf</code> 供参考。</div>

</body></html>"""
    return html


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    for exe in EDGE_CANDIDATES:
        if not Path(exe).exists():
            continue
        cmd = [
            exe, "--headless", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            return True
        print(r.stdout, r.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--name", default="", help="报告署名（姓名）")
    ap.add_argument("--sid", default="", help="报告署名（学号）")
    args = ap.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = REPORT_DIR / "实验一_文本分类_实验报告.html"
    pdf_path = REPORT_DIR / "实验一_文本分类_实验报告.pdf"

    html = build_html(args.name, args.sid)
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML 已生成: {html_path}")

    if args.html_only:
        return 0
    ok = html_to_pdf(html_path, pdf_path)
    print(("PDF 已生成: " + str(pdf_path)) if ok else "PDF 生成失败")
    if ok:
        from pypdf import PdfReader
        n = len(PdfReader(str(pdf_path)).pages)
        print(f"页数: {n}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
