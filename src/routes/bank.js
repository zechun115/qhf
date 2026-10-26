'use strict';
const express = require('express');
const mongoose = require('mongoose');
const BankQuestion = require('../models/BankQuestion');
const Question = require('../models/Question');
const Survey = require('../models/Survey');
const Response = require('../models/Response');
const User = require('../models/User');
const { asyncHandler, badRequest, notFound, forbidden } = require('../utils/errors');
const { requireAuth } = require('../middleware/auth');
const { buildQuestionPayload, OPTION_TYPES } = require('../core/questionRules');

const router = express.Router();

/**
 * 题库题（bank_questions）路由 —— 第二阶段需求变更的八项能力都挂在这里：
 *   ① 保存常用题、建问卷时选用            POST /                  POST /from-question
 *   ② 把题目共享给其他用户                POST /:id/share         POST /:id/unshare
 *   ③ 改题不影响已做好的问卷              （问卷侧存快照，见 questions.js）
 *   ④ 修改历史 / 版本链 / 恢复旧版本      GET /:id/versions       POST /:id/revert
 *   ⑤ 同一题的不同版本同时存在            PUT /:id（生成新版本）  POST /:id/fork
 *   ⑥ 查看题目被哪些问卷使用              GET /:id/usage
 *   ⑦ 题库管理                            GET / 列表 + 上述接口
 *   ⑧ 单题跨问卷统计                      GET /:id/stats
 */

/** 序列化：ObjectId → 字符串，前端不做 ObjectId 处理 */
function toJson(doc, extra = {}) {
  return { ...doc.toObject(), id: doc._id.toString(), _id: undefined, ...extra };
}

/** 按用户名/昵称读取用户（共享用） */
async function loadUserByUsername(username) {
  if (typeof username !== 'string' || !username.trim()) throw badRequest('username 不能为空');
  const user = await User.findOne({ username: username.trim() });
  if (!user) throw notFound('该用户不存在');
  return user;
}

/** 取题库题并校验「owner 或被共享者」身份 */
async function loadAccessibleBankQuestion(req) {
  if (!mongoose.isValidObjectId(req.params.id)) throw badRequest('题库题目 id 格式不正确');
  const q = await BankQuestion.findById(req.params.id);
  if (!q) throw notFound('题库题目不存在');
  const isOwner = String(q.owner_id) === String(req.user.id);
  const isShared = (q.shared_with || []).some((u) => String(u) === String(req.user.id));
  if (!isOwner && !isShared) throw forbidden('没有访问该题库题目的权限');
  return { q, isOwner };
}

/**
 * 「使用情况」「跨问卷统计」只对出题人开放。
 *
 * 原因：这两个接口会把引用该题的问卷标题、以及跨问卷汇总后的答卷内容一起返回。
 * 题目被共享出去后，被共享者只是「可以使用这道题」，不应该看到别人问卷的
 * 标题与答卷数据，否则共享一次就等于把对方的数据暴露了。
 */
function assertOwner(isOwner) {
  if (!isOwner) throw forbidden('只有题目创建者可以查看使用情况与跨问卷统计');
}


/** 树内最新版本号 */
async function maxVersionOf(rootId) {
  const last = await BankQuestion.findOne({ root_id: rootId }).sort({ version: -1 });
  return last ? last.version : 0;
}

/**
 * 「修改 / 恢复旧版本」共用：在版本树末端追加一个新版本文档。
 * 新版本继承源版本的 shared_with（共享是树级语义：整棵树对被共享者可见），
 * 否则共享后作者出新版，被共享者会「丢题」。
 */
async function appendVersion(source, content, ownerId, parentId) {
  const maxVersion = await maxVersionOf(source.root_id);
  return BankQuestion.create({
    ...content,
    owner_id: ownerId,
    version: maxVersion + 1,
    root_id: source.root_id,
    parent_id: parentId,
    shared_with: source.shared_with || [],
    created_at: new Date(),
    updated_at: new Date(),
  });
}

