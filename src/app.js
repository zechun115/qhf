'use strict';
const path = require('path');
const express = require('express');
const { AppError } = require('./utils/errors');

function createApp() {
  const app = express();

  app.use(express.json({ limit: '1mb' }));

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
    if (err && err.code === 11000) {
      return res.status(409).json({ error: { code: 'CONFLICT', message: '数据重复，请检查唯一字段' } });
    }
    console.error('[unhandled]', err);
    return res.status(500).json({ error: { code: 'INTERNAL_ERROR', message: '服务器内部错误' } });
  });

  return app;
}

module.exports = { createApp };
