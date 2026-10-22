'use strict';
const express = require('express');
const bcrypt = require('bcryptjs');
const User = require('../models/User');
const { asyncHandler, badRequest, conflict, unauthorized } = require('../utils/errors');
const { signToken, requireAuth } = require('../middleware/auth');

const router = express.Router();

function checkCredentials(username, password) {
  if (typeof username !== 'string' || username.trim().length < 3 || username.trim().length > 32) {
    throw badRequest('用户名长度需在 3~32 个字符之间');
  }
  if (typeof password !== 'string' || password.length < 6 || password.length > 64) {
    throw badRequest('密码长度需在 6~64 个字符之间');
  }
}

// 注册
router.post(
  '/register',
  asyncHandler(async (req, res) => {
    const { username, password } = req.body || {};
    checkCredentials(username, password);
    const name = username.trim();

    const exists = await User.findOne({ username: name }).lean();
    if (exists) throw conflict('该用户名已被占用');

    const password_hash = await bcrypt.hash(password, 10);
    let user;
    try {
      user = await User.create({ username: name, password_hash });
    } catch (e) {
      // 并发注册时由唯一索引兜底
      if (e && e.code === 11000) throw conflict('该用户名已被占用');
      throw e;
    }

    res.status(201).json({ token: signToken(user._id), user: user.toPublicJSON() });
  })
);

// 登录
router.post(
  '/login',
  asyncHandler(async (req, res) => {
    const { username, password } = req.body || {};
    if (typeof username !== 'string' || typeof password !== 'string') {
      throw badRequest('请填写用户名和密码');
    }
    const user = await User.findOne({ username: username.trim() });
    // 用户不存在与密码错误返回同一提示，避免泄露用户名是否存在
    if (!user) throw unauthorized('用户名或密码错误');
    const ok = await bcrypt.compare(password, user.password_hash);
    if (!ok) throw unauthorized('用户名或密码错误');

    res.json({ token: signToken(user._id), user: user.toPublicJSON() });
  })
);

// 当前登录用户
router.get(
  '/me',
  requireAuth,
  asyncHandler(async (req, res) => {
    const user = await User.findById(req.user.id);
    if (!user) throw unauthorized('用户不存在');
    res.json({ user: user.toPublicJSON() });
  })
);

module.exports = router;
