'use strict';
const { badRequest } = require('../utils/errors');

/**
 * 题目结构规范化 + 题目级规则校验。
 * 这里处理「题目本身是否合法」，不处理「用户答案是否合法」（那是 validation.js 的职责）。
 */

const TYPES = ['single', 'multiple', 'text', 'number', 'dropdown', 'rating', 'date'];
// 可以按「选项」出跳转条件 / 需要选项的题型（rating 的 1~5 星选项由系统自动生成）
const OPTION_TYPES = ['single', 'multiple', 'dropdown', 'rating'];
const RATING_STARS = ['1', '2', '3', '4', '5'];
const AUTO_KEYS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

function normalizeOptions(rawOptions) {
  if (!Array.isArray(rawOptions)) throw badRequest('选项必须是数组');
  if (rawOptions.length < 2) throw badRequest('选项类题型至少需要 2 个选项');
  if (rawOptions.length > 50) throw badRequest('单题选项数量不能超过 50 个');

  const seen = new Set();
  return rawOptions.map((opt, i) => {
    const label = typeof opt === 'string' ? opt.trim() : String((opt && opt.label) || '').trim();
    if (!label) throw badRequest(`第 ${i + 1} 个选项的内容不能为空`);
    let key = (opt && opt.key ? String(opt.key).trim() : '') || AUTO_KEYS[i] || `O${i + 1}`;
    if (seen.has(key)) throw badRequest(`选项标识 ${key} 重复`);
    seen.add(key);
    return { key, label };
  });
}

/** 评分题固定为 1~5 星选项，与腾讯文档收集表的「分值量表」一致 */
function ratingOptions() {
  return RATING_STARS.map((n) => ({ key: n, label: `${n} 星` }));
}

function pickNumber(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  if (!Number.isFinite(n)) throw badRequest('数值约束必须是合法数字');
  return n;
}

function normalizeConstraints(type, raw) {
  const c = raw || {};
  const out = {
    min_choice: null,
    max_choice: null,
    min_length: null,
    max_length: null,
    min: null,
    max: null,
    integer: null,
  };

  if (type === 'multiple') {
    out.min_choice = pickNumber(c.min_choice);
    out.max_choice = pickNumber(c.max_choice);
    if (out.min_choice !== null && out.min_choice < 0) throw badRequest('最少选择数量不能为负数');
    if (out.max_choice !== null && out.max_choice < 1) throw badRequest('最多选择数量至少为 1');
    if (out.min_choice !== null && out.max_choice !== null && out.min_choice > out.max_choice) {
      throw badRequest('最少选择数量不能大于最多选择数量');
    }
  }

  if (type === 'text') {
    out.min_length = pickNumber(c.min_length);
    out.max_length = pickNumber(c.max_length);
    if (out.min_length !== null && out.min_length < 0) throw badRequest('最少字数不能为负数');
    if (out.min_length !== null && out.max_length !== null && out.min_length > out.max_length) {
      throw badRequest('最少字数不能大于最多字数');
    }
  }

  if (type === 'number') {
    out.min = pickNumber(c.min);
    out.max = pickNumber(c.max);
    out.integer = c.integer === true || c.integer === 'true' ? true : null;
    if (out.min !== null && out.max !== null && out.min > out.max) {
      throw badRequest('最小值不能大于最大值');
    }
  }

  return out;
}

/**
 * 校验跳转规则是否合法。
 * @param {Array} rules 待校验规则
 * @param {object} question 规则所属题目（含 order / options / type）
 * @param {Array} allQuestions 该问卷全部题目（用于把 target_question_id 换算成题号）
 */
function validateJumpRules(rules, question, allQuestions) {
  if (rules === undefined || rules === null) return [];
  if (!Array.isArray(rules)) throw badRequest('jump_rules 必须是数组');
  if (rules.length > 20) throw badRequest('单题跳转规则不能超过 20 条');

  const byId = new Map(allQuestions.map((q) => [String(q._id), q]));
  const optionKeys = (question.options || []).map((o) => o.key);

  return rules.map((r, i) => {
    const when = (r && r.when) || {};
    const to = r && r.to === 'end' ? 'end' : 'question';
    const priority = Number.isFinite(Number(r && r.priority)) ? Number(r.priority) : i;

    if (!OPTION_TYPES.includes(question.type) && when.op === 'option_selected') {
      throw badRequest('只有单选 / 多选 / 下拉 / 评分题可以按选项设置跳转');
    }
    if (question.type !== 'number' && ['number_eq', 'number_gte', 'number_lt', 'number_between'].includes(when.op)) {
      throw badRequest('只有数字填空题可以按数值设置跳转');
    }
    if (question.type !== 'text' && when.op === 'text_contains') {
      throw badRequest('只有文本填空题可以按关键字设置跳转');
    }

    if (when.op === 'option_selected' && !optionKeys.includes(when.option_key)) {
      throw badRequest(`跳转条件里的选项 ${when.option_key || '(空)'} 不在本题选项中`);
    }
    if (['number_eq', 'number_gte', 'number_lt'].includes(when.op)) {
      if (!Number.isFinite(Number(when.value))) throw badRequest('跳转条件的数值不合法');
    }
    if (when.op === 'number_between') {
      if (!Number.isFinite(Number(when.value)) || !Number.isFinite(Number(when.value2))) {
        throw badRequest('区间跳转条件的上下界都必须是数字');
      }
    }
    if (when.op === 'text_contains' && (typeof when.text !== 'string' || !when.text)) {
      throw badRequest('关键字跳转条件的内容不能为空');
    }

    let targetId = null;
    if (to === 'question') {
      targetId = r && r.target_question_id ? String(r.target_question_id) : null;
      if (!targetId) throw badRequest('跳转目标不能为空（或选择「结束问卷」）');
      const target = byId.get(targetId);
      if (!target) throw badRequest('跳转目标题目不存在或不属于本问卷');
      if (target.order <= question.order) {
        throw badRequest(`跳转目标必须是后面的题目（当前第 ${question.order} 题，目标第 ${target.order} 题）`);
      }
    }

    return {
      when: {
        op: when.op,
        option_key: when.op === 'option_selected' ? String(when.option_key) : null,
        value: ['number_eq', 'number_gte', 'number_lt', 'number_between'].includes(when.op)
          ? Number(when.value)
          : null,
        value2: when.op === 'number_between' ? Number(when.value2) : null,
        text: when.op === 'text_contains' ? String(when.text) : null,
      },
      to,
      target_question_id: targetId,
      priority,
    };
  });
}

/** 从请求体解析出一份完整题目数据（create 用） */
function buildQuestionPayload(body) {
  const b = body || {};
  const type = b.type;
  if (!TYPES.includes(type)) {
    throw badRequest('题型必须是 single / multiple / text / number / dropdown / rating / date 之一');
  }
  if (typeof b.title !== 'string' || !b.title.trim()) throw badRequest('题干不能为空');
  if (b.title.trim().length > 500) throw badRequest('题干不能超过 500 个字符');

  let options = [];
  if (type === 'rating') options = ratingOptions(); // 评分题选项固定，不接受自定义
  else if (OPTION_TYPES.includes(type)) options = normalizeOptions(b.options);

  return {
    type,
    title: b.title.trim(),
    required: Boolean(b.required),
    options,
    constraints: normalizeConstraints(type, b.constraints),
  };
}

module.exports = {
  TYPES,
  OPTION_TYPES,
  RATING_STARS,
  ratingOptions,
  normalizeOptions,
  normalizeConstraints,
  validateJumpRules,
  buildQuestionPayload,
};
