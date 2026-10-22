# 数据库设计说明

> 数据库：MongoDB 8.x；库名 `questionnaire`；共 4 个集合：`users`、`surveys`、`questions`、`responses`。
> 设计目标：让「用户的每一种操作」都能用尽量少的文档读写完成，同时保证一次答卷写入的原子性。

## 1. 集合总览

```
users (1) ────< surveys (N) ────< questions (N)
                    │
                    └────────< responses (N) ── answers[] 内嵌 ──> question_id 引用 questions
```

| 集合 | 一条文档代表 | 预估规模 | 读写特征 |
| --- | --- | --- | --- |
| `users` | 一个账号 | 与用户数同阶 | 读多写少，按 username 精确查 |
| `surveys` | 一份问卷（元信息 + 状态） | 与问卷数同阶 | 按 owner 列表查、按 share_code 精确查 |
| `questions` | 一道题（含选项、约束、跳转规则） | 约为问卷数 × 题数 | 编辑期频繁单条改；填写期按问卷整批读 |
| `responses` | 一次提交（整份答卷） | 约为问卷数 × 答卷数，增长最快 | 只插入、不更新；统计时按问卷聚合 |

## 2. 各集合结构

### 2.1 users

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `_id` | ObjectId | 主键 |
| `username` | string(3~32) | 登录名，唯一 |
| `password_hash` | string | bcrypt 哈希，绝不返回给客户端 |
| `created_at` | Date | 注册时间 |

索引：`{username: 1}` **唯一**。
理由：登录和注册都要按用户名精确定位；唯一索引让「并发注册同名」由数据库兜底，而不是靠应用层先查后插（有竞态）。

> 用户文档里**不存**问卷 id 数组。原因：问卷数量无上限，数组会无限增长并触发文档重写；归属关系用 `surveys.owner_id` 单向引用表达，查「我的问卷」时走 `{owner_id, created_at}` 复合索引即可。

### 2.2 surveys

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `owner_id` | ObjectId → users | 创建者 |
| `title` / `description` | string | 标题、说明 |
| `allow_anonymous` | bool | 是否允许未登录填写 |
| `allow_multiple` | bool | 是否允许同一用户重复填写 |
| `status` | enum `draft`/`published`/`closed` | 生命周期，单字段状态机 |
| `deadline` | Date \| null | 截止时间，与 status 解耦 |
| `share_code` | string(8) | 对外短码，用于填写链接 |
| `question_count` | number | 题数计数（受控冗余，见 §4.2） |
| `created_at` / `updated_at` / `published_at` / `closed_at` | Date | 时间戳 |

索引：

| 索引 | 用途 |
| --- | --- |
| `{owner_id: 1, created_at: -1}` | 「我的问卷」列表：先等值过滤再按时间倒序，一次索引扫描即出结果 |
| `{share_code: 1}` 唯一 | 填写入口按短码定位；唯一约束保证链接不撞车 |

为什么用 `status` 一个字段而不是 `is_published` + `is_closed` 两个布尔：两个布尔存在 4 种组合，其中「既发布又关闭」是非法状态，需要额外代码维持一致；单字段枚举从数据层就排除了非法状态。

为什么 `deadline` 不并入 `status`：过期是时间的函数，不是被写入的状态。若把「过期」写成 closed，那么延长截止时间就必须重新发布一次，且历史状态被时间污染。现在判定「能否填写」只要看 `status === 'published' && (!deadline || now < deadline)`。

### 2.3 questions

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `survey_id` | ObjectId → surveys | 所属问卷 |
| `order` | number | 题号，1 起，问卷内唯一 |
| `type` | enum `single`/`multiple`/`dropdown`/`rating`/`text`/`number`/`date` | 题型；rating 的 1~5 星选项由服务端自动生成 |
| `title` | string | 题干 |
| `required` | bool | 是否必答 |
| `options[]` | `{key, label}` | 单选/多选的选项，`key` 是稳定标识（A/B/C…） |
| `constraints` | object | 按题型分别使用（见下） |
| `jump_rules[]` | `{when, to, target_question_id, priority}` | 跳转规则 |
| `created_at` / `updated_at` | Date | 时间戳 |

`constraints` 的字段按题型分工，避免为所有题型准备一堆无意义的可空字段：

| 题型 | 使用字段 |
| --- | --- |
| single | 无（只需选项） |
| multiple | `min_choice`、`max_choice` |
| text | `min_length`、`max_length`（按 Unicode 码点计） |
| number | `min`、`max`、`integer` |

`jump_rules[].when.op` 支持 6 种条件：`option_selected`、`number_eq`、`number_gte`、`number_lt`、`number_between`、`text_contains`；`to` 为 `question` 或 `end`。

索引：

| 索引 | 用途 |
| --- | --- |
| `{survey_id: 1, order: 1}` **唯一** | 填写时按问卷取全部题目并按题号排序；唯一约束保证同一问卷不会出现两个「第 3 题」 |
| `{jump_rules.target_question_id: 1}` | 删除题目 / 调整顺序时反查「哪些规则指向它」，用于清理死规则 |

