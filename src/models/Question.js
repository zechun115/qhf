'use strict';
const mongoose = require('mongoose');

/**
 * questions 集合：题目（一道题一个文档）
 *
 * 为什么拆成独立集合，而不是全部嵌在 survey 文档里？
 * - 题目是本系统读写最频繁的编辑单元：改一个选项只应该更新一道题，
 *   内嵌结构下每次编辑都要整份问卷读-改-写，容易产生并发覆盖（lost update）。
 * - 题型异构（单选/多选/文本/数字）导致每道题的字段集合不同，
 *   独立文档可以让「数字题的 min/max」和「多选题的 min_choice/max_choice」各存各的，
 *   不需要为所有题型准备一堆可空字段。
 * - 第二阶段要按题型扩展（比如新增下拉题、评分题）时，只需要新文档多几个字段，
 *   老文档不受影响，也不需要进行集合级迁移。
 *
 * 代价：读整份问卷需要两条查询（surveys + questions），
 * 统计时需要按 question_id 关联 answers。这两个代价都可以通过一次 in 查询和聚合管道消化，
 * 相对于编辑路径的收益是值得的。
 *
 * 顺序：用 order 整数 + {survey_id, order} 唯一复合索引保证；
 * 调整顺序用 bulkWrite 局部更新 order，而不是重排整个数组。
 */
const optionSchema = new mongoose.Schema(
  {
    key: { type: String, required: true }, // 选项标识，如 A / B / C
    label: { type: String, required: true }, // 展示文案
  },
  { _id: false }
);

/**
 * 跳转规则：规则存在数据里，逻辑不写死在代码里。
 *
 * when 描述「什么情况下命中」：
 *   op = option_selected  : 答案中选了 option_key（单选/多选通用）
 *   op = number_eq / number_gte / number_lt / number_between : 数字题比较
 *   op = text_contains    : 文本题包含关键字
 * target 描述「跳到哪里」：
 *   to = question（跳到指定题目） / end（直接结束问卷）
 */
const jumpRuleSchema = new mongoose.Schema(
  {
    when: {
      op: {
        type: String,
        enum: ['option_selected', 'number_eq', 'number_gte', 'number_lt', 'number_between', 'text_contains'],
        required: true,
      },
      option_key: { type: String, default: null },
      value: { type: Number, default: null },
      value2: { type: Number, default: null },
      text: { type: String, default: null },
    },
    to: { type: String, enum: ['question', 'end'], default: 'question' },
    target_question_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Question', default: null },
    priority: { type: Number, default: 0 }, // 数字小的先判定
  },
  { _id: false }
);

const questionSchema = new mongoose.Schema(
  {
    survey_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Survey', required: true },
    order: { type: Number, required: true }, // 1-based 题号
    type: { type: String, enum: ['single', 'multiple', 'text', 'number', 'dropdown', 'rating', 'date'], required: true },
    title: { type: String, required: true, trim: true, maxlength: 500 },
    required: { type: Boolean, default: false },
    options: { type: [optionSchema], default: [] }, // single / multiple / dropdown 使用；rating 固定为 1~5 星

    // 约束按题型分开存，只填对应题型用得到的字段
    constraints: {
      min_choice: { type: Number, default: null }, // multiple
      max_choice: { type: Number, default: null }, // multiple
      min_length: { type: Number, default: null }, // text
      max_length: { type: Number, default: null }, // text
      min: { type: Number, default: null }, // number
      max: { type: Number, default: null }, // number
      integer: { type: Boolean, default: null }, // number
    },

    jump_rules: { type: [jumpRuleSchema], default: [] },

    // ── 第二阶段新增：题库溯源字段 ─────────────────────────────
    // 题目内容仍是完整快照（加入问卷那一刻拷贝），这两个字段只回答
    // 「这题来自题库哪个版本」：usage 反查（需求六）与跨问卷统计（需求八）
    // 靠它们把问卷题和题库版本树连起来。
    // 旧问卷没有这两个字段（null），读取端按「非题库题」分支处理，兼容不迁移。
    bank_question_id: { type: mongoose.Schema.Types.ObjectId, ref: 'BankQuestion', default: null },
    bank_version: { type: Number, default: null }, // 选题时的题库版本号快照

    created_at: { type: Date, default: Date.now },
    updated_at: { type: Date, default: Date.now },
  },
  { collection: 'questions', versionKey: false }
);

// 同一份问卷里题号唯一，同时支撑「按问卷取题并按题号排序」的查询
questionSchema.index({ survey_id: 1, order: 1 }, { unique: true });
// 跳转目标反查（删除题目时要清理指向它的规则）
questionSchema.index({ 'jump_rules.target_question_id': 1 });
// 题库溯源反查：某道题库题（的所有版本）被哪些问卷使用（需求六 / 需求八）
questionSchema.index({ bank_question_id: 1 });

module.exports = mongoose.model('Question', questionSchema);
