'use strict';
const { createApp } = require('./app');
const { connectDB } = require('./db');

const PORT = parseInt(process.env.PORT, 10) || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/questionnaire';

async function main() {
  const app = createApp();

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
