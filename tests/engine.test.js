'use strict';
/**
 * 规则引擎单元测试（不依赖数据库）
 * 对应测试用例表：T10~T17 的核心逻辑部分
 */
const test = require('node:test');
const assert = require('node:assert');
const { computePath, ruleMatches } = require('../src/core/jump');
const { validateAnswer, charLength } = require('../src/core/validation');

function q(id, order, extra = {}) {
  return {
    _id: id,
    order,
    type: 'single',
    title: `第${order}题`,
    required: false,
    options: [
      { key: 'A', label: '选项A' },
      { key: 'B', label: '选项B' },
    ],
    constraints: {},
    jump_rules: [],
    ...extra,
  };
}

const rule = (when, target, priority = 0, to = 'question') => ({
  when,
  to,
  target_question_id: target,
  priority,
});

test('T10-1 无跳转规则时按顺序走完全部题目', () => {
  const qs = [q('1', 1), q('2', 2), q('3', 3)];
  const { path, endedEarly } = computePath(qs, new Map());
  assert.deepStrictEqual(path.map((x) => x.order), [1, 2, 3]);
  assert.strictEqual(endedEarly, false);
});

test('T10-2 单选命中规则后跳过中间的题目', () => {
  const qs = [
    q('1', 1, { jump_rules: [rule({ op: 'option_selected', option_key: 'A' }, '4')] }),
    q('2', 2),
    q('3', 3),
    q('4', 4),
    q('5', 5),
  ];
  const answers = new Map([['1', { option_keys: ['A'] }]]);
  const { path } = computePath(qs, answers);
  assert.deepStrictEqual(path.map((x) => x.order), [1, 4, 5]);
});

test('T10-3 未命中规则时不受影响，继续下一题', () => {
  const qs = [q('1', 1, { jump_rules: [rule({ op: 'option_selected', option_key: 'A' }, '4')] }), q('2', 2), q('3', 3), q('4', 4)];
  const answers = new Map([['1', { option_keys: ['B'] }]]);
  const { path } = computePath(qs, answers);
  assert.deepStrictEqual(path.map((x) => x.order), [1, 2, 3, 4]);
});

test('T10-4 多条规则时按 priority 命中第一条', () => {
  const qs = [
    q('1', 1, {
      jump_rules: [
        rule({ op: 'option_selected', option_key: 'A' }, '4', 5),
        rule({ op: 'option_selected', option_key: 'A' }, '3', 1),
      ],
    }),
    q('2', 2),
    q('3', 3),
    q('4', 4),
  ];
  const { path } = computePath(qs, new Map([['1', { option_keys: ['A'] }]]));
  assert.deepStrictEqual(path.map((x) => x.order), [1, 3, 4]);
});

test('T11-1 多选题按选项跳转', () => {
  const qs = [
    q('1', 1, {
      type: 'multiple',
      jump_rules: [rule({ op: 'option_selected', option_key: 'B' }, '4')],
    }),
    q('2', 2),
    q('3', 3),
    q('4', 4),
  ];
  const { path } = computePath(qs, new Map([['1', { option_keys: ['A', 'B'] }]]));
  assert.deepStrictEqual(path.map((x) => x.order), [1, 4]);
});

test('T12-1 数字区间命中跳转，区间外不跳', () => {
  const make = () => [
    q('1', 1, {
      type: 'number',
      jump_rules: [rule({ op: 'number_gte', value: 18 }, '3')],
    }),
    q('2', 2),
    q('3', 3),
  ];
  assert.deepStrictEqual(
    computePath(make(), new Map([['1', { number: 20 }]])).path.map((x) => x.order),
    [1, 3]
  );
  assert.deepStrictEqual(
    computePath(make(), new Map([['1', { number: 10 }]])).path.map((x) => x.order),
    [1, 2, 3]
  );
});

test('T13-1 跳转到「结束问卷」时提前终止', () => {
  const qs = [
    q('1', 1, { jump_rules: [{ when: { op: 'option_selected', option_key: 'B' }, to: 'end', priority: 0 }] }),
    q('2', 2),
    q('3', 3),
  ];
  const { path, endedEarly } = computePath(qs, new Map([['1', { option_keys: ['B'] }]]));
  assert.deepStrictEqual(path.map((x) => x.order), [1]);
  assert.strictEqual(endedEarly, true);
});

test('T13-2 指向前面题目的非法规则被忽略，不会死循环', () => {
  const qs = [
    q('1', 1, { jump_rules: [rule({ op: 'option_selected', option_key: 'A' }, '1')] }),
    q('2', 2, { jump_rules: [rule({ op: 'option_selected', option_key: 'A' }, '1')] }),
  ];
  const answers = new Map([
    ['1', { option_keys: ['A'] }],
    ['2', { option_keys: ['A'] }],
  ]);
  const { path } = computePath(qs, answers);
  assert.deepStrictEqual(path.map((x) => x.order), [1, 2]);
});

