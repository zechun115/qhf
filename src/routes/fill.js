'use strict';
const express = require('express');
const Survey = require('../models/Survey');
const Question = require('../models/Question');
const Response = require('../models/Response');
const { asyncHandler, notFound, conflict, unprocessable, badRequest, unauthorized } = require('../utils/errors');
const { optionalAuth } = require('../middleware/auth');
const { computePath } = require('../core/jump');
const { validateAnswer } = require('../core/validation');
const { baseUrl } = require('./surveys');

const router = express.Router();

/** 问卷当前是否还能填写；不能填时给出原因 */
function checkAccepting(survey) {
  if (survey.status === 'draft') return '问卷尚未发布';
  if (survey.status === 'closed') return '问卷已关闭';
  if (survey.deadline && new Date() > new Date(survey.deadline)) return '问卷已过截止时间';
  return null;
}

function questionToClient(q) {
  return {
    id: String(q._id),
    order: q.order,
    type: q.type,
    title: q.title,
    required: q.required,
    options: q.options,
    constraints: q.constraints,
    jump_rules: (q.jump_rules || []).map((r) => ({
      when: r.when,
      to: r.to,
      target_question_id: r.target_question_id ? String(r.target_question_id) : null,
      priority: r.priority,
    })),
  };
}

// 填写页初始化：拿问卷信息和全部题目
router.get(
  '/:code',
  optionalAuth,
  asyncHandler(async (req, res) => {
    const survey = await Survey.findOne({ share_code: req.params.code });
    if (!survey) throw notFound('问卷不存在或链接有误');

    const reason = checkAccepting(survey);
    if (reason) throw conflict(reason);

    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    if (!questions.length) throw conflict('该问卷还没有题目');

    let alreadySubmitted = false;
    if (req.user && !survey.allow_multiple) {
      const n = await Response.countDocuments({ survey_id: survey._id, respondent_id: req.user.id });
      alreadySubmitted = n > 0;
    }

    res.json({
      survey: {
        id: String(survey._id),
        title: survey.title,
        description: survey.description,
        allow_anonymous: survey.allow_anonymous,
        allow_multiple: survey.allow_multiple,
        submit_message: survey.submit_message,
        deadline: survey.deadline,
        share_code: survey.share_code,
        share_url: `${baseUrl(req)}/fill.html?code=${survey.share_code}`,
        question_count: questions.length,
      },
      questions: questions.map(questionToClient),
      viewer: { logged_in: Boolean(req.user), user_id: req.user ? req.user.id : null },
      already_submitted: alreadySubmitted,
      requires_login: !survey.allow_anonymous && !req.user,
    });
  })
);

// 提交答卷
router.post(
  '/:code/submit',
  optionalAuth,
  asyncHandler(async (req, res) => {
    const survey = await Survey.findOne({ share_code: req.params.code });
    if (!survey) throw notFound('问卷不存在或链接有误');

    const reason = checkAccepting(survey);
    if (reason) throw conflict(reason);

    // 非匿名问卷必须登录
    if (!survey.allow_anonymous && !req.user) throw unauthorized('该问卷要求登录后才能填写');

    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    if (!questions.length) throw conflict('该问卷还没有题目');

    const rawAnswers = (req.body && req.body.answers) || [];
    if (!Array.isArray(rawAnswers)) throw badRequest('answers 必须是数组');

    // 以题库里的题目 id 为准，忽略不属于本问卷的题号
    const validIds = new Set(questions.map((q) => String(q._id)));
    const answerMap = new Map();
    rawAnswers.forEach((a) => {
      if (!a || !a.question_id) return;
      const id = String(a.question_id);
      if (!validIds.has(id)) return;
      answerMap.set(id, a); // 同一题重复提交时以最后一条为准
    });

    // 服务端权威重算路径：前端提交的路径一律不采信
    const { path, endedEarly } = computePath(questions, answerMap);

    // 只校验路径上的题目；被跳过的题目即使前端带了答案也不参与校验
    const errors = [];
    const toSave = [];
    path.forEach((q) => {
      const raw = answerMap.get(String(q._id));
      const result = validateAnswer(q, raw);
      if (!result.ok) {
        errors.push({ question_id: String(q._id), order: q.order, title: q.title, messages: result.errors });
        return;
      }
      if (result.value) {
        toSave.push({
          question_id: q._id,
          question_order: q.order,
          option_keys: result.value.option_keys || [],
          text: result.value.text !== undefined ? result.value.text : null,
          number: result.value.number !== undefined ? result.value.number : null,
          date: result.value.date !== undefined ? result.value.date : null,
        });
      }
    });

    if (errors.length) {
      throw unprocessable('答卷未通过校验，请修正后重新提交', { errors, path: path.map((q) => q.order) });
    }

    // 限制重复填写
    if (!survey.allow_multiple && req.user) {
      const exists = await Response.countDocuments({ survey_id: survey._id, respondent_id: req.user.id });
      if (exists) throw conflict('该问卷不允许同一用户重复填写');
    }

    const anonymous = !req.user;
    const response = await Response.create({
      survey_id: survey._id,
      respondent_id: req.user ? req.user.id : null,
      anonymous,
      answers: toSave,
      path: path.map((q) => q._id),
      submitted_at: new Date(),
      schema_version: 1,
      meta: {
        user_agent: String(req.get('user-agent') || '').slice(0, 300),
        duration_ms: Number.isFinite(Number(req.body && req.body.duration_ms))
          ? Number(req.body.duration_ms)
          : null,
      },
    });

    res.status(201).json({
      response_id: String(response._id),
      path: path.map((q) => q.order),
      ended_early: endedEarly,
      answered_count: toSave.length,
      ignored_answers: rawAnswers.length - toSave.length,
      submit_message: survey.submit_message,
    });
  })
);

module.exports = { router, checkAccepting };
