# 关键逻辑说明

本文说明四个「必须讲清楚」的实现点：**跳转**、**校验**、**提交时的路径重算**、**题目排序与死规则清理**，以及统计聚合的做法。

---

## 1. 跳转设计

### 1.1 规则存在数据里，引擎只解释规则

需求明确要求「跳转不能写死在程序里」。因此跳转被抽象成 JSON，存在 `questions.jump_rules` 里：

```json
{
  "when": { "op": "option_selected", "option_key": "A" },
  "to": "question",
  "target_question_id": "66f1a2...",
  "priority": 1
}
```

- `when.op` 是条件类型，共 6 种：

| op | 适用题型 | 含义 | 参数 |
| --- | --- | --- | --- |
| `option_selected` | single / multiple | 答案中包含了该选项 | `option_key` |
| `number_eq` | number | 数值等于 | `value` |
| `number_gte` | number | 数值 ≥ | `value` |
| `number_lt` | number | 数值 < | `value` |
| `number_between` | number | 数值落在闭区间内 | `value`、`value2` |
| `text_contains` | text | 文本包含关键字 | `text` |

- `to` 是动作：`question` 跳到指定题目，`end` 直接结束问卷
- `priority` 决定同一题多条规则的判定顺序，数字小的先判，**命中即停**

引擎（`src/core/jump.js`）本身只有一个 `ruleMatches` 函数加一个 `computePath` 循环，完全不认识「身份」「年龄」这些具体业务词。

### 1.2 路径计算流程

```
输入：按题号升序的题目列表、用户已填的答案（题目 id → 答案）
cursor = 0
while cursor < 题目数:
    取第 cursor 题 → 加入 path
    取该题的答案
    把该题规则按 priority 升序排序
    找到第一条 ruleMatches 为真的规则
    若命中:
        若 to == 'end'  → 结束，标记 endedEarly
        若 to == 'question' 且目标题号 > 当前题号 → cursor = 目标题号（跳过去）
        否则（目标不存在 / 目标在前面）→ 视为非法规则，忽略
    否则 cursor = cursor + 1
```

### 1.3 三道防死循环 / 防错机制

| 机制 | 位置 | 作用 |
| --- | --- | --- |
| 只允许向后跳 | `computePath` 内比较题号 | 规则即使被写坏也只会跳向后面，不会 A→B→A |
| 步数上限 | `guard = 题目数 × 2 + 5` | 兜底，任何异常都不会让请求卡死 |
| 写入时就拒绝向前跳 | `questionRules.validateJumpRules` | 配置规则时目标题号必须大于当前题号，从源头避免 |

### 1.4 一个具体例子

问卷：

| 题号 | 题型 | 题干 | 规则 |
| --- | --- | --- | --- |
| 1 | 单选 | 你的身份（A 学生 / B 教师） | 选 A → 跳到第 4 题 |
| 2 | 文本 | 你对课程的建议 | — |
| 3 | 数字 | 你每周投入的小时数 | — |
| 4 | 多选 | 你希望增加哪些内容 | — |
| 5 | 数字 | 给课程打分 | — |

- 学生（第 1 题选 A）→ 路径 `1 → 4 → 5`
- 教师（第 1 题选 B）→ 路径 `1 → 2 → 3 → 4 → 5`

这两条路径都在 `tests/api.fill.test.js` 的 T10 / T10b 中被断言，前端 `fill.html` 与服务端使用的是同一个 `computePath`。

---

## 2. 校验设计

### 2.1 校验只发生在「路径上的题目」

这是跳转与校验的耦合点，也是最容易做错的地方：**被跳过的题目不应该被要求必答**。

所以提交时先算路径，再只对路径上的题目做校验。被跳过的题目即使前端传了答案，也不参与校验、不写入答卷（会计入 `ignored_answers`）。

### 2.2 规则表