// ───────────────────────── ⑦ 题库列表 ─────────────────────────
// scope=mine（默认）：我创建的；scope=shared：共享给我的。
// 每棵版本树只展示最新版本，避免列表里 v1/v2/v3 铺满一屏。
router.get(
  '/',
  requireAuth,
  asyncHandler(async (req, res) => {
    const scope = req.query.scope === 'shared' ? 'shared' : 'mine';
    const uid = String(req.user.id);
    const filter = scope === 'mine' ? { owner_id: req.user.id } : { shared_with: req.user.id };

    const all = await BankQuestion.find(filter).sort({ version: -1 });
    const latestByRoot = new Map();
    for (const doc of all) {
      const key = String(doc.root_id);
      if (!latestByRoot.has(key)) latestByRoot.set(key, doc); // 已按 version 倒序，第一条即最新
    }

    const list = [...latestByRoot.values()].map((doc) => {
      const owner = String(doc.owner_id) === uid;
      return toJson(doc, { is_owner: owner, is_shared_to_me: !owner });
    });
    list.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

    // 共享列表需要展示题目来源（owner 用户名），一次 in 查询取回
    const ownerIds = [...new Set(list.filter((q) => !q.is_owner).map((q) => q.owner_id))];
    const owners = ownerIds.length ? await User.find({ _id: { $in: ownerIds } }).select('username') : [];
    const nameMap = new Map(owners.map((u) => [String(u._id), u.username]));
    list.forEach((q) => {
      q.owner_username = nameMap.get(String(q.owner_id)) || '未知用户';
    });

    res.json({ scope, total: list.length, questions: list });
  })
);

// ───────────────────────── ① 新建题库题 ─────────────────────────
router.post(
  '/',
  requireAuth,
  asyncHandler(async (req, res) => {
    const payload = buildQuestionPayload(req.body);
    const doc = await BankQuestion.create({
      ...payload,
      owner_id: req.user.id,
      version: 1,
      shared_with: [],
    });
    doc.root_id = doc._id; // v1 的根就是自己（创建后再回填，避免 required 校验报 400）
    await doc.save();
    res.status(201).json({ question: toJson(doc) });
  })
);

// ───────────────────── ① 把问卷里的题存为常用题 ─────────────────────
router.post(
  '/from-question',
  requireAuth,
  asyncHandler(async (req, res) => {
    const questionId = req.body && req.body.question_id;
    if (!questionId) throw badRequest('question_id 不能为空');
    const question = await Question.findById(questionId);
    if (!question) throw notFound('题目不存在');
    const survey = await Survey.findById(question.survey_id);
    if (!survey) throw notFound('题目所属问卷不存在');
    if (String(survey.owner_id) !== String(req.user.id)) throw forbidden('只能保存自己问卷里的题目');

    const doc = await BankQuestion.create({
      type: question.type,
      title: question.title,
      required: question.required,
      options: question.options,
      constraints: question.constraints,
      owner_id: req.user.id,
      version: 1,
      shared_with: [],
    });
    doc.root_id = doc._id;
    await doc.save();
    res.status(201).json({ question: toJson(doc) });
  })
);

// ───────────────────────── 题库题详情 ─────────────────────────
router.get(
  '/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    res.json({ question: toJson(q, { is_owner: isOwner }) });
  })
);

// ──────────────── ④⑤ 修改题库题 = 追加新版本（旧版本保留） ────────────────
// 需求三的关键：这里永远不原地覆盖。旧问卷引用的是旧版本文档，
// 新版本是另一个文档，两条引用互不影响。
router.put(
  '/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    if (!isOwner) throw forbidden('只能修改自己创建的题库题目；被共享的题可以 fork 成自己的再改');

    // 部分更新语义：未传的字段继承当前版本内容（例如只改题干时选项保持不变）
    const body = req.body || {};
    const payload = buildQuestionPayload({
      type: body.type || q.type,
      title: body.title !== undefined ? body.title : q.title,
      required: body.required !== undefined ? body.required : q.required,
      options:
        body.options !== undefined
          ? body.options
          : (q.options || []).map((o) => ({ key: o.key, label: o.label })),
      constraints: body.constraints !== undefined ? body.constraints : q.constraints,
    });
    const next = await appendVersion(q, payload, req.user.id, q._id);
    // 注意：这里刻意不改动旧版本文档（不改 updated_at）。
    // 版本历史应当是只读的，旧版本一旦产生就不再变化；列表页取的是每棵树里
    // version 最大的那条，新版本的 updated_at 本来就是最新的，排序不受影响。
    res.status(201).json({ question: toJson(next), previous_version: q.version });
  })
);

