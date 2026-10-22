'use strict';
const express = require('express');
const Question = require('../models/Question');
const Survey = require('../models/Survey');
const { asyncHandler, badRequest, notFound, forbidden, conflict } = require('../utils/errors');
const { requireAuth } = require('../middleware/auth');
const { loadOwnedSurvey } = require('./surveys');
const { buildQuestionPayload, validateJumpRules, OPTION_TYPES } = require('../core/questionRules');

const router = express.Router();

function assertDraft(survey) {
  if (survey.status !== 'draft') {
    throw conflict('问卷已发布或已关闭，不能再修改题目；请新建一份问卷或关闭后重建');
  }
}

async function assertSurveyOfQuestion(req) {
  const question = await Question.findById(req.params.id);
  if (!question) throw notFound('题目不存在');
  const survey = await Survey.findById(question.survey_id);
  if (!survey) throw notFound('题目所属问卷不存在');
  if (String(survey.owner_id) !== String(req.user.id)) throw forbidden('只能操作自己问卷的题目');
  return { question, survey };
}

/**
 * 把题目顺序写成 1..n。
 *
 * 因为 {survey_id, order} 上有唯一索引，直接批量改会撞车：
 * 例如把 [A(1), B(2)] 调成 [B(1), A(2)]，无论先改哪一条，都会与另一条已占用的题号冲突。
 * 所以分两步：先把所有题号整体抬到一个安全区间（+offset），再写最终值。
 */
async function applyOrders(surveyId, orderedIds) {
  const all = await Question.find({ survey_id: surveyId });
  const offset = all.length + 1000;

  await Question.bulkWrite(
    all.map((q) => ({
      updateOne: { filter: { _id: q._id }, update: { $set: { order: q.order + offset } } },
    }))
  );

  await Question.bulkWrite(
    orderedIds.map((id, i) => ({
      updateOne: { filter: { _id: id }, update: { $set: { order: i + 1, updated_at: new Date() } } },
    }))
  );
}

/** 把同一份问卷的题目按当前顺序重排为 1..n，返回最新题目列表 */
async function renumber(surveyId) {
  const list = await Question.find({ survey_id: surveyId }).sort({ order: 1 });
  await applyOrders(
    surveyId,
    list.map((q) => q._id)
  );
  return Question.find({ survey_id: surveyId }).sort({ order: 1 });
}

/**
 * 删除题目 / 调整顺序后，指向「前面」的跳转规则会变成非法（禁止向前跳），
 * 这里统一清理掉，保证库里不留死规则。
 */
async function cleanupInvalidRules(surveyId) {
  const survey = await Survey.findById(surveyId);
  const questions = await Question.find({ survey_id: surveyId }).sort({ order: 1 });
  const byId = new Map(questions.map((q) => [String(q._id), q]));
  const ops = [];

  questions.forEach((q) => {
    const kept = (q.jump_rules || []).filter((r) => {
      if (r.to === 'end') return true;
      const target = byId.get(String(r.target_question_id));
      return Boolean(target) && target.order > q.order;
    });
    if (kept.length !== (q.jump_rules || []).length) {
      ops.push({ updateOne: { filter: { _id: q._id }, update: { $set: { jump_rules: kept } } } });
    }
  });

  if (ops.length) await Question.bulkWrite(ops);
  if (survey) {
    survey.question_count = questions.length;
    await survey.save();
  }
  return questions.length;
}

// 添加题目
router.post(
  '/surveys/:id/questions',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    assertDraft(survey);

    const payload = buildQuestionPayload(req.body);
    const last = await Question.findOne({ survey_id: survey._id }).sort({ order: -1 });
    const order = last ? last.order + 1 : 1;

    const existing = await Question.find({ survey_id: survey._id });
    const rules = validateJumpRules(req.body.jump_rules, { ...payload, order }, existing);

    const question = await Question.create({ survey_id: survey._id, order, ...payload, jump_rules: rules });
    survey.question_count = order;
    survey.updated_at = new Date();
    await survey.save();

    res.status(201).json({
      question: { ...question.toObject(), id: question._id.toString(), _id: undefined },
    });
  })
);

// 修改题目（题干 / 必答 / 选项 / 约束 / 跳转规则）
router.patch(
  '/questions/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { question, survey } = await assertSurveyOfQuestion(req);
    assertDraft(survey);

    const body = req.body || {};
    const nextType = body.type || question.type;
    if (nextType !== question.type && body.type !== undefined) {
      // 改题型时按新题型重建选项与约束，避免遗留上一题型的数据
      const payload = buildQuestionPayload({ ...body, type: nextType });
      question.type = payload.type;
      question.options = payload.options;
      question.constraints = payload.constraints;
      question.title = payload.title;
      question.required = payload.required;
    } else {
      if (body.title !== undefined) {
        if (typeof body.title !== 'string' || !body.title.trim()) throw badRequest('题干不能为空');
        question.title = body.title.trim();
      }
      if (body.required !== undefined) question.required = Boolean(body.required);
      if (body.options !== undefined) {
        if (!OPTION_TYPES.includes(question.type)) throw badRequest('本题型不支持设置选项');
        question.options = require('../core/questionRules').normalizeOptions(body.options);
      }
      if (body.constraints !== undefined) {
        question.constraints = require('../core/questionRules').normalizeConstraints(question.type, body.constraints);
      }
    }

    if (body.jump_rules !== undefined) {
      const others = await Question.find({ survey_id: survey._id });
      question.jump_rules = validateJumpRules(body.jump_rules, question, others);
    }

    question.updated_at = new Date();
    await question.save();
    survey.updated_at = new Date();
    await survey.save();

    res.json({ question: { ...question.toObject(), id: question._id.toString(), _id: undefined } });
  })
);

// 删除题目：删除后重排题号，并清理指向它的 / 变成向前的跳转规则
router.delete(
  '/questions/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { question, survey } = await assertSurveyOfQuestion(req);
    assertDraft(survey);

    await question.deleteOne();
    const count = await cleanupInvalidRules(survey._id);
    await renumber(survey._id);
    survey.question_count = count;
    await survey.save();

    res.json({ deleted: true, question_count: count });
  })
);

// 调整题目顺序
router.put(
  '/surveys/:id/questions/order',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    assertDraft(survey);

    const ids = (req.body && req.body.question_ids) || [];
    if (!Array.isArray(ids) || !ids.length) throw badRequest('question_ids 不能为空');

    const existing = await Question.find({ survey_id: survey._id });
    if (existing.length !== ids.length) throw badRequest('question_ids 必须包含该问卷的全部题目');
    const existSet = new Set(existing.map((q) => String(q._id)));
    if (ids.some((id) => !existSet.has(String(id)))) throw badRequest('存在不属于本问卷的题目 id');

    await applyOrders(survey._id, ids);
    // 顺序变化后，原本合法的「向后跳」可能变成「向前跳」，需要清理
    await cleanupInvalidRules(survey._id);

    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    res.json({
      questions: questions.map((q) => ({ ...q.toObject(), id: q._id.toString(), _id: undefined })),
    });
  })
);

module.exports = { router, cleanupInvalidRules, renumber };
