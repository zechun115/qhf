'use strict';
const mongoose = require('mongoose');

/**
 * responses 集合：一次提交 = 一个文档（答案内嵌）
 *
 * 为什么把 answers 内嵌，而不是单独建一个 answers 集合？
 * - 一次提交天然是一个一致性单元：内嵌后「写入整份答卷」是单文档操作，
 *   MongoDB 保证单文档原子性，不会出现「答了 5 题只存进去 3 题」的中间态；
 *   如果拆表，就必须依赖事务，成本高且没必要。
 * - 统计时需要「整份答卷」的上下文（比如多选题的每题选择数），
 *   内嵌后一次查询即可拿到，$unwind + $group 一条聚合管道出结果。
 * - 单份问卷的答案体积可控（题目数上限 200、文本长度上限约束），不会逼近 16MB 文档上限。
 *
 * 这里确实做了一处「受控冗余」：answers 里冗余了 question_order。
 * 理由：题目以后可能被调整顺序，但历史答卷需要记录「当时是第几题」，
 * 否则回看答卷时顺序会错乱。该字段在提交时一次性写入，之后不再变更，属于快照而非缓存。
 *
 * schema_version 是给第二阶段预留的：新需求改数据结构后，
 * 老答卷按 v1 解释、新答卷写 v2，读取端按版本分支，避免全量迁移。
 */
const answerSchema = new mongoose.Schema(
  {
    question_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Question', required: true },
    question_order: { type: Number, required: true }, // 提交时的题号快照
    option_keys: { type: [String], default: [] }, // 单选 / 多选 / 下拉 / 评分
    text: { type: String, default: null }, // 文本填空
    number: { type: Number, default: null }, // 数字填空
    date: { type: String, default: null }, // 日期题（YYYY-MM-DD 字符串，便于直接导出与展示）
  },
  { _id: false }
);

const responseSchema = new mongoose.Schema(
  {
    survey_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Survey', required: true },
    // 匿名填写时为 null；非匿名填写时为登录用户 id
    respondent_id: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },
    anonymous: { type: Boolean, default: false },

    answers: { type: [answerSchema], default: [] },
    // 服务端按跳转规则推导出的实际作答路径（题目 id 顺序），用于回放与作弊核对
    path: { type: [mongoose.Schema.Types.ObjectId], default: [] },

    submitted_at: { type: Date, default: Date.now },
    schema_version: { type: Number, default: 1 },
    meta: {
      user_agent: { type: String, default: '' },
      duration_ms: { type: Number, default: null },
    },
  },
  { collection: 'responses', versionKey: false }
);

// 统计：按问卷取全部答卷，按时间倒序
responseSchema.index({ survey_id: 1, submitted_at: -1 });
// 限制重复填写：判断「这个人在本问卷是否已经提交过」
responseSchema.index({ survey_id: 1, respondent_id: 1 });
// 按题目反查答案（单题统计 / 排查某题的数据）
responseSchema.index({ survey_id: 1, 'answers.question_id': 1 });

module.exports = mongoose.model('Response', responseSchema);
