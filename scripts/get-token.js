// 临时脚本：登录 demo 账号，打印 token 与问卷信息（用于截图流程）
(async () => {
  const base = 'http://127.0.0.1:3000/api';
  const login = await fetch(base + '/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'demo', password: '123456' }),
  }).then((r) => r.json());
  if (!login.token) throw new Error('login failed: ' + JSON.stringify(login));
  const list = await fetch(base + '/surveys?size=5', {
    headers: { Authorization: 'Bearer ' + login.token },
  }).then((r) => r.json());
  const s = list.items.find((x) => x.status === 'published');
  console.log(JSON.stringify({ token: login.token, survey_id: s.id, share_code: s.share_code }, null, 2));
})().catch((e) => { console.error(e.message); process.exit(1); });