| 题型 | 校验项 | 失败提示示例 |
| --- | --- | --- |
| 所有 | `required=true` 且未作答 | 本题为必答题 |
| single / dropdown / rating | 必须且只能选 1 项 | 单选题必须且只能选择 1 个选项 |
| single / multiple / dropdown / rating | 选项必须在本题选项内 | 选项 Z 不存在于本题 |
| multiple | `min_choice` / `max_choice` | 多选题至少选择 2 项，当前 1 项 |
| text | `min_length` / `max_length`（按 Unicode 码点） | 文本长度不能少于 2 个字符，当前 1 个 |
| number | 必须是合法数字 | 请填写合法的数字 |
| number | `integer=true` 时必须是整数 | 本题要求填写整数 |
| number | `min` / `max` | 数值不能大于 120，当前 200 |
| date | `YYYY-MM-DD` 且必须真实存在 | 请填写合法的日期（格式：YYYY-MM-DD） |

> 新增题型（dropdown / rating / date）只在两处各加了一个分支：`questionRules.js` 的题型枚举与结构校验、`validation.js` 的答案规范化与校验——这正是「题型异构数据放子文档 + 引擎只解释规则」带来的扩展方式，存量问卷与引擎其他部分零改动。评分题的 1~5 星选项由服务端自动生成，保证统计与跳转的口径一致；日期校验在正则之外还用 `new Date()` 反解验证，拒绝 `2026-02-30` 这类格式正确但不存在的日期。

### 2.3 文本长度为什么按「码点」而不是 `length`

JavaScript 的 `'😀'.length === 2`，直接用 `length` 会让用户输入 1 个 emoji 就被算作 2 个字，导致「最多 1 字」的题目无法提交。`validation.js` 里统一用 `Array.from(str).length`，按 Unicode 码点计数。这一行为在 T16-1 中有专门的用例。

### 2.4 同一份引擎，前后端共用

`src/core/validation.js` 与 `src/core/jump.js` 使用 UMD 包装：

```js
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.QBValidation = factory();
})(typeof self !== 'undefined' ? self : this, function () { /* ... */ });
```

- 服务端：`require('../core/validation')`
- 浏览器：`<script src="/core/validation.js">` 后使用 `window.QBValidation`

好处是「前端提示」和「后端判定」永远一致：不会出现前端放行、后端 422 的割裂体验，也不会出现两套规则各写一遍、改一处忘另一处的问题。

这也暴露过一个真实的问题（见 AI 使用日志）：引擎最初只认 `_id`，而浏览器拿到的是 `id`，导致前端跳转失效。修复方式是在引擎里加一个 `qid(q) { return String(q._id || q.id); }`，让同一份代码兼容两种主键字段。

---

## 3. 提交时的「路径重算」

前端 `fill.html` 会在每次答题后本地计算一次路径，用于即时跳转；但提交时它只发送**答案**，不发送路径。

服务端收到后：

```
1. 按短码取问卷 → 校验状态 / 截止时间 / 匿名策略
2. 取该问卷全部题目（按题号）
3. 过滤出属于本问卷的答案，构造 question_id → answer
4. 用同一份 computePath 重新计算路径          ← 权威路径
5. 只校验路径上的题目
6. 有错误 → 422，返回逐题原因
7. 判重（allow_multiple=false 且同一用户已提交 → 409）
8. 写入 responses：answers（仅路径上的题，按路径顺序）+ path（题目 id 序列）+ schema_version
```

这样做解决了三个问题：

1. **绕过必答题**：构造请求只提交后面的题？路径里仍然包含前面必答题，校验照样失败。
2. **前后端不一致**：前端被改过、缓存过期、或者用户禁用 JS，最终以服务端路径为准。
3. **可追溯**：`path` 落库，事后可以回放「这个人当时实际走了哪几题」，统计时也能解释为什么某题作答率低。

---

## 4. 题目排序与死规则清理

### 4.1 唯一索引导致的批量更新冲突

`questions` 上有 `{survey_id: 1, order: 1}` 唯一索引。调整顺序时如果直接批量写最终值，会撞车：

```
原顺序：A(1) B(2)      目标顺序：B(1) A(2)
先改 B→1：与 A 当前的 1 冲突 ✗
先改 A→2：与 B 当前的 2 冲突 ✗
```