单选题的选项为什么用 `{key,label}` 而不是纯字符串数组：答案里存的是 `key`。如果只存展示文案，改一次文案就会让历史答卷对不上号；用稳定 key，改文案不影响数据。

### 2.4 responses

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `survey_id` | ObjectId → surveys | 所属问卷 |
| `respondent_id` | ObjectId \| null | 登录用户；匿名为 null |
| `anonymous` | bool | 是否匿名提交（冗余标记，方便直接按匿名筛选） |
| `answers[]` | `{question_id, question_order, option_keys[], text, number}` | 内嵌的整份答卷 |
| `path[]` | ObjectId[] | 服务端推导出的实际作答路径（题目 id 顺序） |
| `submitted_at` | Date | 提交时间 |
| `schema_version` | number | 文档结构版本，当前为 1 |
| `meta` | `{user_agent, duration_ms}` | 辅助信息 |

索引：

| 索引 | 用途 |
| --- | --- |
| `{survey_id: 1, submitted_at: -1}` | 统计与答卷明细：按问卷取、按时间倒序 |
| `{survey_id: 1, respondent_id: 1}` | 判重：这个用户在本问卷是否已提交 |
| `{survey_id: 1, 'answers.question_id': 1}` | 多键索引，支持「某道题的全部答案」单题统计 |

## 3. 引用与内嵌的取舍

这是 MongoDB 设计里最关键的一次决策，本项目的划分依据是「**一起读、一起写、生命周期相同**」。

| 关系 | 选择 | 理由 |
| --- | --- | --- |
| 用户 → 问卷 | 引用（`surveys.owner_id`） | 问卷数量无上限，内嵌会撑爆用户文档；问卷会被独立查询（列表、按短码） |
| 问卷 → 题目 | **拆分集合 + 引用**（`questions.survey_id`） | 见下方专门说明 |
| 问卷 → 答卷 | 拆分集合 | 答卷数量随时间无上限增长，且只追加不修改；内嵌会让问卷文档不断变大、频繁搬迁 |
| 答卷 → 答案 | **内嵌**（`responses.answers[]`） | 一次提交天然是一个一致性单元；答案永远随答卷一起读写，没有独立查询需求 |

### 3.1 为什么题目要拆成独立集合（而不是内嵌在 survey 里）

内嵌看起来更省事（一次查询拿全），但本项目的编辑场景决定了不能这么做：

1. **写放大与并发覆盖**。编辑期最频繁的操作是「改一道题的标题」「给某题加一条跳转规则」。内嵌结构下每次都要读出整份问卷、改数组里的一个元素、再整体写回；两个浏览器标签同时编辑不同题时，后写的一方会用自己读到的旧数组覆盖对方的修改（典型的 lost update）。拆成独立文档后，每次只更新一道题的文档，互不影响。
2. **题型异构**。数字题只需要 `min/max/integer`，多选题只需要 `min_choice/max_choice`。内嵌成一个大数组时，这些字段会混在同一套 schema 里，校验逻辑被迫对「不可能出现的字段组合」做大量判空。
3. **题号唯一性可以由数据库保证**。独立集合上可以建 `{survey_id, order}` 唯一索引；数组内的元素顺序只能靠应用层维护。
4. **第二阶段的可演进性**。新需求往往就是「新增一种题型」「给题目加新属性」。独立文档只需多几个字段，老数据照常读；内嵌数组则要考虑整个 survey 文档的兼容。

代价是「读整份问卷」要两条查询（survey + questions）。这个代价很小：通常是 1 次主键查询 + 1 次 `{survey_id}` 索引查询，且两道查询可以并行发出。

### 3.2 为什么答案要内嵌在 response 里

1. **原子性**。一次提交是一个业务事务。内嵌后它是**单文档写入**，MongoDB 保证单文档原子性，绝不会出现「第 1、2 题存进去了、第 3 题丢了」的中间态。如果拆成 `answers` 集合，就必须引入多文档事务。
2. **读模式匹配**。统计时要拿到「整份答卷」的上下文（例如多选题每个选项的选择次数、每份答卷的答题路径）；内嵌后一条聚合管道即可完成，不需要 `$lookup`。
3. **体积可控**。单份问卷建议 ≤ 200 题，文本题有 `max_length` 上限，单份答卷文档实际在几 KB 量级，远低于 16MB 上限。

### 3.3 唯一的冗余字段与它的理由

`responses.answers[].question_order` 是刻意冗余的：

- 题目顺序以后可能被调整（草稿期排序），而历史答卷需要保留「当时是第几题」。
- 它是**提交时写入的快照**，之后不再更新，不会产生「缓存与源数据不一致」的维护成本。
- 它让统计与答卷明细不必再关联 `questions` 就能按题号展示。

`surveys.question_count` 是第二个冗余，用于列表页展示题数，避免列表页对每份问卷再查一次 `questions`。它只由题目增删的写路径维护（同一处代码负责），不参与任何业务判定。

