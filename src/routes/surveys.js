'use strict';
const express = require('express');
const { customAlphabet } = require('nanoid');
const QRCode = require('qrcode');
const Survey = require('../models/Survey');
const Question = require('../models/Question');
const Response = require('../models/Response');
const { asyncHandler, badRequest, notFound, forbidden, conflict } = require('../utils/errors');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
// 去掉容易看错的字符（0/O、1/l/I），方便手抄短链
const newCode = customAlphabet('23456789abcdefghjkmnpqrstuvwxyz', 8);

function baseUrl(req) {
  return process.env.PUBLIC_BASE_URL || `${req.protocol}://${req.get('host')}`;
}

function toPublic(survey, req) {
  return {
    id: survey._id.toString(),
    title: survey.title,
    description: survey.description,
    allow_anonymous: survey.allow_anonymous,
    allow_multiple: survey.allow_multiple,
    submit_message: survey.submit_message,
    status: survey.status,
    deadline: survey.deadline,
    share_code: survey.share_code,
    share_url: `${baseUrl(req)}/fill.html?code=${survey.share_code}`,
    question_count: survey.question_count,
    created_at: survey.created_at,
    updated_at: survey.updated_at,
    published_at: survey.published_at,
    closed_at: survey.closed_at,
  };
}

/** 取当前用户拥有的问卷，不存在返回 404，别人的返回 403 */
async function loadOwnedSurvey(req) {
  const survey = await Survey.findById(req.params.id);
  if (!survey) throw notFound('问卷不存在');
  if (String(survey.owner_id) !== String(req.user.id)) throw forbidden('只能操作自己创建的问卷');
  return survey;
}

async function generateUniqueCode() {
  for (let i = 0; i < 5; i += 1) {
    const code = newCode();
    const exists = await Survey.findOne({ share_code: code }).lean();
    if (!exists) return code;
  }
  throw new Error('生成问卷短码失败，请重试');
}

function normalizeSubmitMessage(v) {
  if (v === null || v === undefined) return undefined; // 未传时用模型默认值
  const s = String(v).trim();
  if (!s) return '感谢你的填写！';
  return s.slice(0, 200);
}

// 创建问卷
router.post(
  '/',
  requireAuth,
  asyncHandler(async (req, res) => {
    const { title, description = '', allow_anonymous = false, allow_multiple = true, deadline = null, submit_message = null } =
      req.body || {};
    if (typeof title !== 'string' || !title.trim()) throw badRequest('问卷标题不能为空');
    if (title.trim().length > 120) throw badRequest('问卷标题不能超过 120 个字符');
    if (deadline !== null && Number.isNaN(new Date(deadline).getTime())) {
      throw badRequest('截止时间格式不正确');
    }

    const survey = await Survey.create({
      owner_id: req.user.id,
      title: title.trim(),
      description: String(description || '').slice(0, 2000),
      allow_anonymous: Boolean(allow_anonymous),
      allow_multiple: Boolean(allow_multiple),
      submit_message: normalizeSubmitMessage(submit_message),
      deadline: deadline ? new Date(deadline) : null,
      share_code: await generateUniqueCode(),
    });

    res.status(201).json({ survey: toPublic(survey, req) });
  })
);

// 我的问卷列表
router.get(
  '/',
  requireAuth,
  asyncHandler(async (req, res) => {
    const page = Math.max(1, parseInt(req.query.page, 10) || 1);
    const size = Math.min(50, Math.max(1, parseInt(req.query.size, 10) || 20));
    const filter = { owner_id: req.user.id };
    if (req.query.status) filter.status = req.query.status;

    const [items, total] = await Promise.all([
      Survey.find(filter).sort({ created_at: -1 }).skip((page - 1) * size).limit(size),
      Survey.countDocuments(filter),
    ]);

    // 列表页只额外取每个问卷的答卷数，用一次聚合代替 N 次 count
    const ids = items.map((s) => s._id);
    const counts = ids.length
      ? await Response.aggregate([
          { $match: { survey_id: { $in: ids } } },
          { $group: { _id: '$survey_id', n: { $sum: 1 } } },
        ])
      : [];
    const countMap = new Map(counts.map((c) => [String(c._id), c.n]));

    res.json({
      total,
      page,
      size,
      items: items.map((s) => ({ ...toPublic(s, req), response_count: countMap.get(String(s._id)) || 0 })),
    });
  })
);

// 问卷详情（含题目，仅创建者可见）
router.get(
  '/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    res.json({
      survey: toPublic(survey, req),
      questions: questions.map((q) => ({ ...q.toObject(), id: q._id.toString(), _id: undefined })),
    });
  })
);

