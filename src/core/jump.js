(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.QBJump = factory();
  }
})(
  typeof self !== 'undefined' ? self : this,
  function () {
    'use strict';

    /**
     * 跳转引擎（前后端共用）
     *
     * 1) 规则全部来自数据库里的 question.jump_rules，「第 1 题选 A 就跳第 5 题」这种逻辑不写在代码里。
     * 2) 前端用它做即时跳转（体验），后端在提交时用同一份函数重算路径（权威）。
     *    这样既能让用户边答边跳，又不可能通过改请求绕过必答题。
     * 3) 只允许向后跳 + 步数上限，两道闸门防死循环。
     */

    function ruleMatches(rule, answer) {
      if (!answer) return false;
      const w = (rule && rule.when) || {};

      switch (w.op) {
        case 'option_selected':
          return Array.isArray(answer.option_keys) && answer.option_keys.includes(w.option_key);
        case 'number_eq':
          return typeof answer.number === 'number' && answer.number === w.value;
        case 'number_gte':
          return typeof answer.number === 'number' && answer.number >= w.value;
        case 'number_lt':
          return typeof answer.number === 'number' && answer.number < w.value;
        case 'number_between':
          return (
            typeof answer.number === 'number' &&
            answer.number >= Math.min(w.value, w.value2) &&
            answer.number <= Math.max(w.value, w.value2)
          );
        case 'text_contains':
          return typeof answer.text === 'string' && answer.text.includes(w.text);
        default:
          return false;
      }
    }

    /**
     * 计算完整作答路径。
     * @param {Array} questions 题目数组（按 order 升序传入，函数内部仍会再排一次）
     * @param {object|Map} rawAnswers 题目 id -> 原始答案
     * @returns {{path: Array, endedEarly: boolean, lastQuestionId: string|null}}
     */
    /** 题目在不同场景下的主键字段不同：服务端是 Mongoose 文档(_id)，浏览器里是接口返回的 id */
    function qid(q) {
      return String(q._id || q.id);
    }

    function computePath(questions, rawAnswers) {
      const sorted = [...questions].sort((a, b) => a.order - b.order);
      const path = [];
      if (!sorted.length) return { path, endedEarly: false, lastQuestionId: null };

      const answers =
        rawAnswers instanceof Map ? rawAnswers : new Map(Object.entries(rawAnswers || {}));

      const byId = new Map(sorted.map((q) => [qid(q), q]));
      const indexOf = new Map(sorted.map((q, i) => [qid(q), i]));

      let cursor = 0;
      let guard = sorted.length * 2 + 5;
      let endedEarly = false;

      while (cursor < sorted.length && guard-- > 0) {
        const q = sorted[cursor];
        path.push(q);

        const answer = answers.get(qid(q)) || null;
        const rules = [...(q.jump_rules || [])]
          .map((r, i) => ({ r, i }))
          .sort((a, b) => (a.r.priority || 0) - (b.r.priority || 0) || a.i - b.i);

        const hit = rules.find((item) => ruleMatches(item.r, answer));

        if (hit) {
          if (hit.r.to === 'end') {
            endedEarly = true;
            break;
          }
          const target = byId.get(String(hit.r.target_question_id));
          if (target && indexOf.get(qid(target)) > cursor) {
            cursor = indexOf.get(qid(target));
            continue;
          }
        }
        cursor += 1;
      }

      return {
        path,
        endedEarly,
        lastQuestionId: path.length ? qid(path[path.length - 1]) : null,
      };
    }

    return { computePath, ruleMatches, qid };
  }
);