解决方案是**两阶段更新**：先把该问卷所有题目的 `order` 整体抬到一个安全区间（`+ 题目数 + 1000`），此时不会与任何现存值冲突；再一次性写入最终值 1..n。

实现见 `src/routes/questions.js` 的 `applyOrders()`。这个 bug 是在 T30b 用例跑出来之后才发现的，属于「测试先于手工验证发现问题」的典型案例。

### 4.2 删除题目后的连带处理

删除一道题会破坏两类东西：

| 破坏 | 处理 |
| --- | --- |
| 题号出现空洞（1、2、4） | `renumber()` 重排为 1..n |
| 有其他题目的规则指向它 | `cleanupInvalidRules()` 删除这些规则 |
| 重排后原来的「向后跳」变成「向前跳」 | 同一函数中一并清理（只保留 `to='end'` 与目标题号仍大于当前题号的规则） |

`cleanupInvalidRules()` 在「删除题目」和「调整顺序」两个入口都会被调用，保证库里不残留死规则。

---

## 5. 统计

### 5.1 一条聚合管道取回所有题的原始数据

```js
Response.aggregate([
  { $match: { survey_id } },
  { $unwind: '$answers' },
  { $group: {
      _id: '$answers.question_id',
      answered:     { $sum: 1 },
      option_sets:  { $push: '$answers.option_keys' },
      texts:        { $push: '$answers.text' },
      numbers:      { $push: '$answers.number' }
  }}
])
```

- `$match` 先用 `{survey_id, submitted_at}` 索引把范围收到一份问卷
- `$unwind` 把内嵌的答案数组展开成「一条答案一行」
- `$group` 按题目聚合，一次拿到全部题目所需数据

之所以不在应用层把所有答卷拉回来循环：答卷量增长后，网络传输和 JS 内存都会成为瓶颈；聚合在数据库侧完成只返回「每题一组统计量」。

### 5.2 各题型的二次计算

`$group` 只负责取原始数据，具体统计在各题型的处理函数里完成：

| 题型 | 计算 | 说明 |
| --- | --- | --- |
| single | 遍历每次作答的 `option_keys[0]` 累加 | `percent` 的分母是「答过该题的人数」，不是总答卷数 |
| multiple | 遍历每次作答的整个 `option_keys` 数组累加 | 一个人选 3 项就算 3 次，反映的是「偏好热度」 |
| text | 收集非空文本，计算条数与平均码点长度 | 只返回前 100 条，用 `texts_truncated` 标记是否截断 |
| number | 过滤有效数字，算 count / avg / min / max | 平均值保留两位小数 |

### 5.3 为什么分母是「答过该题的人数」

因为有跳转，不同题目的实际作答人数不同。若统一用总答卷数做分母，会出现「选项占比之和远小于 100%」的误导性结果。因此在返回里同时给出 `answered`（该题作答人数）与 `response_rate`（相对总答卷的作答率），让使用者能区分「这题没人选」和「这题根本没人看到」。

---

## 6. 权限与状态

| 检查点 | 规则 |
| --- | --- |
| 问卷归属 | `String(survey.owner_id) === req.user.id`，否则 403 |
| 题目归属 | 先查题目再查其问卷的 owner，避免「有题目 id 就能改」 |
| 草稿才可编辑 | `status !== 'draft'` 时任何题目写操作返回 409 |
| 发布前置条件 | `question_count >= 1` |
| 填写前置条件 | `status === 'published'` 且未过 `deadline` |
| 匿名策略 | `allow_anonymous === false` 时提交必须登录（401） |
| 重复填写 | `allow_multiple === false` 时同一 `respondent_id` 第二次提交 409 |
| 删除问卷 | 仅草稿，且无答卷 |

状态机：

```
draft ──publish()──> published ──close()──> closed
  │                                           
  └──delete()──> (删除，仅当无答卷)
```

`published` 之后不允许回到 `draft`，也不允许重新打开 `closed` 的问卷。这是刻意保留的「单向门」：问卷一旦被人填过，题目结构就不该再变，否则历史答卷无法解释。第二阶段如果需要「改题目」，正确的做法是新建一份并保留旧数据（这正是本项目为第二阶段预留的演进空间）。
