'use strict';
/** 问卷创建与管理测试：T05~T09、T28、T29、T30 */
const test = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register, createSurvey, addQuestion, publish } = require('./helpers');

let ctx;
let token;
let otherToken;

test.before(async () => {
  ctx = await setup('qb_test_survey');
  ({ token } = await register(ctx.api, 'owner'));
  ({ token: otherToken } = await register(ctx.api, 'stranger'));
});
test.after(async () => {
  await teardown();
});

test('T05 创建问卷，自动生成唯一短链', async () => {
  const survey = await createSurvey(ctx.api, token, { title: '课程反馈问卷', description: '请如实填写' });
  assert.strictEqual(survey.status, 'draft');
  assert.strictEqual(survey.title, '课程反馈问卷');
  assert.match(survey.share_code, /^[0-9a-z]{8}$/);
  assert.ok(survey.share_url.includes(`code=${survey.share_code}`));
  assert.strictEqual(survey.question_count, 0);
});

test('T05b 标题为空返回 400', async () => {
  const res = await ctx.api.post('/api/surveys').set('Authorization', `Bearer ${token}`).send({ title: '  ' });
  assert.strictEqual(res.status, 400);
});

test('T06 依次添加四种题型，题号自动递增', async () => {
  const survey = await createSurvey(ctx.api, token);
  const q1 = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '你的身份',
    required: true,
    options: [
      { key: 'A', label: '学生' },
      { key: 'B', label: '教师' },
    ],
  });
  const q2 = await addQuestion(ctx.api, token, survey.id, {
    type: 'multiple',
    title: '你常用的编程语言',
    options: [
      { key: 'A', label: 'Python' },
      { key: 'B', label: 'Java' },
      { key: 'C', label: 'Go' },
    ],
    constraints: { min_choice: 1, max_choice: 2 },
  });
  const q3 = await addQuestion(ctx.api, token, survey.id, {
    type: 'text',
    title: '请留下你的建议',
    constraints: { min_length: 2, max_length: 50 },
  });
  const q4 = await addQuestion(ctx.api, token, survey.id, {
    type: 'number',
    title: '你的年龄',
    constraints: { min: 0, max: 120, integer: true },
  });

  assert.deepStrictEqual([q1.order, q2.order, q3.order, q4.order], [1, 2, 3, 4]);
  assert.strictEqual(q1.options.length, 2);
  assert.strictEqual(q3.constraints.min_length, 2);
  assert.strictEqual(q4.constraints.integer, true);

  const detail = await ctx.api.get(`/api/surveys/${survey.id}`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(detail.body.questions.length, 4);
  assert.strictEqual(detail.body.survey.question_count, 4);
});

test('T06b 单选题只有一个选项时返回 400', async () => {
  const survey = await createSurvey(ctx.api, token);
  const res = await ctx.api
    .post(`/api/surveys/${survey.id}/questions`)
    .set('Authorization', `Bearer ${token}`)
    .send({ type: 'single', title: '只有一项', options: [{ key: 'A', label: '唯一' }] });
  assert.strictEqual(res.status, 400);
});

test('T06c 多选最少数量大于最多数量时返回 400', async () => {
  const survey = await createSurvey(ctx.api, token);
  const res = await ctx.api
    .post(`/api/surveys/${survey.id}/questions`)
    .set('Authorization', `Bearer ${token}`)
    .send({
      type: 'multiple',
      title: '非法约束',
      options: [
        { key: 'A', label: 'a' },
        { key: 'B', label: 'b' },
      ],
      constraints: { min_choice: 3, max_choice: 1 },
    });
  assert.strictEqual(res.status, 400);
});

test('T07 空问卷不能发布', async () => {
  const survey = await createSurvey(ctx.api, token);
  const res = await publish(ctx.api, token, survey.id);
  assert.strictEqual(res.status, 409);
  assert.match(res.body.error.message, /至少需要 1 道题/);
});

test('T08 有题目后可以发布，短链可访问', async () => {
  const survey = await createSurvey(ctx.api, token, { allow_anonymous: true });
  await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '满意吗',
    options: [
      { key: 'A', label: '满意' },
      { key: 'B', label: '不满意' },
    ],
  });
  const res = await publish(ctx.api, token, survey.id);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.survey.status, 'published');

  const page = await ctx.api.get(`/api/fill/${survey.share_code}`);
  assert.strictEqual(page.status, 200);
  assert.strictEqual(page.body.questions.length, 1);
});

test('T09 草稿状态的问卷不能通过短链填写', async () => {
  const survey = await createSurvey(ctx.api, token);
  await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '草稿题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  const res = await ctx.api.get(`/api/fill/${survey.share_code}`);
  assert.strictEqual(res.status, 409);
  assert.match(res.body.error.message, /尚未发布/);
});

