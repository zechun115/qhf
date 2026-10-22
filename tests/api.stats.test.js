'use strict';
/** 统计测试：T21~T27 */
const test = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register, createSurvey, addQuestion, publish, submit } = require('./helpers');

let ctx;
let token;
let otherToken;
let survey;
let q = {};

test.before(async () => {
  ctx = await setup('qb_test_stats');
  ({ token } = await register(ctx.api, 'statowner'));
  ({ token: otherToken } = await register(ctx.api, 'watcher'));

  survey = await createSurvey(ctx.api, token, { title: '统计验证问卷', allow_anonymous: true });

  q.gender = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '性别',
    required: true,
    options: [
      { key: 'A', label: '男' },
      { key: 'B', label: '女' },
      { key: 'C', label: '其他' },
    ],
  });
  q.fruits = await addQuestion(ctx.api, token, survey.id, {
    type: 'multiple',
    title: '喜欢的水果',
    options: [
      { key: 'A', label: '苹果' },
      { key: 'B', label: '香蕉' },
      { key: 'C', label: '西瓜' },
      { key: 'D', label: '葡萄' },
    ],
    constraints: { min_choice: 1, max_choice: 3 },
  });
  q.advice = await addQuestion(ctx.api, token, survey.id, {
    type: 'text',
    title: '建议',
  });
  q.age = await addQuestion(ctx.api, token, survey.id, {
    type: 'number',
    title: '年龄',
    constraints: { min: 0, max: 120, integer: true },
  });

  await publish(ctx.api, token, survey.id);

  const rows = [
    { a: 'A', fruits: ['A', 'B'], text: '很好', age: 20 },
    { a: 'B', fruits: ['A'], text: '一般', age: 30 },
    { a: 'A', fruits: ['B', 'C'], text: '不错', age: 40 },
  ];
  for (const r of rows) {
    const res = await submit(ctx.api, survey.share_code, [
      { question_id: q.gender.id, option_keys: [r.a] },
      { question_id: q.fruits.id, option_keys: r.fruits },
      { question_id: q.advice.id, text: r.text },
      { question_id: q.age.id, number: r.age },
    ]);
    assert.strictEqual(res.status, 201, JSON.stringify(res.body));
  }
});

test.after(async () => {
  await teardown();
});

test('T21 单选统计：各选项人数与占比正确', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/stats`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.total_responses, 3);
  assert.strictEqual(res.body.anonymous_responses, 3);

  const gender = res.body.questions.find((x) => x.title === '性别');
  const map = Object.fromEntries(gender.options.map((o) => [o.key, o.count]));
  assert.deepStrictEqual(map, { A: 2, B: 1, C: 0 });
  assert.strictEqual(gender.answered, 3);
  assert.strictEqual(gender.options.find((o) => o.key === 'A').percent, 66.67);
});

test('T22 多选统计：按选项被选择的次数计数', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/stats`).set('Authorization', `Bearer ${token}`);
  const fruits = res.body.questions.find((x) => x.title === '喜欢的水果');
  const map = Object.fromEntries(fruits.options.map((o) => [o.key, o.count]));
  assert.deepStrictEqual(map, { A: 2, B: 2, C: 1, D: 0 });
});

test('T23 文本统计：返回全部填写内容与平均字数', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/stats`).set('Authorization', `Bearer ${token}`);
  const advice = res.body.questions.find((x) => x.title === '建议');
  assert.deepStrictEqual(advice.texts.sort(), ['一般', '不错', '很好']);
  assert.strictEqual(advice.text_count, 3);
  assert.strictEqual(advice.avg_length, 2);
});

test('T24 数字统计：均值 / 最小值 / 最大值正确', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/stats`).set('Authorization', `Bearer ${token}`);
  const age = res.body.questions.find((x) => x.title === '年龄');
  assert.strictEqual(age.number_count, 3);
  assert.strictEqual(age.avg, 30);
  assert.strictEqual(age.min, 20);
  assert.strictEqual(age.max, 40);
});

test('T25 单题统计接口只返回指定题目', async () => {
  const res = await ctx.api
    .get(`/api/surveys/${survey.id}/stats/questions/${q.gender.id}`)
    .set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.question.title, '性别');
  assert.strictEqual(res.body.total_responses, 3);
});

test('T26 答卷明细接口把选项还原成可读文案', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/responses`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.total, 3);
  const first = res.body.items[0];
  assert.strictEqual(first.answers[0].question_order, 1);
  assert.ok(['男', '女', '其他'].some((label) => first.answers[0].display.includes(label)));
});

test('T27 非问卷创建者不能看统计', async () => {
  const res = await ctx.api.get(`/api/surveys/${survey.id}/stats`).set('Authorization', `Bearer ${otherToken}`);
  assert.strictEqual(res.status, 403);
});
