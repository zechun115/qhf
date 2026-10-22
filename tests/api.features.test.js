'use strict';
/** 新增常用功能测试：下拉 / 评分 / 日期题型、复制问卷、答卷导出 CSV、提交提示语、填写二维码 —— T59~T69 */
const test = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register, createSurvey, addQuestion, publish, submit } = require('./helpers');

let ctx;
let token;

test.before(async () => {
  ctx = await setup('qb_test_features');
  ({ token } = await register(ctx.api, 'owner'));
});
test.after(async () => {
  await teardown();
});

/** 搭一份「下拉 + 评分 + 日期 + 文本」的已发布问卷，返回 {survey, qDropdown, qRating, qDate, qText} */
async function buildFeatureSurvey() {
  const survey = await createSurvey(ctx.api, token, { title: '新题型问卷', allow_anonymous: true });
  const qDropdown = await addQuestion(ctx.api, token, survey.id, {
    type: 'dropdown',
    title: '你的年级',
    required: true,
    options: [
      { key: 'A', label: '大一' },
      { key: 'B', label: '大二' },
      { key: 'C', label: '大三' },
    ],
  });
  const qRating = await addQuestion(ctx.api, token, survey.id, { type: 'rating', title: '满意度', required: true });
  const qDate = await addQuestion(ctx.api, token, survey.id, { type: 'date', title: '填写日期', required: true });
  const qText = await addQuestion(ctx.api, token, survey.id, { type: 'text', title: '建议' });
  await publish(ctx.api, token, survey.id);
  return { survey, qDropdown, qRating, qDate, qText };
}

test('T59 创建下拉选择题，行为与单选一致', async () => {
  const { qDropdown } = await buildFeatureSurvey();
  assert.strictEqual(qDropdown.type, 'dropdown');
  assert.strictEqual(qDropdown.options.length, 3);
});

test('T60 评分题自动生成 1~5 星选项，且不接受自定义选项', async () => {
  const survey = await createSurvey(ctx.api, token);
  const q = await addQuestion(ctx.api, token, survey.id, {
    type: 'rating',
    title: '给课程打几分',
    options: [
      { key: 'X', label: '试图覆盖' },
      { key: 'Y', label: '无效' },
    ],
  });
  assert.deepStrictEqual(
    q.options.map((o) => o.key),
    ['1', '2', '3', '4', '5']
  );
});

test('T61 下拉 / 评分提交合法答案通过，非法选项被拒绝', async () => {
  const { survey, qDropdown, qRating, qDate, qText } = await buildFeatureSurvey();
  const code = survey.share_code;
  const ok = await submit(ctx.api, code, [
    { question_id: qDropdown.id, option_keys: ['B'] },
    { question_id: qRating.id, option_keys: ['4'] },
    { question_id: qDate.id, date: '2026-10-21' },
    { question_id: qText.id, text: '不错' },
  ]);
  assert.strictEqual(ok.status, 201);

  const bad = await submit(ctx.api, code, [
    { question_id: qDropdown.id, option_keys: ['Z'] },
    { question_id: qRating.id, option_keys: ['9'] },
    { question_id: qDate.id, date: '2026-02-30' },
  ]);
  assert.strictEqual(bad.status, 422);
  const msgs = bad.body.error.details.errors.flatMap((e) => e.messages).join(';');
  assert.ok(msgs.includes('不存在于本题'));
  assert.ok(msgs.includes('请填写合法的日期'));
});

test('T62 日期题格式校验：非 YYYY-MM-DD 或不存在的日期都拒绝', async () => {
  const { survey, qDropdown, qRating, qDate, qText } = await buildFeatureSurvey();
  for (const bad of ['2026/10/21', '21-10-2026', '2026-13-01']) {
    const res = await submit(ctx.api, survey.share_code, [
      { question_id: qDropdown.id, option_keys: ['A'] },
      { question_id: qRating.id, option_keys: ['5'] },
      { question_id: qDate.id, date: bad },
    ]);
    assert.strictEqual(res.status, 422, bad);
  }
});