// ──────────────── ⑤ fork：基于任意可访问版本开一棵新树 ────────────────
// 团队场景：同事拿到共享题后 fork 成自己的题库题，之后各改各的互不干扰。
router.post(
  '/:id/fork',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q } = await loadAccessibleBankQuestion(req);
    const doc = await BankQuestion.create({
      type: q.type,
      title: q.title,
      required: q.required,
      options: q.options,
      constraints: q.constraints,
      owner_id: req.user.id,
      version: 1,
      parent_id: q._id, // 记录「从哪个题改来的」（需求四）
      shared_with: [],
    });
    doc.root_id = doc._id;
    await doc.save();
    res.status(201).json({ question: toJson(doc, { forked_from: q._id.toString() }) });
  })
);

// ───────────────────── ④ 版本链：v1 → v2 → v3 ─────────────────────
router.get(
  '/:id/versions',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q } = await loadAccessibleBankQuestion(req);
    const versions = await BankQuestion.find({ root_id: q.root_id }).sort({ version: 1 });
    res.json({
      root_id: q.root_id.toString(),
      latest_version: versions.length ? versions[versions.length - 1].version : q.version,
      versions: versions.map((v) => toJson(v, {
        is_owner: String(v.owner_id) === String(req.user.id),
      })),
    });
  })
);

// ──────────────── ④ 恢复旧版本 = 以旧版本内容追加新版本 ────────────────
// 不删不回滚，历史链保持完整：v1 → v2 → v3(=v1 内容)。
router.post(
  '/:id/revert',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    if (!isOwner) throw forbidden('只有创建者可以恢复旧版本');

    const targetVersion = Number(req.body && req.body.version);
    if (!Number.isInteger(targetVersion) || targetVersion < 1) throw badRequest('version 必须是正整数');
    const old = await BankQuestion.findOne({ root_id: q.root_id, version: targetVersion });
    if (!old) throw notFound(`版本 v${targetVersion} 不存在`);

    const next = await appendVersion(q, {
      type: old.type,
      title: old.title,
      required: old.required,
      options: old.options,
      constraints: old.constraints,
    }, req.user.id, old._id);
    res.status(201).json({ question: toJson(next), restored_from: targetVersion });
  })
);

// ───────────────────── ② 共享 / 取消共享（树级） ─────────────────────
router.post(
  '/:id/share',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    if (!isOwner) throw forbidden('只有创建者可以共享题目');
    const user = await loadUserByUsername(req.body && req.body.username);
    if (String(user._id) === String(req.user.id)) throw badRequest('不能共享给自己');

    // 共享是树级语义：整棵版本树对所有版本生效
    await BankQuestion.updateMany({ root_id: q.root_id }, { $addToSet: { shared_with: user._id } });
    res.json({ shared: true, username: user.username, user_id: user._id.toString() });
  })
);

router.post(
  '/:id/unshare',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    if (!isOwner) throw forbidden('只有创建者可以取消共享');
    const user = await loadUserByUsername(req.body && req.body.username);
    await BankQuestion.updateMany({ root_id: q.root_id }, { $pull: { shared_with: user._id } });
    res.json({ shared: false, username: user.username });
  })
);

// ───────────────────── ⑥ 题目被哪些问卷使用 ─────────────────────
// 通过问卷题上的溯源字段反查；跨整棵版本树（旧问卷引用 v1、新问卷引用 v2 都算）。
router.get(
  '/:id/usage',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    assertOwner(isOwner);
    const versionIds = await BankQuestion.find({ root_id: q.root_id }).distinct('_id');
    const refs = await Question.find({ bank_question_id: { $in: versionIds } })
      .select('survey_id bank_question_id bank_version title order');
    const surveyIds = [...new Set(refs.map((r) => String(r.survey_id)))];
    const surveys = await Survey.find({ _id: { $in: surveyIds } })
      .select('title status created_at published_at')
      .sort({ created_at: -1 });

    res.json({
      version_count: versionIds.length,
      survey_count: surveys.length,
      surveys: surveys.map((s) => ({
        ...s.toObject(),
        id: s._id.toString(),
        _id: undefined,
        used_versions: refs
          .filter((r) => String(r.survey_id) === String(s._id))
          .map((r) => ({ bank_version: r.bank_version, title: r.title })),
      })),
    });
  })
);

