'use strict';
/**
 * 演示数据脚本：创建 1 个演示账号 + 1 份已发布问卷（11 题、七种题型、三类跳转规则）
 * + 24 份覆盖各路径的答卷。
 * 用法：npm run seed
 */
const bcrypt = require('bcryptjs');
const { connectDB, disconnectDB, DEFAULT_URI } = require('../src/db');
const User = require('../src/models/User');
const Survey = require('../src/models/Survey');
const Question = require('../src/models/Question');
const Response = require('../src/models/Response');
const { computePath } = require('../src/core/jump');

/** 简单可复现的伪随机（保证每次 seed 结果一致，便于演示与截图） */
function makeRng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}
const pick = (rng, arr) => arr[Math.floor(rng() * arr.length)];

async function main() {
  await connectDB(process.env.MONGO_URI || DEFAULT_URI);

  await Promise.all([User.deleteMany({}), Survey.deleteMany({}), Question.deleteMany({}), Response.deleteMany({})]);

  const user = await User.create({
    username: 'demo',
    password_hash: await bcrypt.hash('123456', 10),
  });

  const survey = await Survey.create({
    owner_id: user._id,
    title: '本科生课程学习体验调查',
    description:
      '本问卷用于演示系统的完整能力：单选、多选、下拉、评分、文本、数字六种题型，以及三类跳转规则——按选项跨题跳转、按数值条件追问、按选项提前结束。',
    allow_anonymous: true,
    allow_multiple: true,
    status: 'published',
    published_at: new Date(),
    share_code: 'demo2026',
    question_count: 11,
    submit_message: '问卷已提交，感谢你的反馈！',
  });

  const qs = await Question.create([
    {
      // Q1
      survey_id: survey._id,
      order: 1,
      type: 'single',
      title: '你的身份是',
      required: true,
      options: [
        { key: 'A', label: '学生' },
        { key: 'B', label: '教师' },
        { key: 'C', label: '其他' },
      ],
    },
    {
      // Q2（仅教师作答）
      survey_id: survey._id,
      order: 2,
      type: 'single',
      title: '你在本课程中承担的角色',
      required: true,
      options: [
        { key: 'A', label: '主讲教师' },
        { key: 'B', label: '助教' },
        { key: 'C', label: '教学管理' },
      ],
    },
    {
      // Q3（仅学生作答）
      survey_id: survey._id,
      order: 3,
      type: 'number',
      title: '你每周课外投入本课程的时间（小时）',
      required: true,
      constraints: { min: 0, max: 60, integer: true },
    },
    {
      // Q4（仅学生作答）
      survey_id: survey._id,
      order: 4,
      type: 'dropdown',
      title: '你的年级',
      required: true,
      options: [
        { key: 'A', label: '大一' },
        { key: 'B', label: '大二' },
        { key: 'C', label: '大三' },
        { key: 'D', label: '大四' },
        { key: 'E', label: '研究生' },
      ],
    },
    {
      // Q5
      survey_id: survey._id,
      order: 5,
      type: 'single',
      title: '你觉得本课程的难度',
      required: true,
      options: [
        { key: 'A', label: '偏易' },
        { key: 'B', label: '适中' },
        { key: 'C', label: '偏难' },
      ],
    },
    {
      // Q6
      survey_id: survey._id,
      order: 6,
      type: 'multiple',
      title: '你希望课程增加哪些内容',
      required: true,
      options: [
        { key: 'A', label: '更多真实案例' },
        { key: 'B', label: '更多动手实验' },
        { key: 'C', label: '更多课堂讨论' },
        { key: 'D', label: '更多课后习题' },
        { key: 'E', label: '行业前沿讲座' },
      ],
      constraints: { min_choice: 1, max_choice: 3 },
    },
    {
      // Q7
      survey_id: survey._id,
      order: 7,
      type: 'text',
      title: '你对课程内容或讲授方式的具体建议',
      required: true,
      constraints: { min_length: 2, max_length: 200 },
    },
    {
      // Q8
      survey_id: survey._id,
      order: 8,
      type: 'single',
      title: '你是否愿意向同学推荐本课程',
      required: true,
      options: [
        { key: 'A', label: '愿意' },
        { key: 'B', label: '不确定' },
        { key: 'C', label: '不愿意' },
      ],
    },
    {
      // Q9
      survey_id: survey._id,
      order: 9,
      type: 'rating',
      title: '你对课程讲授的满意度',
      required: true,
      options: [
        { key: '1', label: '1 星' },
        { key: '2', label: '2 星' },
        { key: '3', label: '3 星' },
        { key: '4', label: '4 星' },
        { key: '5', label: '5 星' },
      ],
    },
    {
      // Q10
      survey_id: survey._id,
      order: 10,
      type: 'number',
      title: '如果满分 10 分，你给本课程打几分',
      required: true,
      constraints: { min: 0, max: 10, integer: true },
    },
    {
      // Q11（仅低分者作答）
      survey_id: survey._id,
      order: 11,
      type: 'text',
      title: '你的评分低于 6 分，主要原因是',
      required: false,
      constraints: { max_length: 100 },
    },
  ]);
  const [q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11] = qs;

  // 三类跳转规则，全部作为数据存在题目里，由引擎解释执行：
  q1.jump_rules = [
    // ① 选项跳题：学生跳过教师专属题，直接进入第 3 题
    { when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: q3._id, priority: 1 },
    // ③ 提前结束：其他身份无可答内容，直接结束问卷
    { when: { op: 'option_selected', option_key: 'C' }, to: 'end', priority: 2 },
  ];
  q2.jump_rules = [
    // ① 选项跳题：教师答完角色题后跳过学生专属题（每周投入、年级）
    { when: { op: 'option_selected', option_key: 'A' }, to: 'question', target_question_id: q5._id, priority: 1 },
    { when: { op: 'option_selected', option_key: 'B' }, to: 'question', target_question_id: q5._id, priority: 2 },
    { when: { op: 'option_selected', option_key: 'C' }, to: 'question', target_question_id: q5._id, priority: 3 },
  ];
  q5.jump_rules = [
    // ① 选项跳题：觉得偏难的人直接跳到建议题，先说困难
    { when: { op: 'option_selected', option_key: 'C' }, to: 'question', target_question_id: q7._id, priority: 1 },
  ];
  q8.jump_rules = [
    // ③ 提前结束：不愿意推荐者跳过满意度与评分，直接结束
    { when: { op: 'option_selected', option_key: 'C' }, to: 'end', priority: 1 },
  ];
  q10.jump_rules = [
    // ② 数值条件：评分低于 6 分时追问原因（第 11 题）
    { when: { op: 'number_lt', value: 6 }, to: 'question', target_question_id: q11._id, priority: 1 },
  ];
  await Promise.all([q1.save(), q2.save(), q5.save(), q8.save(), q10.save()]);

  // ---- 生成 24 份覆盖各条路径的答卷（用跳转引擎自己算路径，保证与真实提交一致）----
  const rng = makeRng(20261021);
  const ADVICE = [
    '希望多讲一些真实项目案例，理论最好结合实际系统',
    '实验课时间有点紧，建议延长或提供课后环境',
    '讲授很清晰，建议增加课堂讨论环节',
    '习题难度跨度太大，希望分层布置作业',
    '课件可以再更新一下行业前沿的内容',
    '老师答疑很及时，课程安排合理，暂时没有其他建议',
    '希望增加一次综合性的大实验，把各章知识串起来',
    '建议把参考资料的链接整理成一个清单发给大家',
    '节奏稍快，关键算法希望能多讲一遍推导过程',
    '多引入一些开源项目的源码阅读会很有帮助',
  ];
  const LOW_REASON = [
    '实验环境配置耗时太多，影响学习积极性',
    '考核方式偏重记忆，希望更侧重动手能力',
    '课程时间与自己的实验安排冲突较大',
  ];

  // 依次生成：2 份「其他」（提前结束）、6 份教师（1 份不愿意推荐提前结束）、16 份学生（3 份低分追问）
  const rows = [];

  for (let i = 0; i < 2; i++) {
    rows.push({ 1: { option_keys: ['C'] } }); // 其他 → 直接结束
  }

  for (let i = 0; i < 6; i++) {
    const row = {
      1: { option_keys: ['B'] },
      2: { option_keys: [pick(rng, ['A', 'A', 'B', 'C'])] },
      5: { option_keys: [pick(rng, ['A', 'B', 'B'])] },
      6: { option_keys: [pick(rng, ['A', 'B']), pick(rng, ['C', 'D', 'E'])] },
      7: { text: pick(rng, ADVICE) },
      9: { option_keys: [String(pick(rng, [4, 4, 5, 5, 5]))] },
      10: { number: pick(rng, [7, 8, 8, 9, 9, 10]) },
    };
    if (i === 4) {
      // 1 位教师不愿意推荐 → 提前结束（不含第 9、10 题）
      row[8] = { option_keys: ['C'] };
      delete row[9];
      delete row[10];
    } else {
      row[8] = { option_keys: [pick(rng, ['A', 'A', 'B'])] };
    }
    rows.push(row);
  }

  for (let i = 0; i < 16; i++) {
    const low = i % 6 === 2; // 第 3、9、15 个学生走低分追问路径
    const diff = low ? 'C' : pick(rng, ['A', 'B', 'B', 'C']);
    const resources = [pick(rng, ['A', 'B']), pick(rng, ['C', 'D']), 'E'].slice(0, 1 + Math.floor(rng() * 3));
    const row = {
      1: { option_keys: ['A'] },
      3: { number: low ? pick(rng, [2, 3, 4]) : 5 + Math.floor(rng() * 20) },
      4: { option_keys: [pick(rng, ['A', 'B', 'B', 'C', 'C', 'D'])] },
      5: { option_keys: [diff] },
      6: { option_keys: [...new Set(resources)] },
      7: { text: pick(rng, ADVICE) },
      9: { option_keys: [String(low ? pick(rng, [2, 3]) : pick(rng, [4, 4, 5, 5, 5]))] },
      10: { number: low ? pick(rng, [4, 5]) : 6 + Math.floor(rng() * 5) },
    };
    if (low) row[11] = { text: pick(rng, LOW_REASON) };
    rows.push(row);
  }

  const qByOrder = new Map(qs.map((q) => [q.order, q]));
  let day = 0;
  for (const row of rows) {
    // 构造「题目 id → 答案」，让跳转引擎计算真实路径
    const answersMap = {};
    for (const [order, v] of Object.entries(row)) answersMap[String(qByOrder.get(Number(order))._id)] = v;
    const { path } = computePath(qs, answersMap);

    // 只保留路径上题目的答案（与前端提交行为一致）
    const pathIds = new Set(path.map((q) => String(q._id)));
    const answers = Object.entries(answersMap)
      .filter(([qidStr]) => pathIds.has(qidStr))
      .map(([qidStr, v]) => {
        const q = qs.find((x) => String(x._id) === qidStr);
        return {
          question_id: q._id,
          question_order: q.order,
          option_keys: v.option_keys || [],
          text: v.text !== undefined ? v.text : null,
          number: v.number !== undefined ? v.number : null,
          date: v.date !== undefined ? v.date : null,
        };
      });

    // 提交时间分散到过去 12 天，统计页的时间线更真实
    if (day < 12) day += 1;
    const submittedAt = new Date(Date.now() - day * 86400000 - Math.floor(rng() * 6) * 3600000);

    await Response.create({
      survey_id: survey._id,
      respondent_id: null,
      anonymous: true,
      answers,
      path,
      submitted_at: submittedAt,
      created_at: submittedAt,
    });
  }

  const total = await Response.countDocuments({ survey_id: survey._id });
  console.log('演示数据已写入：');
  console.log('  账号：demo / 123456');
  console.log(`  问卷：11 题（6 种题型、3 类跳转规则）`);
  console.log(`  答卷：${total} 份，覆盖全部跳转路径`);
  console.log('  填写链接：http://127.0.0.1:3000/fill.html?code=' + survey.share_code);
  await disconnectDB();
}

main().catch(async (e) => {
  console.error(e);
  await disconnectDB();
  process.exit(1);
});
