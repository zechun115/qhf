'use strict';
/**
 * 题库（bank_questions）第二阶段需求变更测试：T70 ~ T83
 *
 * 覆盖需求：
 * ① 保存常用题 / 问卷选用          ② 共享给其他用户
 * ③ 改题不影响已做好的问卷          ④ 版本链 / 恢复旧版本
 * ⑤ 不同版本同时存在 / fork         ⑥ 查看被哪些问卷使用
 * ⑦ 题库列表管理                    ⑧ 单题跨问卷统计
 */
const { test, describe, after } = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register, createSurvey, addQuestion, publish, submit } = require('./helpers');

after(async () => {
  await teardown();
});

// 模块级共享连接：两个 describe 共用一份 mongoose 连接与 app 实例
let api;
let alice; let aliceToken; // 题作者
let bob; let bobToken; // 被共享者

describe('题库与题目版本管理（第二阶段）', () => {
  test('T70 初始化：注册两个用户，Alice 创建单选题存入题库', async (t) => {
    ({ api } = await setup('qb_bank_test'));
    alice = await register(api, 'alice');
    bob = await register(api, 'bob');
    aliceToken = alice.token;
    bobToken = bob.token;

    const res = await api
      .post('/api/bank-questions')
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({
        type: 'single',
        title: '你的年龄',
        options: ['18 岁以下', '18~25 岁', '26~35 岁', '36 岁以上'],
      });
    assert.equal(res.status, 201);
    assert.equal(res.body.question.version, 1);
    assert.equal(res.body.question.title, '你的年龄');
    assert.equal(res.body.question.options.length, 4);
    assert.equal(res.body.question.root_id, res.body.question.id); // v1 的根是自身
    t.ctx = { bankId: res.body.question.id };
    global.__bankId = res.body.question.id;
  });

  test('T71 题库列表：能看到自己创建的题（scope=mine）', async () => {
    const res = await api.get('/api/bank-questions').set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.total, 1);
    assert.equal(res.body.questions[0].title, '你的年龄');
    assert.equal(res.body.questions[0].is_owner, true);
  });

  test('T72 未登录 / 他人题库列表不可见：Bob 的题库为空', async () => {
    const res = await api.get('/api/bank-questions').set('Authorization', `Bearer ${bobToken}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.total, 0);
    const anon = await api.get('/api/bank-questions');
    assert.equal(anon.status, 401);
  });

  test('T73 修改题库题 = 生成新版本：旧版本保留、version 递增、parent 指向旧版', async () => {
    const bankId = global.__bankId;
    const res = await api
      .put(`/api/bank-questions/${bankId}`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ title: '你的年龄段', options: ['<18', '18~25', '26~35', '>=36', '不愿意说'] });
    assert.equal(res.status, 201);
    assert.equal(res.body.question.version, 2);
    assert.equal(res.body.question.parent_id, bankId);
    assert.equal(res.body.question.root_id, global.__bankId);
    assert.equal(res.body.question.options.length, 5);
    assert.equal(res.body.previous_version, 1);

    // 旧版本仍然存在
    const old = await api.get(`/api/bank-questions/${bankId}`).set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(old.status, 200);
    assert.equal(old.body.question.title, '你的年龄');
  });

  test('T74 版本链：v1 → v2 可查询，latest_version 正确', async () => {
    const bankId = global.__bankId;
    const res = await api.get(`/api/bank-questions/${bankId}/versions`).set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.versions.length, 2);
    assert.equal(res.body.versions[0].version, 1);
    assert.equal(res.body.versions[1].version, 2);
    assert.equal(res.body.versions[1].parent_id, res.body.versions[0].id);
    assert.equal(res.body.latest_version, 2);
  });

  test('T75 恢复旧版本：revert v1 生成 v3（内容同 v1，历史链完整）', async () => {
    const bankId = global.__bankId;
    const res = await api
      .post(`/api/bank-questions/${bankId}/revert`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ version: 1 });
    assert.equal(res.status, 201);
    assert.equal(res.body.question.version, 3);
    assert.equal(res.body.question.title, '你的年龄');
    assert.equal(res.body.question.options.length, 4);
    assert.equal(res.body.restored_from, 1);

    const chain = await api.get(`/api/bank-questions/${bankId}/versions`).set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(chain.body.versions.length, 3);
    assert.equal(chain.body.versions[2].parent_id, res.body.question.parent_id);
  });

  test('T76 共享：Alice 把题共享给 Bob，Bob 可读、可从题库列表看到（scope=shared）', async () => {
    const bankId = global.__bankId;
    const res = await api
      .post(`/api/bank-questions/${bankId}/share`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ username: 'bob' });
    assert.equal(res.status, 200);
    assert.equal(res.body.shared, true);

    const list = await api
      .get('/api/bank-questions?scope=shared')
      .set('Authorization', `Bearer ${bobToken}`);
    assert.equal(list.status, 200);
    assert.equal(list.body.total, 1);
    assert.equal(list.body.questions[0].is_shared_to_me, true);
  });

  test('T77 共享权限：Bob 不能改 Alice 的题（403），但可以 fork 成自己的', async () => {
    const bankId = global.__bankId;
    const put = await api
      .put(`/api/bank-questions/${bankId}`)
      .set('Authorization', `Bearer ${bobToken}`)
      .send({ title: 'Bob 恶意改题' });
    assert.equal(put.status, 403);

    const fork = await api.post(`/api/bank-questions/${bankId}/fork`).set('Authorization', `Bearer ${bobToken}`);
    assert.equal(fork.status, 201);
    assert.equal(fork.body.question.version, 1);
    assert.equal(fork.body.question.owner_id !== undefined, true);
    assert.notEqual(fork.body.question.id, bankId);
    global.__forkId = fork.body.question.id;

    // fork 后 Bob 可以随便改自己的树
    const put2 = await api
      .put(`/api/bank-questions/${global.__forkId}`)
      .set('Authorization', `Bearer ${bobToken}`)
      .send({ title: 'Bob 的年龄题' });
    assert.equal(put2.status, 201);
    assert.equal(put2.body.question.version, 2);
  });

  test('T78 未共享的题他人完全不可访问（403），共享给不存在用户报 404', async () => {
    const carol = await register(api, 'carol');
    const res = await api.get(`/api/bank-questions/${global.__bankId}`).set('Authorization', `Bearer ${carol.token}`);
    assert.equal(res.status, 403);

    const bad = await api
      .post(`/api/bank-questions/${global.__bankId}/share`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ username: 'nobody_here' });
    assert.equal(bad.status, 404);
  });

  test('T79 从问卷保存题目到题库（from-question），再从题库选题加入新问卷', async () => {
    // Alice 建问卷 + 加一道多选题 + 发布
    const survey = await createSurvey(api, aliceToken, { title: '习惯调查' });
    const q = await addQuestion(api, aliceToken, survey.id, {
      type: 'multiple',
      title: '你常用的运动',
      options: ['跑步', '游泳', '健身'],
    });
    await publish(api, aliceToken, survey.id);

    // 保存到题库
    const save = await api
      .post('/api/bank-questions/from-question')
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ question_id: q.id });
    assert.equal(save.status, 201);
    assert.equal(save.body.question.title, '你常用的运动');
    assert.equal(save.body.question.version, 1);
    global.__sportBankId = save.body.question.id;

    // 他人问卷不能保存到自己的题库
    const otherSurvey = await createSurvey(api, bobToken, { title: 'Bob 的问卷' });
    const otherQ = await addQuestion(api, bobToken, otherSurvey.id, {
      type: 'text',
      title: '随便说说',
    });
    const steal = await api
      .post('/api/bank-questions/from-question')
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ question_id: otherQ.id });
    assert.equal(steal.status, 403);

    // 从题库选题加入另一份问卷 → 内容是快照 + 带溯源字段
    const survey2 = await createSurvey(api, aliceToken, { title: '第二次调查' });
    const add = await api
      .post(`/api/surveys/${survey2.id}/questions`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ bank_question_id: global.__sportBankId });
    assert.equal(add.status, 201);
    assert.equal(add.body.question.title, '你常用的运动');
    assert.equal(add.body.question.bank_question_id, global.__sportBankId);
    assert.equal(add.body.question.bank_version, 1);
    assert.equal(add.body.question.options.length, 3);
    global.__survey2Id = survey2.id;

    // 发布问卷2：T82 要验证「已发布后不能从题库再加题」
    await publish(api, aliceToken, survey2.id);
  });

  test('T80 需求③核心：修改题库题后，已选用它的问卷快照内容不变', async () => {
    // 修改题库里的运动题（出 v2，改选项）
    const put = await api
      .put(`/api/bank-questions/${global.__sportBankId}`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ title: '你常用的运动（2026 版）', options: ['跑步', '游泳', '健身', '骑行'] });
    assert.equal(put.status, 201);
    assert.equal(put.body.question.version, 2);

    // 问卷2里的题目内容仍是选题时的快照
    const detail = await api.get(`/api/surveys/${global.__survey2Id}`).set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(detail.status, 200);
    const snap = detail.body.questions.find((x) => x.bank_question_id === global.__sportBankId);
    assert.ok(snap, '问卷里应存在带溯源字段的题目');
    assert.equal(snap.title, '你常用的运动');
    assert.equal(snap.options.length, 3);
    assert.equal(snap.bank_version, 1);
  });

  test('T81 需求⑥：查看题目被哪些问卷使用', async () => {
    const res = await api
      .get(`/api/bank-questions/${global.__sportBankId}/usage`)
      .set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.survey_count, 1);
    assert.equal(res.body.surveys[0].title, '第二次调查');
    assert.equal(res.body.surveys[0].used_versions[0].bank_version, 1);
  });

  test('T82 已发布问卷不能再从题库选题（题目不可变，需求③）', async () => {
    const res = await api
      .post(`/api/surveys/${global.__survey2Id}/questions`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ bank_question_id: global.__sportBankId });
    assert.equal(res.status, 409);
  });

  test('T83 清理：取消共享后 Bob 不再可见', async () => {
    const bankId = global.__bankId;
    const res = await api
      .post(`/api/bank-questions/${bankId}/unshare`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ username: 'bob' });
    assert.equal(res.status, 200);
    const list = await api.get('/api/bank-questions?scope=shared').set('Authorization', `Bearer ${bobToken}`);
    assert.equal(list.body.total, 0);
  });
});

// 上面的统计测试需要真实填答数据，单独用一个完整流程描述块补齐
describe('题库跨问卷统计（完整数据流）', () => {
  let token;
  let bankId;
  let codeA;
  let codeB;

  test('准备：建题库题 → 两份问卷各引用 → 发布 → 各填两份', async () => {
    // 复用第一个 describe 的连接（api 已由 setup 创建），只注册一个新用户
    const u = await register(api, 'stat_user');
    token = u.token;

    const bank = await api
      .post('/api/bank-questions')
      .set('Authorization', `Bearer ${token}`)
      .send({ type: 'single', title: '你的年龄', options: ['18~25', '26~35', '36+'] });
    bankId = bank.body.question.id;

    const mkSurvey = async (title) => {
      const s = await createSurvey(api, token, { title, allow_anonymous: true });
      const q = await api
        .post(`/api/surveys/${s.id}/questions`)
        .set('Authorization', `Bearer ${token}`)
        .send({ bank_question_id: bankId });
      assert.equal(q.status, 201);
      await publish(api, token, s.id);
      const detail = await api.get(`/api/surveys/${s.id}`).set('Authorization', `Bearer ${token}`);
      return { surveyId: s.id, code: detail.body.survey.share_code, questionId: q.body.question.id };
    };

    const a = await mkSurvey('问卷A');
    const b = await mkSurvey('问卷B');
    codeA = a.code;
    codeB = b.code;
    global.__qids = { a: a.questionId, b: b.questionId };

    // 问卷A：2 份答 18~25；问卷B：1 份 26~35、1 份 36+
    await submit(api, codeA, [{ question_id: a.questionId, option_keys: ['A'] }]);
    await submit(api, codeA, [{ question_id: a.questionId, option_keys: ['A'] }]);
    await submit(api, codeB, [{ question_id: b.questionId, option_keys: ['B'] }]);
    const r4 = await submit(api, codeB, [{ question_id: b.questionId, option_keys: ['C'] }]);
    assert.equal(r4.status, 201);
  });

  test('跨问卷统计：response_count=4，各选项计数 2/1/1', async () => {
    const res = await api.get(`/api/bank-questions/${bankId}/stats`).set('Authorization', `Bearer ${token}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.survey_count, 2);
    assert.equal(res.body.response_count, 4);
    assert.equal(res.body.total_answers, 4);
    const byKey = Object.fromEntries(res.body.option_counts.map((o) => [o.key, o.count]));
    assert.equal(byKey['A'], 2);
    assert.equal(byKey['B'], 1);
    assert.equal(byKey['C'], 1);
  });

  test('usage：跨两份问卷均可反查', async () => {
    const res = await api.get(`/api/bank-questions/${bankId}/usage`).set('Authorization', `Bearer ${token}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.survey_count, 2);
  });

  test('数字题 / 文本题统计分支', async () => {
    // 数字题库题
    const bank = await api
      .post('/api/bank-questions')
      .set('Authorization', `Bearer ${token}`)
      .send({ type: 'number', title: '每天运动分钟数', constraints: { min: 0, max: 600 } });
    const bankNumId = bank.body.question.id;

    const s = await createSurvey(api, token, { title: '运动时长', allow_anonymous: true });
    const q = await api
      .post(`/api/surveys/${s.id}/questions`)
      .set('Authorization', `Bearer ${token}`)
      .send({ bank_question_id: bankNumId });
    assert.equal(q.status, 201);
    await publish(api, token, s.id);
    const detail = await api.get(`/api/surveys/${s.id}`).set('Authorization', `Bearer ${token}`);
    await submit(api, detail.body.survey.share_code, [{ question_id: q.body.question.id, number: 30 }]);
    await submit(api, detail.body.survey.share_code, [{ question_id: q.body.question.id, number: 60 }]);

    const stats = await api.get(`/api/bank-questions/${bankNumId}/stats`).set('Authorization', `Bearer ${token}`);
    assert.equal(stats.status, 200);
    assert.equal(stats.body.number_stats.min, 30);
    assert.equal(stats.body.number_stats.max, 60);
    assert.equal(stats.body.number_stats.avg, 45);
  });

  test('未使用过的题：统计返回全零但不报错', async () => {
    const bank = await api
      .post('/api/bank-questions')
      .set('Authorization', `Bearer ${token}`)
      .send({ type: 'text', title: '从未使用的题' });
    const res = await api.get(`/api/bank-questions/${bank.body.question.id}/stats`).set('Authorization', `Bearer ${token}`);
    assert.equal(res.status, 200);
    assert.equal(res.body.survey_count, 0);
    assert.equal(res.body.response_count, 0);
  });
});

/**
 * 多用户可用性审计后补充的回归测试（T89~T92）。
 * 这几条覆盖「别人用这个系统时」最容易踩到的坑：
 * 共享题的越权查看、版本历史被污染、非法 id 变成 500、选题参数非法。
 */
describe('题库权限与健壮性回归（T89~T92）', () => {
  let sharedBankId;

  test('T89 被共享者看不到「使用情况」与「跨问卷统计」（避免暴露他人问卷与答卷）', async () => {
    const bank = await api
      .post('/api/bank-questions')
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ type: 'single', title: '共享可见性测试', options: ['甲', '乙'] });
    assert.equal(bank.status, 201);
    sharedBankId = bank.body.question.id;

    const share = await api
      .post(`/api/bank-questions/${sharedBankId}/share`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ username: 'bob' });
    assert.equal(share.status, 200);

    // 被共享者拥有读权限：详情、版本历史都可以看
    const detail = await api.get(`/api/bank-questions/${sharedBankId}`).set('Authorization', `Bearer ${bobToken}`);
    assert.equal(detail.status, 200);
    const versions = await api
      .get(`/api/bank-questions/${sharedBankId}/versions`)
      .set('Authorization', `Bearer ${bobToken}`);
    assert.equal(versions.status, 200);

    // 但「使用情况 / 跨问卷统计」只属于出题人
    const usageBob = await api
      .get(`/api/bank-questions/${sharedBankId}/usage`)
      .set('Authorization', `Bearer ${bobToken}`);
    assert.equal(usageBob.status, 403);
    const statsBob = await api
      .get(`/api/bank-questions/${sharedBankId}/stats`)
      .set('Authorization', `Bearer ${bobToken}`);
    assert.equal(statsBob.status, 403);

    // 出题人自己可以正常查看
    const usageAlice = await api
      .get(`/api/bank-questions/${sharedBankId}/usage`)
      .set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(usageAlice.status, 200);
    const statsAlice = await api
      .get(`/api/bank-questions/${sharedBankId}/stats`)
      .set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(statsAlice.status, 200);
  });

  test('T90 修改题库题只追加新版本，历史版本的内容与时间戳都不再变动', async () => {
    const before = await api
      .get(`/api/bank-questions/${sharedBankId}/versions`)
      .set('Authorization', `Bearer ${aliceToken}`);
    const v1Before = before.body.versions.find((v) => v.version === 1);
    assert.ok(v1Before, '应存在 v1');

    const put = await api
      .put(`/api/bank-questions/${sharedBankId}`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ title: '共享可见性测试（改）' });
    assert.equal(put.status, 201);
    assert.equal(put.body.question.version, 2);

    const after = await api
      .get(`/api/bank-questions/${sharedBankId}/versions`)
      .set('Authorization', `Bearer ${aliceToken}`);
    assert.equal(after.body.versions.length, 2);
    const v1After = after.body.versions.find((v) => v.version === 1);
    assert.equal(v1After.title, v1Before.title);
    assert.equal(new Date(v1After.updated_at).getTime(), new Date(v1Before.updated_at).getTime());
  });

  test('T91 非法 id 统一返回 400（不再冒 500 服务器内部错误）', async () => {
    const cases = [
      ['get', '/api/surveys/not-an-id'],
      ['get', '/api/surveys/not-an-id/stats'],
      ['get', '/api/bank-questions/not-an-id'],
      ['patch', '/api/questions/not-an-id'],
      ['delete', '/api/questions/not-an-id'],
    ];
    for (const [method, url] of cases) {
      const res = await api[method](url).set('Authorization', `Bearer ${aliceToken}`);
      assert.equal(res.status, 400, `${method.toUpperCase()} ${url} 应返回 400，实际 ${res.status}`);
      assert.equal(res.body.error.code, 'BAD_REQUEST');
    }
  });

  test('T92 从题库选题：id 非法 → 400，题目不存在 → 404', async () => {
    const survey = await createSurvey(api, aliceToken, { title: '健壮性问卷' });
    const bad = await api
      .post(`/api/surveys/${survey.id}/questions`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ bank_question_id: 'not-an-id' });
    assert.equal(bad.status, 400);

    const missing = await api
      .post(`/api/surveys/${survey.id}/questions`)
      .set('Authorization', `Bearer ${aliceToken}`)
      .send({ bank_question_id: '507f1f77bcf86cd799439011' });
    assert.equal(missing.status, 404);
  });
});
