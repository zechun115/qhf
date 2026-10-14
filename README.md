# 当代人工智能实验一：文本分类

10 类新闻组文本（20 Newsgroups 风格）分类实验。从数据划分、文本预处理、
TF-IDF 特征工程，到朴素贝叶斯 / 逻辑回归 / 支持向量机 / 多层感知机四种
经典分类器的超参数调优与最终预测，形成了一条完整、可复现的实验链路。

> 完整实验报告见 `report/实验一_文本分类_实验报告.pdf`。

---

## 一、环境准备

```bash
# 建议使用 conda 或 venv 创建独立环境（Python >= 3.10）
python -m venv .venv
source .venv/Scripts/activate      # Windows
# source .venv/bin/activate        # Linux / macOS

pip install -r requirements.txt
```

依赖：`numpy`、`pandas`、`scikit-learn`、`matplotlib`、`nltk`（仅用于英文词干化，
未安装时程序会自动跳过词干化步骤，不影响其他功能）。

## 二、目录结构

```
qhf/
├── main.py                       
├── requirements.txt
├── predictions.csv               
├── data/
│   ├── train_data.csv            # 7368 条带标签训练数据
│   ├── test_data_unlabeled.csv   # 2457 条待预测数据
│   └── draft_main.py             # 助教提供的加载示例（保留备查）
├── src/
│   ├── utils.py                  # 随机种子、日志、结果落盘
│   ├── data.py                   # 数据加载与分层划分
│   ├── preprocess.py             # 文本清洗（每一步均可开关，支持消融）
│   ├── features.py               # TF-IDF 特征工程（只在训练集上 fit）
│   ├── models.py                 # 模型工厂与超参数候选集合
│   ├── evaluate.py               # 评估指标、混淆矩阵、误差分析
│   ├── plotting.py               # 实验图表
│   └── experiment.py             # 五个阶段的实验编排
├── results/
│   ├── predictions.csv           # 与根目录一致
│   ├── figures/                  # 全部图表（PNG）
│   ├── metrics/                  # 全部指标（JSON / CSV）与运行日志
│   └── logs/
└── report/                       # 实验报告（PDF / HTML 源文件）
```

## 三、运行方式

```bash
# 跑完整实验（默认 seed=42，验证集 20%）
python main.py

# 只跑某个阶段
python main.py --stage eda          # 数据探索
python main.py --stage preprocess   # 预处理消融
python main.py --stage features     # 特征表示消融
python main.py --stage tune         # 模型调参 + 交叉验证 + 最终预测
python main.py --stage final        # 只做最终预测

# 自定义随机种子与验证集比例
python main.py --val-size 0.2 --seed 42
```

运行结束后：

- 提交文件：`predictions.csv`（单列、无表头，共 2457 行，行序与
  `test_data_unlabeled.csv` 一一对应）；
- 指标文件：`results/metrics/*.json`、`*.csv`；
- 图表：`results/figures/*.png`；
- 运行日志：`results/logs/run-<时间戳>.log`。

## 四、实验设计

实验遵循「先划分数据、只改变需要研究的因素、先基线后改进」的原则，
共分五个阶段：

| 阶段 | 内容 | 控制变量 |
|---|---|---|
| 0 | 数据探索 + 分层划分（80% / 20%） | — |
| 1 | 预处理消融（6 种清洗方案） | 固定 LR(C=10) + 基准 TF-IDF |
| 2 | 特征表示消融（6 种 TF-IDF 配置） | 固定最优清洗 + LR(C=10) |
| 3 | 四模型超参数网格搜索 | 固定最优清洗与特征，只在验证集上选择 |
| 4 | 5 折分层交叉验证 | 确认最优配置的稳定性 |
| 5 | 锁定方案 → 训练集+验证集重训 → 预测测试集 | — |

**防数据泄露**：TF-IDF 的词表与 IDF 只在训练集上 `fit`；测试集全程只参与
`transform`，不参与任何统计量估计与模型选择。

**方案选择规则**：先取验证集准确率最优者；在 0.3% 容差内，优先选择结构
更简单的模型（复杂度排序 NB < LR < SVM < MLP），对应评分标准中
「综合考虑验证集性能与模型复杂度」。

## 五、可复现性

- 所有随机源（数据划分、模型初始化、MLP 权重）统一使用 `--seed`（默认 42）
  固定，见 `src/utils.py::set_seed`；
- 依赖版本记录在 `requirements.txt`；
- 全部实验配置、指标与图表落盘到 `results/`，日志保留完整运行过程；
- 代码中不出现绝对路径，所有路径基于项目根目录推导。

## 六、主要实验结果

（运行 `python main.py` 后自动生成，详见 `results/metrics/`）

**数据**：训练 7,368 / 测试 2,457 / 10 类；分层 8:2 划分（seed=42）。

**预处理消融**（LR C=10 + TF-IDF 20k）

| 方案 | 内容 | 验证准确率 |
|---|---|---|
| C0 | 不清洗 | 0.9301 |
| **C1** | **基础归一化（最优）** | **0.9342** |
| C2 | +去邮件头 | 0.9335 |
| C3 | +去引用 | 0.9104 |
| C4 | +去停用词/词长过滤 | 0.9159 |
| C5 | +词干化 | 0.9138 |

> 反直觉结论：清洗越激进性能越差——引用行与邮件头本身携带主题线索。

**特征表示消融**：去掉 IDF 掉 3.8 个百分点；词表 5k → 32k（F3）最优 0.9369；
加入 bigram 反而下降到 0.9213。

**模型对比**（最优配置，C1 + F3 特征）

| 模型 | 最优超参数 | 验证准确率 | 5 折交叉验证 | 单次训练 |
|---|---|---|---|---|
| NB | alpha=0.1 | 0.9254 | 0.9265 ± 0.0061 | 0.0s |
| **LR** | **C=100** | **0.9383** | **0.9318 ± 0.0050** | **5.6s** |
| SVM | linear, C=100 | 0.9328 | 0.9299 ± 0.0056 | 67.6s |
| MLP | (100,), alpha=0.1 | 0.9389 | 0.9350 ± 0.0040 | 192.2s |

按「准确率最优、0.3% 容差内取复杂度更低者」的规则，最终锁定
**逻辑回归（C=100）**：验证准确率 0.9383、Macro-F1 0.9385，
在训练集 + 验证集（7,368 条）上重训后对测试集输出 2,457 条预测
（`predictions.csv`）。