// ───────────────────── ⑧ 单题跨问卷统计 ─────────────────────
// 聚合管道：responses 按 survey_id 展开 → 匹配该题所有快照 → 按题型分组统计。
// 选项类：$unwind option_keys 后按 key 计数；
// 数字类：$min/$max/$avg；文本类：计数 + 最近 20 条样本；日期类：按值计数。
router.get(
  '/:id/stats',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { q, isOwner } = await loadAccessibleBankQuestion(req);
    assertOwner(isOwner);
    const versionIds = await BankQuestion.find({ root_id: q.root_id }).distinct('_id');
    const refs = await Question.find({ bank_question_id: { $in: versionIds } }).select('survey_id');
    const surveyIds = [...new Set(refs.map((r) => r.survey_id))];
    const questionIds = refs.map((r) => r._id);

    if (!questionIds.length) {
      return res.json({
        question: toJson(q),
        survey_count: 0, response_count: 0, total_answers: 0,
        option_counts: [], number_stats: null, text_stats: null, date_counts: [],
      });
    }

    const baseMatch = { survey_id: { $in: surveyIds } };
    const answerMatch = { 'answers.question_id': { $in: questionIds } };

    const [totalAgg] = await Response.aggregate([
      { $match: baseMatch },
      { $unwind: '$answers' },
      { $match: answerMatch },
      { $group: { _id: '$_id' } },
      { $count: 'responses' },
    ]);
    const [answersAgg] = await Response.aggregate([
      { $match: baseMatch },
      { $unwind: '$answers' },
      { $match: answerMatch },
      { $count: 'answers' },
    ]);

    let optionCounts = [];
    let numberStats = null;
    let textStats = null;
    let dateCounts = [];

    if (OPTION_TYPES.includes(q.type)) {
      optionCounts = await Response.aggregate([
        { $match: baseMatch },
        { $unwind: '$answers' },
        { $match: answerMatch },
        { $unwind: '$answers.option_keys' },
        { $group: { _id: '$answers.option_keys', count: { $sum: 1 } } },
        { $sort: { count: -1, _id: 1 } },
      ]);
      // 用最新版本的选项文案补 label（跨版本 key 语义一致的常见场景）
      const labelMap = new Map((q.options || []).map((o) => [o.key, o.label]));
      optionCounts = optionCounts.map((row) => ({
        key: row._id,
        label: labelMap.get(row._id) || row._id,
        count: row.count,
      }));
    }

    if (q.type === 'number') {
      const [row] = await Response.aggregate([
        { $match: baseMatch },
        { $unwind: '$answers' },
        { $match: { ...answerMatch, 'answers.number': { $ne: null } } },
        {
          $group: {
            _id: null,
            count: { $sum: 1 },
            min: { $min: '$answers.number' },
            max: { $max: '$answers.number' },
            avg: { $avg: '$answers.number' },
          },
        },
      ]);
      numberStats = row ? { count: row.count, min: row.min, max: row.max, avg: Math.round(row.avg * 100) / 100 } : null;
    }

    if (q.type === 'text') {
      const [row] = await Response.aggregate([
        { $match: baseMatch },
        { $sort: { submitted_at: -1 } },
        { $unwind: '$answers' },
        { $match: { ...answerMatch, 'answers.text': { $ne: null, $nin: ['', null] } } },
        { $group: { _id: null, count: { $sum: 1 }, samples: { $push: '$answers.text' } } },
        { $project: { count: 1, samples: { $slice: ['$samples', 20] } } },
      ]);
      textStats = row ? { count: row.count, samples: row.samples } : { count: 0, samples: [] };
    }

    if (q.type === 'date') {
      dateCounts = await Response.aggregate([
        { $match: baseMatch },
        { $unwind: '$answers' },
        { $match: { ...answerMatch, 'answers.date': { $ne: null } } },
        { $group: { _id: '$answers.date', count: { $sum: 1 } } },
        { $sort: { count: -1, _id: 1 } },
        { $limit: 30 },
      ]).then((rows) => rows.map((r) => ({ date: r._id, count: r.count })));
    }

    res.json({
      question: toJson(q),
      survey_count: surveyIds.length,
      response_count: totalAgg ? totalAgg.responses : 0,
      total_answers: answersAgg ? answersAgg.answers : 0,
      option_counts: optionCounts,
      number_stats: numberStats,
      text_stats: textStats,
      date_counts: dateCounts,
    });
  })
);

module.exports = { router };
