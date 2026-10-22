'use strict';
/** 账号功能测试：T01~T04 */
const test = require('node:test');
const assert = require('node:assert');
const { setup, teardown, register } = require('./helpers');

let ctx;

test.before(async () => {
  ctx = await setup('qb_test_account');
});
test.after(async () => {
  await teardown();
});

test('T01 注册成功并返回 token', async () => {
  const res = await ctx.api.post('/api/auth/register').send({ username: 'alice', password: 'secret123' });
  assert.strictEqual(res.status, 201);
  assert.ok(res.body.token);
  assert.strictEqual(res.body.user.username, 'alice');
  assert.strictEqual(res.body.user.password_hash, undefined, '响应中不能出现密码哈希');
});

test('T02 用户名重复注册返回 409', async () => {
  const res = await ctx.api.post('/api/auth/register').send({ username: 'alice', password: 'secret123' });
  assert.strictEqual(res.status, 409);
  assert.strictEqual(res.body.error.code, 'CONFLICT');
});

test('T02b 用户名或密码长度不合法返回 400', async () => {
  const shortName = await ctx.api.post('/api/auth/register').send({ username: 'ab', password: 'secret123' });
  assert.strictEqual(shortName.status, 400);
  const shortPwd = await ctx.api.post('/api/auth/register').send({ username: 'bobby', password: '123' });
  assert.strictEqual(shortPwd.status, 400);
});

test('T03 正确密码登录成功，错误密码返回 401 且提示统一', async () => {
  const ok = await ctx.api.post('/api/auth/login').send({ username: 'alice', password: 'secret123' });
  assert.strictEqual(ok.status, 200);
  assert.ok(ok.body.token);

  const bad = await ctx.api.post('/api/auth/login').send({ username: 'alice', password: 'wrong-pass' });
  assert.strictEqual(bad.status, 401);
  const notExist = await ctx.api.post('/api/auth/login').send({ username: 'nobody', password: 'secret123' });
  assert.strictEqual(notExist.status, 401);
  assert.strictEqual(bad.body.error.message, notExist.body.error.message, '两种失败应返回相同提示');
});

test('T04 未带 token 访问受保护接口返回 401，带 token 返回本人信息', async () => {
  const anon = await ctx.api.get('/api/surveys');
  assert.strictEqual(anon.status, 401);

  const { token } = await register(ctx.api, 'carol');
  const me = await ctx.api.get('/api/auth/me').set('Authorization', `Bearer ${token}`);
  assert.strictEqual(me.status, 200);
  assert.strictEqual(me.body.user.username, 'carol');
});

test('T04b 伪造 token 被拒绝', async () => {
  const res = await ctx.api.get('/api/surveys').set('Authorization', 'Bearer not-a-real-token');
  assert.strictEqual(res.status, 401);
});
