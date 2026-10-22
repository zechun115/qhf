'use strict';
const jwt = require('jsonwebtoken');
const { unauthorized } = require('../utils/errors');

const SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';
const EXPIRES_IN = '7d';

function signToken(userId) {
  return jwt.sign({ uid: String(userId) }, SECRET, { expiresIn: EXPIRES_IN });
}

function readToken(req) {
  const header = req.headers.authorization || '';
  if (header.startsWith('Bearer ')) return header.slice(7).trim();
  return null;
}

/** 必须登录 */
function requireAuth(req, res, next) {
  const token = readToken(req);
  if (!token) return next(unauthorized());
  try {
    const payload = jwt.verify(token, SECRET);
    req.user = { id: payload.uid };
    next();
  } catch (e) {
    next(unauthorized('登录状态已失效，请重新登录'));
  }
}

/** 可选登录：填答接口用，匿名问卷允许不带 token */
function optionalAuth(req, res, next) {
  const token = readToken(req);
  req.user = null;
  if (!token) return next();
  try {
    const payload = jwt.verify(token, SECRET);
    req.user = { id: payload.uid };
  } catch (e) {
    // token 过期不应阻断匿名访问，按未登录处理
  }
  next();
}

module.exports = { signToken, requireAuth, optionalAuth, SECRET };
