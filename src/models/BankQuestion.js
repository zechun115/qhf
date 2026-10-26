'use strict';
const mongoose = require('mongoose');

/**
 * bank_questions 集合：题库题（第二阶段新增）
 *
 * 需求背景（需求变更第一~七条）：用户希望题目可以脱离问卷单独保存、复用、
 * 共享给他人，并且修改题目时不能影响已经使用它的问卷。
 *
 * 核心设计决策——「版本即文档」+「问卷侧存快照」：
 *
 * 1) 版本即文档：每次修改题库题不原地覆盖，而是插入一个新文档，
 *    version + 1，parent_id 指向修改前的版本，同一棵版本树的文档共享 root_id。
 *    这样 v1 → v2 → v3 的链条天然由 {root_id, version} 表达，
 *    「找回旧版本」只是读旧文档，「恢复旧版本」= 以旧文档内容再 fork 一个新版本。
 *    对比方案（数组内嵌 history）：数组会随修改次数无限增长，且并发修改
 *    两个版本时互相覆盖；独立文档则可以按版本各自被引用，天然支持
 *    「不同问卷使用不同版本」（需求五）。
 *
 * 2) 问卷侧存快照：问卷题目（questions 集合）增加 bank_question_id /
 *    bank_version 两个字段记录「这题来自题库哪个版本」，但题目内容在
 *    加入问卷那一刻整体拷贝（快照）。题库题之后无论怎么出新版本，
 *    已加入问卷的题目内容一个字节都不会变（需求三），历史答卷的数据
 *    语义始终保持对得上。
 *
 * 3) 共享用 shared_with 用户 id 数组而不是单独的共享表：
 *    单题共享是低频小规模操作（一个题最多共享给一个团队），内嵌数组
 *    一次查询即可判断权限；被共享者获得「读 + fork」，不能改原作者的题，
 *    fork 出来的新树 owner 是自己，从而避免写写冲突。
 *
 * 列表查询约定：题库列表只展示每棵版本树的最新版本，
 * 用 {root_id: 1, version: -1} 分组取第一条（聚合 $sort + $group $first）。
 */
const optionSchema = new mongoose.Schema(
  {
    key: { type: String, required: true },
    label: { type: String, required: true },
  },
  { _id: false }
);

const constraintsSchema = new mongoose.Schema(
  {
    min_choice: { type: Number, default: null },
    max_choice: { type: Number, default: null },
    min_length: { type: Number, default: null },
    max_length: { type: Number, default: null },
    min: { type: Number, default: null },
    max: { type: Number, default: null },
    integer: { type: Boolean, default: null },
  },
  { _id: false }
);

const bankQuestionSchema = new mongoose.Schema(
  {
    owner_id: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
    type: { type: String, enum: ['single', 'multiple', 'text', 'number', 'dropdown', 'rating', 'date'], required: true },
    title: { type: String, required: true, trim: true, maxlength: 500 },
    required: { type: Boolean, default: false },
    options: { type: [optionSchema], default: [] },
    constraints: { type: constraintsSchema, default: () => ({}) },

    // 版本链字段
    version: { type: Number, required: true, min: 1 }, // 树内版本号，从 1 开始
    // v1 的根是自身：由路由层在 create 后回填（先插入拿到 _id，再写 root_id），
    // 因此 schema 层不设 required，靠写路径约定保证非空；版本树查询都命中 root_id 索引。
    root_id: { type: mongoose.Schema.Types.ObjectId, ref: 'BankQuestion' },
    parent_id: { type: mongoose.Schema.Types.ObjectId, ref: 'BankQuestion', default: null }, // 修改/恢复来源版本

    // 共享：被共享者可读、可选题、可 fork；不能改原题
    shared_with: { type: [mongoose.Schema.Types.ObjectId], default: [] },

    created_at: { type: Date, default: Date.now },
    updated_at: { type: Date, default: Date.now },
  },
  { collection: 'bank_questions', versionKey: false }
);

// 我的题库列表（按更新时间倒序）
bankQuestionSchema.index({ owner_id: 1, updated_at: -1 });
// 取一棵版本树的全部版本 / 判断最新版本
bankQuestionSchema.index({ root_id: 1, version: -1 });
// 「共享给我的」反查
bankQuestionSchema.index({ shared_with: 1 });
// 跨问卷统计时按树根找全部版本
bankQuestionSchema.index({ shared_with: 1, root_id: 1 });

module.exports = mongoose.model('BankQuestion', bankQuestionSchema);
