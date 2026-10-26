'use strict';
const path = require('path');
const express = require('express');
const { AppError } = require('./utils/errors');

function createApp() {
  const app = express();

  // 部署在 Nginx / 云托管等反向代理之后时，让 req.protocol 能读到 X-Forwarded-Proto，
  // 否则生成的填写短链会固定成 http://，扫码/复制出去的链接在 https 站点上会跳错协议。
  app.set('trust proxy', 1);

  app.use(express.json({ limit: '1mb' }));

  // 基础的响应头加固：本项目是教学项目，不引入 helmet，只补最关键的几条
  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'SAMEORIGIN');
    res.setHeader('Referrer-Policy', 'same-origin');
    next();
  });

  // 前端与后端共用同一套规则引擎（校验 + 跳转），浏览器直接加载这两个文件
  app.use('/core', express.static(path.join(__dirname, 'core')));
  app.use(express.static(path.join(__dirname, '..', 'public')));

  app.get('/api/health', (req, res) => res.json({ ok: true, ts: Date.now() }));

  app.use('/api/auth', require('./routes/auth'));
  app.use('/api/fill', require('./routes/fill').router);
  app.use('/api/surveys', require('./routes/stats'));
  app.use('/api/surveys', require('./routes/surveys').router);
  app.use('/api', require('./routes/questions').router);
  app.use('/api/bank-questions', require('./routes/bank').router);

  // 未匹配的 API 路由统一 404，避免返回 HTML 让前端解析失败
  app.use('/api', (req, res) => {
    res.status(404).json({ error: { code: 'NOT_FOUND', message: '接口不存在' } });
  });

  // 统一错误处理：业务异常按 status 返回，未知异常记录日志并返回 500
  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    if (err instanceof AppError) {
      return res.status(err.status).json({
        error: { code: err.code, message: err.message, details: err.details },
      });
    }
    if (err && err.name === 'ValidationError') {
      return res.status(400).json({
        error: { code: 'BAD_REQUEST', message: '数据校验失败', details: Object.keys(err.errors || {}) },
      });
    }
    // 非法 ObjectId（例如 /api/surveys/undefined）不应该变成 500，
    // 统一当作「资源不存在」处理，前端能拿到可读提示而不是「服务器内部错误」。
    if (err && err.name === 'CastError') {
      return res.status(400).json({
        error: { code: 'BAD_REQUEST', message: '资源 id 格式不正确' },
      });
    }
    if (err && err.code === 11000) {
      return res.status(409).json({ error: { code: 'CONFLICT', message: '数据重复，请检查唯一字段' } });
    }
    console.error('[unhandled]', err);
    return res.status(500).json({ error: { code: 'INTERNAL_ERROR', message: '服务器内部错误' } });
  });

  return app;
}

module.exports = { createApp };
