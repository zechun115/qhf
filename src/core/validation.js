(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.QBValidation = factory();
  }
})(
  typeof self !== 'undefined' ? self : this,
  function () {
    'use strict';

    /**
     * 校验引擎（前后端共用）
     *
     * 同一份文件既被 Node 的 require 加载做服务端权威校验，
     * 也被浏览器 <script> 加载做提交前的前端校验，
     * 目的：规则只有一份实现，前端提示与后端判定永远不会不一致。
     *
     * 规则来自数据库（type / constraints / required），代码只解释规则，不写死任何具体题目。
     */

    /** 按 Unicode 码点计长度，避免 emoji / 生僻字被当成 2 个字符 */
    function charLength(str) {
      return Array.from(String(str)).length;
    }

    function isBlank(v) {
      return v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
    }

    /** 规范化原始答案，返回 null 表示未作答 */
    function normalizeAnswer(question, raw) {
      if (!raw) return null;

      switch (question.type) {
        case 'single':
        case 'multiple':
        case 'dropdown':
        case 'rating': {
          const keys = Array.isArray(raw.option_keys)
            ? raw.option_keys.filter((k) => typeof k === 'string')
            : [];
          const unique = [...new Set(keys)];
          return unique.length ? { option_keys: unique } : null;
        }
        case 'text': {
          if (isBlank(raw.text)) return null;
          return { text: String(raw.text) };
        }
        case 'number': {
          if (isBlank(raw.number)) return null;
          const n = Number(raw.number);
          return Number.isFinite(n) ? { number: n } : { number: NaN };
        }
        case 'date': {
          if (isBlank(raw.date)) return null;
          return { date: String(raw.date).trim() };
        }
        default:
          return null;
      }
    }

    /** 校验单题答案 → {ok, errors[], value} */
    function validateAnswer(question, raw) {
      const errors = [];
      const value = normalizeAnswer(question, raw);
      const c = question.constraints || {};
      const optionKeys = (question.options || []).map((o) => o.key);

      if (!value) {
        if (question.required) errors.push('本题为必答题');
        return { ok: errors.length === 0, errors, value: null };
      }

      if (question.type === 'single' || question.type === 'dropdown' || question.type === 'rating') {
        const typeLabel = question.type === 'single' ? '单选题' : question.type === 'rating' ? '评分题' : '下拉选择题';
        if (value.option_keys.length !== 1) {
          errors.push(typeLabel + '必须且只能选择 1 个选项');
        } else if (!optionKeys.includes(value.option_keys[0])) {
          errors.push('选项 ' + value.option_keys[0] + ' 不存在于本题');
        }
      }

      if (question.type === 'multiple') {
        const chosen = value.option_keys;
        const invalid = chosen.filter((k) => !optionKeys.includes(k));
        if (invalid.length) errors.push('选项 ' + invalid.join(', ') + ' 不存在于本题');
        const min = c.min_choice === null || c.min_choice === undefined ? 0 : c.min_choice;
        const max = c.max_choice === null || c.max_choice === undefined ? Infinity : c.max_choice;
        if (chosen.length < min) errors.push('多选题至少选择 ' + min + ' 项，当前 ' + chosen.length + ' 项');
        if (chosen.length > max) errors.push('多选题最多选择 ' + max + ' 项，当前 ' + chosen.length + ' 项');
      }

      if (question.type === 'text') {
        const len = charLength(value.text);
        if (c.min_length !== null && c.min_length !== undefined && len < c.min_length) {
          errors.push('文本长度不能少于 ' + c.min_length + ' 个字符，当前 ' + len + ' 个');
        }
        if (c.max_length !== null && c.max_length !== undefined && len > c.max_length) {
          errors.push('文本长度不能超过 ' + c.max_length + ' 个字符，当前 ' + len + ' 个');
        }
      }

      if (question.type === 'number') {
        const n = value.number;
        if (!Number.isFinite(n)) {
          errors.push('请填写合法的数字');
        } else {
          if (c.integer === true && !Number.isInteger(n)) errors.push('本题要求填写整数');
          if (c.min !== null && c.min !== undefined && n < c.min) {
            errors.push('数值不能小于 ' + c.min + '，当前 ' + n);
          }
          if (c.max !== null && c.max !== undefined && n > c.max) {
            errors.push('数值不能大于 ' + c.max + '，当前 ' + n);
          }
        }
      }

      if (question.type === 'date') {
        // 只接受 YYYY-MM-DD 且必须是真实存在的日期（2024-02-31 不合法）
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.date);
        const valid =
          m &&
          (() => {
            const d = new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00Z`);
            return (
              !Number.isNaN(d.getTime()) &&
              d.getUTCFullYear() === Number(m[1]) &&
              d.getUTCMonth() + 1 === Number(m[2]) &&
              d.getUTCDate() === Number(m[3])
            );
          })();
        if (!valid) errors.push('请填写合法的日期（格式：YYYY-MM-DD）');
      }

      return { ok: errors.length === 0, errors, value };
    }

    return { normalizeAnswer, validateAnswer, charLength };
  }
);
