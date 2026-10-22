'use strict';
const mongoose = require('mongoose');
const request = require('supertest');
const { createApp } = require('../src/app');
const { connectDB, disconnectDB } = require('../src/db');
const User = require('../src/models/User');
const Survey = require('../src/models/Survey');
const Question = require('../src/models/Question');
const Response = require('../src/models/Response');

const BASE = process.env.MONGO_TEST_URI || 'mongodb://127.0.0.1:27017';

/**
 * 每个测试文件用独立数据库名，互不干扰，可并行执行。
 */
async function setup(dbName) {
  await connectDB(`${BASE}/${dbName}`);
  await mongoose.connection.dropDatabase();
  await Promise.all([
    User.syncIndexes(),
    Survey.syncIndexes(),
    Question.syncIndexes(),
    Response.syncIndexes(),
  ]);
  const app = createApp();
  return { app, api: request(app) };
}

async function teardown() {
  await mongoose.connection.dropDatabase().catch(() => {});
  await disconnectDB();
}

/** 注册一个用户并返回 { token, user } */
async function register(api, username, password = 'secret123') {
  const res = await api.post('/api/auth/register').send({ username, password });
  if (res.status !== 201) throw new Error(`注册失败: ${res.status} ${JSON.stringify(res.body)}`);
  return res.body;
}

/** 创建问卷并返回 id */
async function createSurvey(api, token, overrides = {}) {
  const res = await api
    .post('/api/surveys')
    .set('Authorization', `Bearer ${token}`)
    .send({ title: '测试问卷', ...overrides });
  if (res.status !== 201) throw new Error(`建问卷失败: ${res.status} ${JSON.stringify(res.body)}`);
  return res.body.survey;
}

/** 加一道题 */
async function addQuestion(api, token, surveyId, payload) {
  const res = await api
    .post(`/api/surveys/${surveyId}/questions`)
    .set('Authorization', `Bearer ${token}`)
    .send(payload);
  if (res.status !== 201) throw new Error(`加题失败: ${res.status} ${JSON.stringify(res.body)}`);
  return res.body.question;
}

/** 发布 */
async function publish(api, token, surveyId) {
  const res = await api.post(`/api/surveys/${surveyId}/publish`).set('Authorization', `Bearer ${token}`);
  return res;
}

/** 填答 */
async function submit(api, code, answers, token = null, extra = {}) {
  const req = api.post(`/api/fill/${code}/submit`);
  if (token) req.set('Authorization', `Bearer ${token}`);
  return req.send({ answers, ...extra });
}

module.exports = { setup, teardown, register, createSurvey, addQuestion, publish, submit };
