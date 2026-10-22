'use strict';

/** 统一的业务异常：带 HTTP 状态码与机器可读的 code */
class AppError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details || null;
  }
}

/** 包一层 async 路由，异常统一交给 errorHandler，避免每个 handler 写 try/catch */
const asyncHandler = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

const badRequest = (msg, details) => new AppError(400, 'BAD_REQUEST', msg, details);
const unauthorized = (msg = '请先登录') => new AppError(401, 'UNAUTHORIZED', msg);
const forbidden = (msg = '无权访问该资源') => new AppError(403, 'FORBIDDEN', msg);
const notFound = (msg = '资源不存在') => new AppError(404, 'NOT_FOUND', msg);
const conflict = (msg, details) => new AppError(409, 'CONFLICT', msg, details);
const unprocessable = (msg, details) => new AppError(422, 'VALIDATION_FAILED', msg, details);

module.exports = {
  AppError,
  asyncHandler,
  badRequest,
  unauthorized,
  forbidden,
  notFound,
  conflict,
  unprocessable,
};
