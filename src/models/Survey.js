'use strict';
const mongoose = require('mongoose');

/**
 * surveys 集合：问卷主体（元信息 + 生命周期状态）
 *
 * 设计说明：
 * 1) 题目不内嵌在同文档里，而是拆到 questions 集合（见 Question.js 的理由），
 *    这里只保留 question_count 这个「计数冗余」，用于列表页展示，避免列表页 N+1 查询。
 *    该字段是所有冗余字段里唯一的一个，由题目增删的写路径同步维护。
 * 2) 生命周期用 status 一个字段表达（draft → published → closed），
 *    不额外存 is_published / is_closed 两个布尔，避免状态互相矛盾。
 * 3) deadline 与 status 分离：过期不等于关闭，判定「是否还能填」时两者都要看，
 *    这样「延长截止时间」只需要改 deadline，不用重新发布。
 * 4) share_code 是给外部填答者用的短码，与 _id 分离：
 *    链接里不暴露数据库主键，同时便于以后换短链/自定义别名。
 */
const surveySchema = new mongoose.Schema(
  {
    owner_id: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    title: { type: String, required: true, trim: true, maxlength: 120 },
    description: { type: String, default: '', maxlength: 2000 },
    allow_anonymous: { type: Boolean, default: false },
    allow_multiple: { type: Boolean, default: true },
    status: {
      type: String,
      enum: ['draft', 'published', 'closed'],
      default: 'draft',
    },
    deadline: { type: Date, default: null },
    // 提交后的致谢 / 提示语（对标腾讯文档收集表）；不影响答卷结构，发布后仍可修改
    submit_message: { type: String, default: '感谢你的填写！', maxlength: 200 },
    share_code: { type: String, required: true },
    question_count: { type: Number, default: 0 },
    created_at: { type: Date, default: Date.now },
    updated_at: { type: Date, default: Date.now },
    published_at: { type: Date, default: null },
    closed_at: { type: Date, default: null },
  },
  { collection: 'surveys', versionKey: false }
);

// 我的问卷列表：按创建者过滤 + 按创建时间倒序
surveySchema.index({ owner_id: 1, created_at: -1 });
// 填写入口按短码查，必须唯一
surveySchema.index({ share_code: 1 }, { unique: true });

module.exports = mongoose.model('Survey', surveySchema);