test('T28 看不到别人的问卷，也无法修改', async () => {
  const survey = await createSurvey(ctx.api, token, { title: '私有问卷' });

  const list = await ctx.api.get('/api/surveys').set('Authorization', `Bearer ${otherToken}`);
  assert.strictEqual(list.body.items.filter((s) => s.id === survey.id).length, 0);

  const detail = await ctx.api.get(`/api/surveys/${survey.id}`).set('Authorization', `Bearer ${otherToken}`);
  assert.strictEqual(detail.status, 403);

  const patch = await ctx.api
    .patch(`/api/surveys/${survey.id}`)
    .set('Authorization', `Bearer ${otherToken}`)
    .send({ title: '被改了' });
  assert.strictEqual(patch.status, 403);
});

test('T29 已发布问卷不能改题目，只能改截止时间', async () => {
  const survey = await createSurvey(ctx.api, token, { allow_anonymous: true });
  const q = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '题目',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  await publish(ctx.api, token, survey.id);

  const editQuestion = await ctx.api
    .patch(`/api/questions/${q.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ title: '偷偷改题' });
  assert.strictEqual(editQuestion.status, 409);

  const editTitle = await ctx.api
    .patch(`/api/surveys/${survey.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ title: '改标题' });
  assert.strictEqual(editTitle.status, 409);

  const editDeadline = await ctx.api
    .patch(`/api/surveys/${survey.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ deadline: '2030-01-01T00:00:00.000Z' });
  assert.strictEqual(editDeadline.status, 200);
  assert.ok(editDeadline.body.survey.deadline);
});

test('T30 删除中间题目后题号重排，指向它的跳转规则被清理', async () => {
  const survey = await createSurvey(ctx.api, token);
  const q1 = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '第1题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  const q2 = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '第2题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  const q3 = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '第3题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });

  // 先给第1题配置「选A跳到第3题」
  const withRule = await ctx.api
    .patch(`/api/questions/${q1.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ jump_rules: [{ when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: q3.id }] });
  assert.strictEqual(withRule.status, 200);
  assert.strictEqual(withRule.body.question.jump_rules.length, 1);

  // 删掉第3题：指向它的规则应被清理，剩余题号重排为 1、2
  const del = await ctx.api.delete(`/api/questions/${q3.id}`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(del.status, 200);

  const detail = await ctx.api.get(`/api/surveys/${survey.id}`).set('Authorization', `Bearer ${token}`);
  assert.deepStrictEqual(detail.body.questions.map((q) => [q.title, q.order]), [
    ['第1题', 1],
    ['第2题', 2],
  ]);
  assert.strictEqual(detail.body.questions[0].jump_rules.length, 0);
  assert.strictEqual(detail.body.survey.question_count, 2);

  // 该问卷仍可正常加题，说明 q2 的数据没被误删
  const q4 = await addQuestion(ctx.api, token, survey.id, {
    type: 'text',
    title: '新增题',
  });
  assert.strictEqual(q4.order, 3);
  assert.ok(q2.id);
});

test('T30b 调整题目顺序后，变成「向前跳」的规则被清理', async () => {
  const survey = await createSurvey(ctx.api, token);
  const a = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: 'A题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  const b = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: 'B题',
    options: [
      { key: 'A', label: 'a' },
      { key: 'B', label: 'b' },
    ],
  });
  await ctx.api
    .patch(`/api/questions/${a.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ jump_rules: [{ when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: b.id }] });

  // 把 B 调到前面，A 变成第 2 题，原规则变成向前跳 → 必须被清理
  const reorder = await ctx.api
    .put(`/api/surveys/${survey.id}/questions/order`)
    .set('Authorization', `Bearer ${token}`)
    .send({ question_ids: [b.id, a.id] });
  assert.strictEqual(reorder.status, 200);
  const movedA = reorder.body.questions.find((q) => q.id === a.id);
  assert.strictEqual(movedA.order, 2);
  assert.strictEqual(movedA.jump_rules.length, 0);
});

test('删除已发布问卷被拒绝，草稿可以删除', async () => {
  const published = await createSurvey(ctx.api, token, { allow_anonymous: true });
  await addQuestion(ctx.api, token, published.id, {
    type: 'text',
    title: '题',
  });
  await publish(ctx.api, token, published.id);
  const res1 = await ctx.api.delete(`/api/surveys/${published.id}`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res1.status, 409);

  const draft = await createSurvey(ctx.api, token);
  const res2 = await ctx.api.delete(`/api/surveys/${draft.id}`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res2.status, 200);
  assert.strictEqual(res2.body.deleted, true);
});
