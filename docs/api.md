# API 说明

- 基础路径：`/api`
- 请求与响应均为 `application/json; charset=utf-8`
- 除注册、登录、填写页数据、提交答卷外，其余接口都需要在请求头带 `Authorization: Bearer <token>`

## 0. 统一约定

### 0.1 错误响应格式

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "该问卷不允许同一用户重复填写",
    "details": null
  }
}
```

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | 参数缺失或格式不正确 |
| 401 | `UNAUTHORIZED` | 未登录 / token 失效 / 密码错误 |
| 403 | `FORBIDDEN` | 已登录但访问了别人的资源 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` | 与当前状态冲突（已发布、已关闭、已截止、重复填写） |
| 422 | `VALIDATION_FAILED` | 答卷未通过校验，`details.errors` 给出逐题原因 |
| 500 | `INTERNAL_ERROR` | 未预期的服务端异常 |

### 0.2 通用枚举

- 题型 `type`：`single` 单选、`multiple` 多选、`text` 文本填空、`number` 数字填空
- 问卷状态 `status`：`draft` 草稿、`published` 已发布、`closed` 已关闭
- 跳转条件 `when.op`：`option_selected`、`number_eq`、`number_gte`、`number_lt`、`number_between`、`text_contains`

---

## 1. 账号

### 1.1 注册

`POST /api/auth/register`

```json
{ "username": "alice", "password": "secret123" }
```

- 用户名 3~32 字符，密码 6~64 字符
- 成功 `201`：

```json
{ "token": "eyJhbGci...", "user": { "id": "66f...", "username": "alice", "created_at": "2026-10-19T11:00:00.000Z" } }
```

| 失败 | 说明 |
| --- | --- |
| 400 | 用户名或密码长度不合法 |
| 409 | 用户名已存在 |

### 1.2 登录

`POST /api/auth/login`，请求体同上。

- 成功 `200`，返回结构同注册
- 失败 `401`：用户名不存在与密码错误返回**同一句提示**，避免泄露用户名是否存在

### 1.3 当前用户

`GET /api/auth/me` → `{ "user": { ... } }`

---

## 2. 问卷管理

### 2.1 创建问卷

`POST /api/surveys`

```json
{
  "title": "课程反馈问卷",
  "description": "请如实填写",
  "allow_anonymous": false,
  "allow_multiple": true,
  "submit_message": "感谢填写！结果将用于改进教学。",
  "deadline": "2026-12-31T23:59:00.000Z"
}
```

- `201`：

```json
{
  "survey": {
    "id": "66f...",
    "title": "课程反馈问卷",
    "status": "draft",
    "share_code": "k3m9x2ab",
    "share_url": "http://127.0.0.1:3000/fill.html?code=k3m9x2ab",
    "question_count": 0
  }
}
```

### 2.2 我的问卷列表

`GET /api/surveys?page=1&size=20&status=published`

```json
{
  "total": 3, "page": 1, "size": 20,
  "items": [ { "...": "同 2.1，另含 response_count 答卷数" } ]
}
```

### 2.3 问卷详情（含题目）

`GET /api/surveys/:id` → `{ "survey": {...}, "questions": [ {...} ] }`

题目对象：

```json
{
  "id": "66f...",
  "order": 1,
  "type": "single",
  "title": "你的身份",
  "required": true,
  "options": [{ "key": "A", "label": "学生" }, { "key": "B", "label": "教师" }],
  "constraints": { "min_choice": null, "max_choice": null, "min_length": null, "max_length": null, "min": null, "max": null, "integer": null },
  "jump_rules": [
    { "when": { "op": "option_selected", "option_key": "A" }, "to": "question", "target_question_id": "66f...", "priority": 1 }
  ]
}
```

### 2.4 修改问卷

`PATCH /api/surveys/:id`

| 状态 | 允许修改 |
| --- | --- |
| draft | `title`、`description`、`allow_anonymous`、`allow_multiple`、`deadline`、`submit_message` |
| published | `deadline`、`submit_message`（提示语不影响答卷结构，对标腾讯文档收集表） |
| closed | 不允许（409） |

### 2.5 发布 / 关闭