## 4. 为什么不用关系型数据库结构

如果把同样的需求建成关系模型，至少需要下面这些表和列：

| 关系模型需要 | 本项目对应 | 关系模型的痛点 |
| --- | --- | --- |
| `surveys` + `questions` + `question_options` | `surveys` + `questions`（选项内嵌） | 选项被拆表，读一道题要 join 两张表 |
| `questions` 需要 `min_choice`、`max_choice`、`min_length`、`max_length`、`min`、`max`、`is_integer` 七列 | `constraints` 子文档 | 任一题型只用其中 1~3 列，其余全为 NULL，表结构被「最宽题型」绑架 |
| `jump_rules` + `jump_conditions` + `jump_targets` | `questions.jump_rules[]` | 一条「选 A 跳第 5 题」在关系模型里要 3 张表 join，编辑一条规则要动多表事务 |
| `responses` + `answers_single` + `answers_multiple` + `answers_text` + `answers_number`（或 EAV） | `responses.answers[]` | 要么按题型分 4 张答案表再 UNION，要么退回 EAV（`question_id, key, value`），后者丢失类型且查询极难写 |
| 每次需求变更 → `ALTER TABLE` + 数据回填 | 新增字段即可 | 课程第二阶段的「需求变更」正是关系模型的迁移噩梦 |

结论：本系统的数据天然是**层次化、异构、随需求演进**的。用关系模型会得到一张宽表加一堆 NULL，或者一组需要大量 JOIN 的窄表；而 MongoDB 的文档模型可以直接把「一份问卷」「一份答卷」当作一个整体来存取。

## 5. 为什么适合 MongoDB

1. **读写模式匹配**：写路径是「一次提交写一份完整答卷」，读路径是「整份问卷 / 整份答卷 / 按题聚合」，都是文档模型的强项。
2. **异构数据自然表达**：七种题型共用一套外层结构，各自的特有约束放在子文档里，不需要宽表；新增题型（下拉、评分、日期）只是扩枚举 + 引擎各加一个分支，存量问卷零迁移。
3. **聚合管道直接出统计**：`$unwind answers` → `$group by question_id` 一条管道即可完成「每题被回答多少次、每个选项被选多少次」，无需应用层把上百万条答案拉回内存。
4. **无模式迁移负担**：第二阶段加字段、加题型时，老文档照常可读，配合 `schema_version` 做读时兼容。
5. **水平扩展路径清晰**：答卷量增长后可按 `survey_id` 做分片（该字段在每个集合中都存在，且是查询必带条件）。

## 6. 典型查询与索引命中

| 场景 | 查询 | 命中索引 |
| --- | --- | --- |
| 登录 | `users.findOne({username})` | `{username:1}` 唯一 |
| 我的问卷列表 | `surveys.find({owner_id}).sort({created_at:-1}).skip/limit` | `{owner_id:1, created_at:-1}` |
| 打开填写页 | `surveys.findOne({share_code})` | `{share_code:1}` 唯一 |
| 读取题目 | `questions.find({survey_id}).sort({order:1})` | `{survey_id:1, order:1}` |
| 判重 | `responses.countDocuments({survey_id, respondent_id})` | `{survey_id:1, respondent_id:1}` |
| 整卷统计 | `responses.aggregate([{$match:{survey_id}},{$unwind:'$answers'},{$group:...}])` | `{survey_id:1, submitted_at:-1}` 前缀 |
| 单题统计 | `responses.aggregate([{$match:{survey_id,'answers.question_id':qid}},{$unwind},{$match},{$group}])` | `{survey_id:1,'answers.question_id':1}` |

## 7. 为第二阶段预留的设计

| 预留 | 说明 |
| --- | --- |
| `responses.schema_version` | 新需求若改变答卷结构，新答卷写 v2，读取端按版本分支解释，不需要全量迁移老数据 |
| 题目独立集合 | 新增题型只需新文档多几个字段，`type` 枚举扩展即可，不影响已有题目 |
| `jump_rules` 是数据不是代码 | 新增跳转条件类型只需在引擎里加一个 `op` 分支，不用改数据结构 |
| `answers[]` 里存 `question_id` 而非题号 | 题目顺序变化不影响历史答卷的对应关系 |

## 8. 被否决的方案（记录取舍过程）

| 方案 | 否决原因 |
| --- | --- |
| 全部塞进一个 `surveys` 集合（题目、答卷都内嵌） | 问卷文档会随答卷数无限增长，最终触及 16MB 上限，且每次提交都要重写整个文档 |
| 每道题一个 `answers` 集合文档（EAV 风格） | 统计要跨集合 join，写入不再原子，读写都变复杂；本项目没有「按单个答案查询」的独立需求 |
| 用 `_id` 作为填写链接 | 暴露数据库主键，且不便以后换短链/自定义别名，因此引入 `share_code` |
| 把「是否过期」写成 `status=closed` | 时间是函数不是状态，写死会导致延长截止时间必须重新发布，并污染历史状态 |
