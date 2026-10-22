'use strict';
/** 填写 / 跳转 / 校验测试：T10~T20 */
const test = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register, createSurvey, addQuestion, publish, submit } = require('./helpers');

let ctx;
let token;
let survey;
let q = {};

test.before(async () => {
  ctx = await setup('qb_test_fill');
  ({ token } = await register(ctx.api, 'filler'));

  survey = await createSurvey(ctx.api, token, { title: '校园生活调查', allow_anonymous: false, allow_multiple: true });

  q.identity = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '你的身份',
    required: true,
    options: [
      { key: 'A', label: '学生' },
      { key: 'B', label: '教师' },
    ],
  });
  q.studentAdvice = await addQuestion(ctx.api, token, survey.id, {
    type: 'text',
    title: '你对课程的建议',
    required: true,
    constraints: { min_length: 2, max_length: 50 },
  });
  q.teachingYears = await addQuestion(ctx.api, token, survey.id, {
    type: 'number',
    title: '你的教龄（年）',
    required: true,
    constraints: { min: 0, max: 50, integer: true },
  });
  q.recommend = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '是否推荐这门课',
    required: true,
    options: [
      { key: 'A', label: '推荐' },
      { key: 'B', label: '不推荐' },
    ],
  });
  q.remark = await addQuestion(ctx.api, token, survey.id, {
    type: 'text',
    title: '补充说明',
    required: false,
  });

  // 学生 → 跳过「建议 / 教龄」直达第 4 题；教师 → 正常往下走
  const res = await ctx.api
    .patch(`/api/questions/${q.identity.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({
      jump_rules: [
        { when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: q.recommend.id, priority: 1 },
      ],
    });
  assert.strictEqual(res.status, 200, JSON.stringify(res.body));

  await publish(ctx.api, token, survey.id);
});

test.after(async () => {
  await teardown();
});

test('T10 学生身份跳转：路径为 1 → 4 → 5', async () => {
  const res = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['A'] },
      { question_id: q.recommend.id, option_keys: ['A'] },
    ],
    token
  );
  assert.strictEqual(res.status, 201, JSON.stringify(res.body));
  assert.deepStrictEqual(res.body.path, [1, 4, 5]);
  assert.strictEqual(res.body.ended_early, false);
  assert.strictEqual(res.body.answered_count, 2, '第 5 题非必答且未填，不应产生答案记录');
});

test('T10b 教师身份不跳转：路径为 1 → 2 → 3 → 4 → 5', async () => {
  const res = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['B'] },
      { question_id: q.studentAdvice.id, text: '希望多讲案例' },
      { question_id: q.teachingYears.id, number: 5 },
      { question_id: q.recommend.id, option_keys: ['A'] },
      { question_id: q.remark.id, text: '没有' },
    ],
    token
  );
  assert.strictEqual(res.status, 201, JSON.stringify(res.body));
  assert.deepStrictEqual(res.body.path, [1, 2, 3, 4, 5]);
  assert.strictEqual(res.body.answered_count, 5);
});

test('T10c 被跳过的题目即使提交了答案也不影响校验与统计', async () => {
  const res = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['A'] },
      { question_id: q.studentAdvice.id, text: '这条应该被忽略' },
      { question_id: q.recommend.id, option_keys: ['B'] },
    ],
    token
  );
  assert.strictEqual(res.status, 201, JSON.stringify(res.body));
  assert.deepStrictEqual(res.body.path, [1, 4, 5]);
});

test('T14 必答题未作答返回 422 并指出具体题目', async () => {
  const res = await submit(ctx.api, survey.share_code, [{ question_id: q.identity.id, option_keys: ['B'] }], token);
  assert.strictEqual(res.status, 422);
  const orders = res.body.error.details.errors.map((e) => e.order);
  assert.ok(orders.includes(2) && orders.includes(3), '应同时报告跳过的必答题');
});

test('T16 文本长度不合规返回 422', async () => {
  const res = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['B'] },
      { question_id: q.studentAdvice.id, text: '好' },
      { question_id: q.teachingYears.id, number: 3 },
      { question_id: q.recommend.id, option_keys: ['A'] },
    ],
    token
  );
  assert.strictEqual(res.status, 422);
  assert.match(res.body.error.details.errors[0].messages.join(), /不能少于 2/);
});

test('T17 数字题填小数 / 超范围返回 422', async () => {
  const decimal = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['B'] },
      { question_id: q.studentAdvice.id, text: '内容足够长' },
      { question_id: q.teachingYears.id, number: 3.5 },
      { question_id: q.recommend.id, option_keys: ['A'] },
    ],
    token
  );
  assert.strictEqual(decimal.status, 422);
  assert.match(decimal.body.error.details.errors[0].messages.join(), /整数/);

  const outOfRange = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['B'] },
      { question_id: q.studentAdvice.id, text: '内容足够长' },
      { question_id: q.teachingYears.id, number: 99 },
      { question_id: q.recommend.id, option_keys: ['A'] },
    ],
    token
  );
  assert.strictEqual(outOfRange.status, 422);
  assert.match(outOfRange.body.error.details.errors[0].messages.join(), /不能大于 50/);
});

test('T15 多选题数量下限 / 上限校验', async () => {
  const s2 = await createSurvey(ctx.api, token, { title: '多选测试', allow_anonymous: true });
  const multi = await addQuestion(ctx.api, token, s2.id, {
    type: 'multiple',
    title: '你喜欢的水果',
    required: true,
    options: [
      { key: 'A', label: '苹果' },
      { key: 'B', label: '香蕉' },
      { key: 'C', label: '西瓜' },
      { key: 'D', label: '葡萄' },
    ],
    constraints: { min_choice: 2, max_choice: 3 },
  });
  await publish(ctx.api, token, s2.id);

  const tooFew = await submit(ctx.api, s2.share_code, [{ question_id: multi.id, option_keys: ['A'] }]);
  assert.strictEqual(tooFew.status, 422);
  assert.match(tooFew.body.error.details.errors[0].messages.join(), /至少选择 2 项/);

  const tooMany = await submit(ctx.api, s2.share_code, [{ question_id: multi.id, option_keys: ['A', 'B', 'C', 'D'] }]);
  assert.strictEqual(tooMany.status, 422);
  assert.match(tooMany.body.error.details.errors[0].messages.join(), /最多选择 3 项/);

  const ok = await submit(ctx.api, s2.share_code, [{ question_id: multi.id, option_keys: ['A', 'C'] }]);
  assert.strictEqual(ok.status, 201, JSON.stringify(ok.body));
});

test('T19 提交成功后答卷落库，字段结构与预期一致', async () => {
  const Response = require('../src/models/Response');
  const res = await submit(
    ctx.api,
    survey.share_code,
    [
      { question_id: q.identity.id, option_keys: ['A'] },
      { question_id: q.recommend.id, option_keys: ['A'] },
      { question_id: q.remark.id, text: '祝课程越办越好' },
    ],
    token
  );
  assert.strictEqual(res.status, 201);
  const doc = await Response.findById(res.body.response_id).lean();
  assert.ok(doc);
  assert.strictEqual(doc.answers.length, 3);
  assert.strictEqual(doc.answers[0].question_order, 1);
  assert.deepStrictEqual(doc.path.length, 3);
  assert.ok(doc.submitted_at instanceof Date);
});

test('T20 非匿名问卷未登录不能填写', async () => {
  const res = await submit(ctx.api, survey.share_code, [{ question_id: q.identity.id, option_keys: ['A'] }]);
  assert.strictEqual(res.status, 401);
});

test('T20b 匿名问卷无需登录即可提交，答卷标记为匿名', async () => {
  const s3 = await createSurvey(ctx.api, token, { title: '匿名问卷', allow_anonymous: true });
  const t = await addQuestion(ctx.api, token, s3.id, { type: 'text', title: '随便说点什么' });
  await publish(ctx.api, token, s3.id);

  const res = await submit(ctx.api, s3.share_code, [{ question_id: t.id, text: '匿名留言' }]);
  assert.strictEqual(res.status, 201, JSON.stringify(res.body));

  const Response = require('../src/models/Response');
  const doc = await Response.findById(res.body.response_id).lean();
  assert.strictEqual(doc.anonymous, true);
  assert.strictEqual(doc.respondent_id, null);
});

test('T20c 关闭重复填写后同一用户第二次提交返回 409', async () => {
  const s4 = await createSurvey(ctx.api, token, { title: '限填一次', allow_multiple: false });
  const t = await addQuestion(ctx.api, token, s4.id, { type: 'text', title: '一句话' });
  await publish(ctx.api, token, s4.id);

  const first = await submit(ctx.api, s4.share_code, [{ question_id: t.id, text: '第一次' }], token);
  assert.strictEqual(first.status, 201);

  const second = await submit(ctx.api, s4.share_code, [{ question_id: t.id, text: '第二次' }], token);
  assert.strictEqual(second.status, 409);
  assert.match(second.body.error.message, /不允许同一用户重复填写/);
});

test('T20d 超过截止时间后不能填写', async () => {
  const s5 = await createSurvey(ctx.api, token, { title: '已截止', allow_anonymous: true });
  const t = await addQuestion(ctx.api, token, s5.id, { type: 'text', title: '题目' });
  await publish(ctx.api, token, s5.id);
  await ctx.api
    .patch(`/api/surveys/${s5.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ deadline: new Date(Date.now() - 60_000).toISOString() });

  const res = await submit(ctx.api, s5.share_code, [{ question_id: t.id, text: '迟到了' }]);
  assert.strictEqual(res.status, 409);
  assert.match(res.body.error.message, /截止时间/);
});

test('T20e 关闭问卷后链接失效', async () => {
  const s6 = await createSurvey(ctx.api, token, { title: '待关闭', allow_anonymous: true });
  await addQuestion(ctx.api, token, s6.id, { type: 'text', title: '题目' });
  await publish(ctx.api, token, s6.id);
  const close = await ctx.api.post(`/api/surveys/${s6.id}/close`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(close.status, 200);

  const res = await ctx.api.get(`/api/fill/${s6.share_code}`);
  assert.strictEqual(res.status, 409);
  assert.match(res.body.error.message, /已关闭/);
});