- `POST /api/surveys/:id/publish`：至少 1 道题，`draft → published`
- `POST /api/surveys/:id/close`：`published → closed`，链接立即失效

### 2.6 删除问卷

`DELETE /api/surveys/:id`：仅草稿且无答卷，级联删除题目。

### 2.7 复制问卷（生成副本）

`POST /api/surveys/:id/duplicate` → `201`

复制问卷元信息（标题加「（副本）」后缀）与全部题目，副本为 **draft** 状态、不继承截止时间。跳转规则一并复制，且 `target_question_id` 按新旧题目 id 映射**重写**，保证规则指向副本内的题目：

```json
{ "survey": { "id": "新 id", "title": "原问卷（副本）", "status": "draft", "...": "..." }, "copied_questions": 5 }
```

---

## 3. 题目管理（仅草稿状态）

### 3.1 添加题目

`POST /api/surveys/:id/questions`

单选 / 多选：

```json
{
  "type": "multiple",
  "title": "你喜欢的水果",
  "required": true,
  "options": [{ "key": "A", "label": "苹果" }, { "key": "B", "label": "香蕉" }],
  "constraints": { "min_choice": 2, "max_choice": 3 }
}
```

文本 / 数字 / 日期：

```json
{ "type": "number", "title": "年龄", "required": true, "constraints": { "min": 0, "max": 120, "integer": true } }
{ "type": "date", "title": "你的出生日期", "required": true }
```

下拉选择：

```json
{ "type": "dropdown", "title": "你的年级", "options": [{ "key": "A", "label": "大一" }, { "key": "B", "label": "大二" }] }
```

评分题：

```json
{ "type": "rating", "title": "你对课程的满意度" }
```

- `type` 取值：`single` / `multiple` / `dropdown` / `rating` / `text` / `number` / `date`
- **rating（评分题）**：选项固定为 `1 星 ~ 5 星`，由服务端自动生成，不接受自定义 `options`；提交时答案为 `{ "option_keys": ["4"] }`
- **date（日期）**：答案为 `{ "date": "2026-10-21" }`，服务端校验 `YYYY-MM-DD` 格式并拒绝不存在的日期（如 `2026-02-30`）
- `options` 可省略 `key`，服务端按 A/B/C… 自动编号
- 题号由服务端分配为「当前最大题号 + 1」

### 3.2 修改题目

`PATCH /api/questions/:id`，字段均可选：`type`、`title`、`required`、`options`、`constraints`、`jump_rules`

> `jump_rules` 是**整体替换**语义：传什么就存什么，因此编辑页添加/删除一条规则时，会把完整数组回传。

### 3.3 删除题目

`DELETE /api/questions/:id`

副作用：
1. 剩余题目按原顺序重排为 1..n
2. 指向该题的跳转规则被清理
3. 因重排而变成「向前跳」的规则同样被清理

### 3.4 调整顺序

`PUT /api/surveys/:id/questions/order`

```json
{ "question_ids": ["66f...b", "66f...a", "66f...c"] }
```

必须包含该问卷的全部题目 id；返回重排后的题目列表。

---

## 4. 填写

### 4.1 获取填写页数据

`GET /api/fill/:code`（`code` 为 `share_code`，无需登录）

```json
{
  "survey": { "id": "...", "title": "...", "allow_anonymous": true, "share_url": "..." },
  "questions": [ { "id": "...", "order": 1, "type": "single", "...": "..." } ],
  "viewer": { "logged_in": false, "user_id": null },
  "already_submitted": false,
  "requires_login": false
}
```

| 失败 | 说明 |
| --- | --- |
| 404 | 短码不存在 |
| 409 | 问卷未发布 / 已关闭 / 已过截止时间 |

### 4.2 提交答卷

`POST /api/fill/:code/submit`（`allow_anonymous=true` 时可不登录）

```json
{
  "answers": [
    { "question_id": "q1...", "option_keys": ["A"] },
    { "question_id": "q2...", "option_keys": ["A", "C"] },
    { "question_id": "q3...", "text": "希望多讲案例" },
    { "question_id": "q4...", "number": 25 }
  ],
  "duration_ms": 45000
}
```

成功 `201`：