test('T14-1 必答题未作答时报错', () => {
  const res = validateAnswer(q('1', 1, { required: true }), null);
  assert.strictEqual(res.ok, false);
  assert.match(res.errors[0], /必答/);
});

test('T14-2 非必答题未作答时通过', () => {
  const res = validateAnswer(q('1', 1, { required: false }), null);
  assert.strictEqual(res.ok, true);
});

test('T15-1 多选题选择数量低于下限时报错', () => {
  const question = q('1', 1, {
    type: 'multiple',
    options: ['A', 'B', 'C', 'D'].map((k) => ({ key: k, label: k })),
    constraints: { min_choice: 2, max_choice: 3 },
  });
  const res = validateAnswer(question, { option_keys: ['A'] });
  assert.strictEqual(res.ok, false);
  assert.match(res.errors.join(), /至少选择 2 项/);
});

test('T15-2 多选题选择数量高于上限时报错', () => {
  const question = q('1', 1, {
    type: 'multiple',
    options: ['A', 'B', 'C', 'D'].map((k) => ({ key: k, label: k })),
    constraints: { min_choice: 2, max_choice: 3 },
  });
  const res = validateAnswer(question, { option_keys: ['A', 'B', 'C', 'D'] });
  assert.strictEqual(res.ok, false);
  assert.match(res.errors.join(), /最多选择 3 项/);
});

test('T15-3 多选题选择数量合法时通过', () => {
  const question = q('1', 1, {
    type: 'multiple',
    options: ['A', 'B', 'C', 'D'].map((k) => ({ key: k, label: k })),
    constraints: { min_choice: 2, max_choice: 3 },
  });
  assert.strictEqual(validateAnswer(question, { option_keys: ['A', 'B'] }).ok, true);
});

test('T16-1 文本长度按码点计算，emoji 记 1 个字符', () => {
  assert.strictEqual(charLength('你好😀'), 3);
  const question = q('1', 1, { type: 'text', constraints: { min_length: 2, max_length: 3 } });
  assert.strictEqual(validateAnswer(question, { text: '你好😀' }).ok, true);
  const tooShort = validateAnswer(question, { text: '好' });
  assert.strictEqual(tooShort.ok, false);
  assert.match(tooShort.errors.join(), /不能少于 2/);
});

test('T17-1 数字题整数校验', () => {
  const question = q('1', 1, { type: 'number', constraints: { min: 0, max: 120, integer: true } });
  assert.strictEqual(validateAnswer(question, { number: 25 }).ok, true);
  const decimal = validateAnswer(question, { number: 25.5 });
  assert.strictEqual(decimal.ok, false);
  assert.match(decimal.errors.join(), /整数/);
});

test('T17-2 数字题范围校验', () => {
  const question = q('1', 1, { type: 'number', constraints: { min: 0, max: 120, integer: true } });
  const tooBig = validateAnswer(question, { number: 200 });
  assert.strictEqual(tooBig.ok, false);
  assert.match(tooBig.errors.join(), /不能大于 120/);
  const tooSmall = validateAnswer(question, { number: -1 });
  assert.strictEqual(tooSmall.ok, false);
  assert.match(tooSmall.errors.join(), /不能小于 0/);
});

test('T18-1 提交不存在的选项被拒绝', () => {
  const res = validateAnswer(q('1', 1), { option_keys: ['Z'] });
  assert.strictEqual(res.ok, false);
  assert.match(res.errors.join(), /不存在于本题/);
});

test('T18-2 单题提交多个选项被拒绝', () => {
  const res = validateAnswer(q('1', 1), { option_keys: ['A', 'B'] });
  assert.strictEqual(res.ok, false);
  assert.match(res.errors.join(), /只能选择 1 个/);
});

test('ruleMatches 覆盖各类条件运算符', () => {
  assert.strictEqual(ruleMatches({ when: { op: 'number_lt', value: 5 } }, { number: 4 }), true);
  assert.strictEqual(ruleMatches({ when: { op: 'number_between', value: 1, value2: 3 } }, { number: 3 }), true);
  assert.strictEqual(ruleMatches({ when: { op: 'text_contains', text: '学生' } }, { text: '我是学生' }), true);
  assert.strictEqual(ruleMatches({ when: { op: 'text_contains', text: '教师' } }, { text: '我是学生' }), false);
  assert.strictEqual(ruleMatches({ when: { op: 'option_selected', option_key: 'A' } }, null), false);
});