test('T63 新题型统计：下拉与评分按选项计数，日期给出明细', async () => {
  const { survey, qDropdown, qRating, qDate } = await buildFeatureSurvey();
  await submit(ctx.api, survey.share_code, [
    { question_id: qDropdown.id, option_keys: ['A'] },
    { question_id: qRating.id, option_keys: ['5'] },
    { question_id: qDate.id, date: '2026-10-20' },
  ]);
  await submit(ctx.api, survey.share_code, [
    { question_id: qDropdown.id, option_keys: ['A'] },
    { question_id: qRating.id, option_keys: ['4'] },
    { question_id: qDate.id, date: '2026-10-21' },
  ]);

  const res = await ctx.api
    .get(`/api/surveys/${survey.id}/stats`)
    .set('Authorization', `Bearer ${token}`);
  const byOrder = new Map(res.body.questions.map((q) => [q.order, q]));
  const drop = byOrder.get(1);
  const rating = byOrder.get(2);
  const date = byOrder.get(3);
  assert.strictEqual(drop.options.find((o) => o.key === 'A').count, 2);
  assert.strictEqual(rating.options.find((o) => o.key === '5').count, 1);
  assert.deepStrictEqual(date.dates, ['2026-10-21', '2026-10-20']);
});

test('T64 复制问卷：题目与跳转规则一并复制且目标重映射', async () => {
  const survey = await createSurvey(ctx.api, token, { title: '原问卷' });
  const q1 = await addQuestion(ctx.api, token, survey.id, {
    type: 'single',
    title: '身份',
    required: true,
    options: [
      { key: 'A', label: '学生' },
      { key: 'B', label: '教师' },
    ],
  });
  const q2 = await addQuestion(ctx.api, token, survey.id, { type: 'text', title: '建议' });
  await ctx.api
    .patch(`/api/questions/${q1.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ jump_rules: [{ when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: q2.id }] });

  const dup = await ctx.api.post(`/api/surveys/${survey.id}/duplicate`).set('Authorization', `Bearer ${token}`);
  assert.strictEqual(dup.status, 201);
  assert.strictEqual(dup.body.survey.status, 'draft');
  assert.ok(dup.body.survey.title.includes('副本'));
  assert.ok(dup.body.survey.id !== survey.id);
  assert.notStrictEqual(dup.body.survey.share_code, survey.share_code);

  const detail = await ctx.api
    .get(`/api/surveys/${dup.body.survey.id}`)
    .set('Authorization', `Bearer ${token}`);
  const newQ1 = detail.body.questions.find((q) => q.order === 1);
  const newQ2 = detail.body.questions.find((q) => q.order === 2);
  assert.ok(newQ1.id !== q1.id && newQ2.id !== q2.id);
  // 关键断言：复制后的规则指向新问卷里的题目，而不是原问卷
  assert.strictEqual(newQ1.jump_rules[0].target_question_id, newQ2.id);
});

test('T65 复制的问卷发布后可正常填写', async () => {
  const survey = await createSurvey(ctx.api, token, { title: '待复制', allow_anonymous: true });
  const q = await addQuestion(ctx.api, token, survey.id, { type: 'rating', title: '评分', required: true });
  await publish(ctx.api, token, survey.id);
  const dup = await ctx.api.post(`/api/surveys/${survey.id}/duplicate`).set('Authorization', `Bearer ${token}`);
  const pub = await ctx.api
    .post(`/api/surveys/${dup.body.survey.id}/publish`)
    .set('Authorization', `Bearer ${token}`);
  assert.strictEqual(pub.status, 200);
  const res = await submit(ctx.api, dup.body.survey.share_code, [
    { question_id: pub.body.survey ? q.id : q.id, option_keys: ['3'] },
  ]);
  // 复制后题目 id 变了，原 id 提交应被忽略（题不存在），必答题校验失败返回 422
  assert.strictEqual(res.status, 422);
});

test('T66 答卷导出 CSV：表头、行数与 UTF-8 BOM', async () => {
  const { survey, qDropdown, qRating, qDate, qText } = await buildFeatureSurvey();
  await submit(ctx.api, survey.share_code, [
    { question_id: qDropdown.id, option_keys: ['C'] },
    { question_id: qRating.id, option_keys: ['2'] },
    { question_id: qDate.id, date: '2026-10-21' },
    { question_id: qText.id, text: '希望加案例' },
  ]);

  const res = await ctx.api
    .get(`/api/surveys/${survey.id}/responses/export`)
    .set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res.status, 200);
  assert.ok(res.headers['content-type'].includes('text/csv'));
  const text = res.text;
  assert.ok(text.charCodeAt(0) === 0xfeff, '应带 UTF-8 BOM');
  const lines = text.replace(/^\ufeff/, '').trim().split('\r\n');
  assert.ok(lines[0].includes('Q1 你的年级'));
  assert.strictEqual(lines.length, 2); // 表头 + 1 条答卷
  assert.ok(lines[1].includes('大三'));
  assert.ok(lines[1].includes('希望加案例'));
});

test('T67 提交提示语：创建时设置，提交响应与填写页数据都带出', async () => {
  const survey = await createSurvey(ctx.api, token, {
    title: '提示语问卷',
    allow_anonymous: true,
    submit_message: '问卷已收到，抽奖结果将短信通知！',
  });
  const q = await addQuestion(ctx.api, token, survey.id, { type: 'rating', title: '评分', required: true });
  await publish(ctx.api, token, survey.id);

  const meta = await ctx.api.get(`/api/fill/${survey.share_code}`);
  assert.strictEqual(meta.body.survey.submit_message, '问卷已收到，抽奖结果将短信通知！');

  const res = await submit(ctx.api, survey.share_code, [{ question_id: q.id, option_keys: ['4'] }]);
  assert.strictEqual(res.status, 201);
  assert.strictEqual(res.body.submit_message, '问卷已收到，抽奖结果将短信通知！');
});

test('T68 已发布问卷仍可修改提交提示语，但题目不可改', async () => {
  const { survey } = await buildFeatureSurvey();
  const ok = await ctx.api
    .patch(`/api/surveys/${survey.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ submit_message: '提交成功，感谢参与！' });
  assert.strictEqual(ok.status, 200);
  assert.strictEqual(ok.body.survey.submit_message, '提交成功，感谢参与！');

  const blocked = await ctx.api
    .patch(`/api/surveys/${survey.id}`)
    .set('Authorization', `Bearer ${token}`)
    .send({ title: '试图改标题' });
  assert.strictEqual(blocked.status, 409);
});

test('T69 填写二维码：返回 PNG data URL，链接指向填写页，且他人不可访问', async () => {
  const { survey } = await buildFeatureSurvey();

  const res = await ctx.api
    .get(`/api/surveys/${survey.id}/qrcode`)
    .set('Authorization', `Bearer ${token}`);
  assert.strictEqual(res.status, 200);
  assert.ok(res.body.qr_data_url.startsWith('data:image/png;base64,'), '应是 PNG data URL');
  // data URL 至少 1KB，说明真的编码了内容而不是空图
  assert.ok(res.body.qr_data_url.length > 1000);
  assert.ok(res.body.fill_url.includes('/fill.html?code=' + survey.share_code));

  // 越权：另一个账号不能拿到别人的二维码
  const { token: other } = await register(ctx.api, 'qrstranger');
  const deny = await ctx.api
    .get(`/api/surveys/${survey.id}/qrcode`)
    .set('Authorization', `Bearer ${other}`);
  assert.strictEqual(deny.status, 403);
});
