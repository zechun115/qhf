'use strict';
const express = require('express');
const mongoose = require('mongoose');
const Survey = require('../models/Survey');
const Question = require('../models/Question');
const Response = require('../models/Response');
const { asyncHandler, notFound, forbidden, badRequest } = require('../utils/errors');
const { requireAuth } = require('../middleware/auth');
const { charLength } = require('../core/validation');

const router = express.Router();

const round2 = (n) => Math.round(n * 100) / 100;

/**
 * 用一条聚合管道把「每道题被回答了多少次、每题的原始答案」一次性取出来。
 * 之所以在数据库里 $unwind + $group 而不是把整份答卷拉到内存里循环：
 * 答卷量上来后，聚合在服务端完成能显著减少网络传输与 JS 侧内存占用。
 */
async function aggregateByQuestion(surveyId, questionId) {
  const match = { survey_id: surveyId };
  const pipeline = [{ $match: match }];
  if (questionId) pipeline.push({ $match: { 'answers.question_id': questionId } });
  pipeline.push(
    { $unwind: '$answers' },
    ...(questionId ? [{ $match: { 'answers.question_id': questionId } }] : []),
    {
      $group: {
        _id: '$answers.question_id',
        answered: { $sum: 1 },
        option_sets: { $push: '$answers.option_keys' },
        texts: { $push: '$answers.text' },
        numbers: { $push: '$answers.number' },
        dates: { $push: '$answers.date' },
      },
    }
  );
  return Response.aggregate(pipeline);
}

function statForQuestion(question, group, total) {
  const base = {
    question_id: String(question._id),
    order: question.order,
    type: question.type,
    title: question.title,
    required: question.required,
    answered: group ? group.answered : 0,
    response_rate: total ? round2(((group ? group.answered : 0) / total) * 100) : 0,
  };

  // 单选 / 多选 / 下拉 / 评分（评分题的 1~5 星选项由系统自动生成，统计口径与单选一致）
  if (['single', 'multiple', 'dropdown', 'rating'].includes(question.type)) {
    const counts = new Map(question.options.map((o) => [o.key, 0]));
    const sets = group ? group.option_sets : [];
    sets.forEach((keys) => (keys || []).forEach((k) => counts.set(k, (counts.get(k) || 0) + 1)));
    return {
      ...base,
      options: question.options.map((o) => ({
        key: o.key,
        label: o.label,
        count: counts.get(o.key) || 0,
        percent: group && group.answered ? round2(((counts.get(o.key) || 0) / group.answered) * 100) : 0,
      })),
    };
  }

  if (question.type === 'text') {
    const texts = (group ? group.texts : []).filter((t) => typeof t === 'string');
    const totalChars = texts.reduce((sum, t) => sum + charLength(t), 0);
    return {
      ...base,
      text_count: texts.length,
      avg_length: texts.length ? round2(totalChars / texts.length) : 0,
      texts: texts.slice(0, 100), // 只回前 100 条，避免响应体过大
      texts_truncated: texts.length > 100,
    };
  }

  if (question.type === 'number') {
    const nums = (group ? group.numbers : []).filter((n) => typeof n === 'number' && Number.isFinite(n));
    const sum = nums.reduce((a, b) => a + b, 0);
    return {
      ...base,
      number_count: nums.length,
      avg: nums.length ? round2(sum / nums.length) : 0,
      min: nums.length ? Math.min(...nums) : null,
      max: nums.length ? Math.max(...nums) : null,
      values: nums.slice(0, 100),
      values_truncated: nums.length > 100,
    };
  }

  if (question.type === 'date') {
    const dates = (group ? group.dates : []).filter((d) => typeof d === 'string' && d);
    return {
      ...base,
      date_count: dates.length,
      dates: [...new Set(dates)].sort().reverse().slice(0, 50),
      dates_truncated: new Set(dates).size > 50,
    };
  }

  return base;
}

async function loadOwned(req) {
  if (!mongoose.isValidObjectId(req.params.id)) throw badRequest('问卷 id 格式不正确');
  const survey = await Survey.findById(req.params.id);
  if (!survey) throw notFound('问卷不存在');
  if (String(survey.owner_id) !== String(req.user.id)) throw forbidden('只能查看自己问卷的统计');
  return survey;
}

// 整卷统计
router.get(
  '/:id/stats',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwned(req);
    const [questions, total, groups] = await Promise.all([
      Question.find({ survey_id: survey._id }).sort({ order: 1 }),
      Response.countDocuments({ survey_id: survey._id }),
      aggregateByQuestion(survey._id),
    ]);

    const groupMap = new Map(groups.map((g) => [String(g._id), g]));
    const anonymousCount = await Response.countDocuments({ survey_id: survey._id, anonymous: true });

    res.json({
      survey: { id: String(survey._id), title: survey.title, status: survey.status },
      total_responses: total,
      anonymous_responses: anonymousCount,
      logged_in_responses: total - anonymousCount,
      questions: questions.map((q) => statForQuestion(q, groupMap.get(String(q._id)), total)),
    });
  })
);