// 修改问卷元信息：草稿可改全部；已发布只允许改截止时间；已关闭不可改
router.patch(
  '/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    if (survey.status === 'closed') throw conflict('问卷已关闭，无法修改');

    const body = req.body || {};
    const editableInDraft = ['title', 'description', 'allow_anonymous', 'allow_multiple'];
    const touchedDraftFields = editableInDraft.filter((k) => k in body);
    if (survey.status === 'published' && touchedDraftFields.length) {
      throw conflict('问卷已发布，只能修改截止时间与提交提示语；如需改题目请先关闭问卷');
    }

    if ('title' in body) {
      if (typeof body.title !== 'string' || !body.title.trim()) throw badRequest('问卷标题不能为空');
      survey.title = body.title.trim();
    }
    if ('description' in body) survey.description = String(body.description || '').slice(0, 2000);
    if ('allow_anonymous' in body) survey.allow_anonymous = Boolean(body.allow_anonymous);
    if ('allow_multiple' in body) survey.allow_multiple = Boolean(body.allow_multiple);
    // 提示语不影响答卷解释，发布后仍允许修改（对标腾讯文档收集表）
    if ('submit_message' in body) survey.submit_message = normalizeSubmitMessage(body.submit_message);
    if ('deadline' in body) {
      if (body.deadline === null) survey.deadline = null;
      else {
        const d = new Date(body.deadline);
        if (Number.isNaN(d.getTime())) throw badRequest('截止时间格式不正确');
        survey.deadline = d;
      }
    }

    survey.updated_at = new Date();
    await survey.save();
    res.json({ survey: toPublic(survey, req) });
  })
);

// 发布
router.post(
  '/:id/publish',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    if (survey.status === 'published') throw conflict('问卷已经是发布状态');
    if (survey.status === 'closed') throw conflict('问卷已关闭，不能重新发布');
    if (survey.question_count < 1) throw conflict('至少需要 1 道题才能发布');

    survey.status = 'published';
    survey.published_at = new Date();
    survey.updated_at = new Date();
    await survey.save();
    res.json({ survey: toPublic(survey, req) });
  })
);

// 关闭
router.post(
  '/:id/close',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    if (survey.status === 'closed') throw conflict('问卷已经关闭');
    survey.status = 'closed';
    survey.closed_at = new Date();
    survey.updated_at = new Date();
    await survey.save();
    res.json({ survey: toPublic(survey, req) });
  })
);

// 删除（仅草稿，且必须没有答卷）
router.delete(
  '/:id',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    if (survey.status !== 'draft') throw conflict('只有草稿状态的问卷可以删除');
    const responses = await Response.countDocuments({ survey_id: survey._id });
    if (responses > 0) throw conflict('该问卷已有答卷，不能删除');

    await Question.deleteMany({ survey_id: survey._id });
    await survey.deleteOne();
    res.json({ deleted: true });
  })
);

// 复制问卷（对标腾讯文档收集表「生成副本」）：复制元信息与全部题目，跳转目标按新旧题目 id 映射重写
router.post(
  '/:id/duplicate',
  requireAuth,
  asyncHandler(async (req, res) => {
    const src = await loadOwnedSurvey(req);
    const srcQuestions = await Question.find({ survey_id: src._id }).sort({ order: 1 });

    const copy = await Survey.create({
      owner_id: req.user.id,
      title: `${src.title}（副本）`.slice(0, 120),
      description: src.description,
      allow_anonymous: src.allow_anonymous,
      allow_multiple: src.allow_multiple,
      submit_message: src.submit_message,
      deadline: null, // 副本不继承截止时间，由创建者重新评估
      share_code: await generateUniqueCode(),
      question_count: srcQuestions.length,
    });

    // 先建全部题目拿到新 id，再按 oldId -> newId 重写跳转目标，避免规则指向原问卷的题目
    const idMap = new Map();
    const created = [];
    for (const q of srcQuestions) {
      const doc = await Question.create({
        survey_id: copy._id,
        order: q.order,
        type: q.type,
        title: q.title,
        required: q.required,
        options: q.options,
        constraints: q.constraints,
      });
      idMap.set(String(q._id), doc._id);
      created.push(doc);
    }
    for (let i = 0; i < created.length; i += 1) {
      const srcQ = srcQuestions[i];
      const rules = (srcQ.jump_rules || [])
        .map((r) => ({ ...r.toObject(), target_question_id: idMap.get(String(r.target_question_id)) || null }))
        .filter((r) => r.to === 'end' || r.target_question_id);
      if (rules.length) {
        created[i].jump_rules = rules;
        await created[i].save();
      }
    }

    res.status(201).json({ survey: toPublic(copy, req), copied_questions: created.length });
  })
);

// 生成填写页二维码：服务端渲染成 PNG data URL，前端直接 <img> 展示即可
router.get(
  '/:id/qrcode',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwnedSurvey(req);
    const fillUrl = `${baseUrl(req)}/fill.html?code=${survey.share_code}`;
    let qrDataUrl;
    try {
      qrDataUrl = await QRCode.toDataURL(fillUrl, { width: 280, margin: 2, errorCorrectionLevel: 'M' });
    } catch (err) {
      throw badRequest('二维码生成失败：' + err.message);
    }
    res.json({ survey_id: survey._id.toString(), fill_url: fillUrl, qr_data_url: qrDataUrl });
  })
);

module.exports = { router, loadOwnedSurvey, toPublic, baseUrl };
