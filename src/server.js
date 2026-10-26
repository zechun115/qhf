'use strict';
const { createApp } = require('./app');
const { connectDB } = require('./db');

const PORT = parseInt(process.env.PORT, 10) || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/questionnaire';

async function main() {
  const app = createApp();

  // 默认密钥只适合本地演示：一旦部署到能被别人访问的环境，必须换成随机值，
  // 否则任何人都能用公开的默认密钥伪造登录令牌。这里只提醒，不阻断启动。
  if (!process.env.JWT_SECRET) {
    const tip = '正在使用内置默认 JWT 密钥（仅适合本地演示）。对外部署前请设置环境变量 JWT_SECRET。';
    if (process.env.NODE_ENV === 'production') console.error('[auth] ' + tip);
    else console.warn('[auth] ' + tip);
  }

  try {
    await connectDB(MONGO_URI);
    console.log(`[db] connected: ${MONGO_URI}`);
  } catch (e) {
    console.error('[db] 连接失败：', e.message);
    console.error('请确认 MongoDB 已启动（默认 mongodb://127.0.0.1:27017），或用 MONGO_URI 指定连接串。');
    process.exit(1);
  }

  app.listen(PORT, () => {
    console.log(`[web] http://127.0.0.1:${PORT}`);
  });
}

main();