```json
{ "response_id": "66f...", "path": [1, 4, 5], "ended_early": false, "answered_count": 3, "ignored_answers": 0 }
```

- `path`：服务端**重新计算**出的作答路径（题号序列），不采信前端提交的路径
- `ignored_answers`：题目被跳过（不在路径上）或题号不属于本问卷而被忽略的答案数量

失败 `422`：

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "答卷未通过校验，请修正后重新提交",
    "details": {
      "path": [1, 2, 3, 4, 5],
      "errors": [
        { "question_id": "...", "order": 2, "title": "你对课程的建议", "messages": ["文本长度不能少于 2 个字符，当前 1 个"] }
      ]
    }
  }
}
```

| 失败 | 说明 |
| --- | --- |
| 401 | 非匿名问卷未登录 |
| 409 | 已关闭 / 已截止 / 不允许重复填写 |

---

## 5. 统计

### 5.1 整卷统计

`GET /api/surveys/:id/stats`

```json
{
  "survey": { "id": "...", "title": "...", "status": "published" },
  "total_responses": 12,
  "anonymous_responses": 8,
  "logged_in_responses": 4,
  "questions": [
    {
      "question_id": "...", "order": 1, "type": "single", "title": "你的身份",
      "answered": 12, "response_rate": 100,
      "options": [ { "key": "A", "label": "学生", "count": 9, "percent": 75 } ]
    },
    {
      "question_id": "...", "order": 2, "type": "multiple", "title": "喜欢的水果",
      "answered": 10, "response_rate": 83.33,
      "options": [ { "key": "A", "label": "苹果", "count": 7, "percent": 70 } ]
    },
    {
      "question_id": "...", "order": 3, "type": "text", "title": "建议",
      "answered": 9, "response_rate": 75,
      "text_count": 9, "avg_length": 12.4,
      "texts": ["希望多讲案例", "..."], "texts_truncated": false
    },
    {
      "question_id": "...", "order": 4, "type": "number", "title": "年龄",
      "answered": 9, "response_rate": 75,
      "number_count": 9, "avg": 21.33, "min": 18, "max": 26,
      "values": [18, 20, 26], "values_truncated": false
    }
  ]
}
```

> `answered` 是「实际回答过该题的人数」，因为有跳转，它可能小于总答卷数；`percent` 的分母也是 `answered` 而非总答卷数。

### 5.2 单题统计

`GET /api/surveys/:id/stats/questions/:questionId` → `{ "total_responses": 12, "question": { ... } }`

### 5.3 答卷明细

`GET /api/surveys/:id/responses?page=1&size=20`

```json
{
  "total": 12, "page": 1, "size": 20,
  "items": [
    {
      "id": "...", "anonymous": false, "respondent_id": "...", "submitted_at": "...",
      "answers": [
        { "question_id": "...", "question_order": 1, "question_title": "你的身份", "type": "single", "display": "A. 学生" }
      ]
    }
  ]
}
```

`display` 已把选项 key 还原为可读文案，填空题直接是文本或数字。

### 5.4 答卷导出 CSV（对标腾讯文档收集表「导出 Excel」）

`GET /api/surveys/:id/responses/export` → `200`，`Content-Type: text/csv; charset=utf-8`

- 表头：`提交时间`、`匿名`、`Q1 题干`、`Q2 题干`…
- 选项类题型（含下拉、评分）还原为选项文案，多选用「；」连接
- 文件带 UTF-8 BOM，Excel 直接双击打开不乱码
- 需要创建者身份（`Authorization: Bearer`）

### 5.5 填写二维码

`GET /api/surveys/:id/qrcode` → `200`

```json
{
  "survey_id": "…",
  "fill_url": "http://127.0.0.1:3000/fill.html?code=demo2026",
  "qr_data_url": "data:image/png;base64,iVBORw0KGgo…"
}
```

- 服务端用 `qrcode` 包把填写链接渲染成 280×280 PNG，前端 `<img>` 直接展示
- 二维码内容与 `share_url` 完全一致，手机相机扫码即达填写页
- 需要创建者身份（`Authorization: Bearer`），他人请求返回 403

---

## 6. 其他

`GET /api/health` → `{ "ok": true, "ts": 1760000000000 }`