// 单题统计
router.get(
  '/:id/stats/questions/:questionId',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwned(req);
    if (!mongoose.isValidObjectId(req.params.questionId)) throw badRequest('题目 id 格式不正确');
    const question = await Question.findOne({ _id: req.params.questionId, survey_id: survey._id });
    if (!question) throw notFound('题目不存在');

    const [total, groups] = await Promise.all([
      Response.countDocuments({ survey_id: survey._id }),
      aggregateByQuestion(survey._id, question._id),
    ]);

    res.json({ total_responses: total, question: statForQuestion(question, groups[0], total) });
  })
);

// 答卷明细（按题目 id 还原成可读文本），便于「查看所有填写内容」
router.get(
  '/:id/responses',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwned(req);
    const page = Math.max(1, parseInt(req.query.page, 10) || 1);
    const size = Math.min(100, Math.max(1, parseInt(req.query.size, 10) || 20));

    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    const qMap = new Map(questions.map((q) => [String(q._id), q]));

    const [items, total] = await Promise.all([
      Response.find({ survey_id: survey._id }).sort({ submitted_at: -1 }).skip((page - 1) * size).limit(size),
      Response.countDocuments({ survey_id: survey._id }),
    ]);

    res.json({
      total,
      page,
      size,
      items: items.map((r) => ({
        id: String(r._id),
        anonymous: r.anonymous,
        respondent_id: r.respondent_id ? String(r.respondent_id) : null,
        submitted_at: r.submitted_at,
        answers: [...r.answers]
          .sort((a, b) => a.question_order - b.question_order)
          .map((a) => {
            const q = qMap.get(String(a.question_id));
            let display = '';
            if (q && ['single', 'multiple', 'dropdown', 'rating'].includes(q.type)) {
              const labels = a.option_keys.map((k) => {
                const opt = q.options.find((o) => o.key === k);
                return opt ? `${opt.key}. ${opt.label}` : k;
              });
              display = labels.join('；');
            } else if (q && q.type === 'text') {
              display = a.text || '';
            } else if (q && q.type === 'number') {
              display = a.number === null || a.number === undefined ? '' : String(a.number);
            } else if (q && q.type === 'date') {
              display = a.date || '';
            }
            return {
              question_id: String(a.question_id),
              question_order: a.question_order,
              question_title: q ? q.title : '(题目已删除)',
              type: q ? q.type : 'unknown',
              display,
            };
          }),
      })),
    });
  })
);

// 答卷导出 CSV（对标腾讯文档收集表「导出 Excel」）：UTF-8 BOM 保证 Excel 直接打开不乱码
router.get(
  '/:id/responses/export',
  requireAuth,
  asyncHandler(async (req, res) => {
    const survey = await loadOwned(req);
    const questions = await Question.find({ survey_id: survey._id }).sort({ order: 1 });
    const qMap = new Map(questions.map((q) => [String(q._id), q]));
    const responses = await Response.find({ survey_id: survey._id }).sort({ submitted_at: 1 }).lean();

    const escape = (v) => {
      const s = v === null || v === undefined ? '' : String(v);
      return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const fmtTime = (d) => new Date(d).toISOString().replace('T', ' ').slice(0, 19);

    const header = ['提交时间', '匿名', ...questions.map((q) => `Q${q.order} ${q.title}`)];
    const lines = [header.map(escape).join(',')];
    for (const r of responses) {
      const byQ = new Map((r.answers || []).map((a) => [String(a.question_id), a]));
      const row = [
        fmtTime(r.submitted_at),
        r.anonymous ? '是' : '否',
        ...questions.map((q) => {
          const a = byQ.get(String(q._id));
          if (!a) return '';
          if (['single', 'multiple', 'dropdown', 'rating'].includes(q.type)) {
            return (a.option_keys || [])
              .map((k) => {
                const opt = (q.options || []).find((o) => o.key === k);
                return opt ? opt.label : k;
              })
              .join('；');
          }
          if (q.type === 'text') return a.text || '';
          if (q.type === 'number') return a.number === null || a.number === undefined ? '' : a.number;
          if (q.type === 'date') return a.date || '';
          return '';
        }),
      ];
      lines.push(row.map(escape).join(','));
    }

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="responses-${survey.share_code}.csv"`);
    res.send('\ufeff' + lines.join('\r\n'));
  })
);

module.exports = router;
