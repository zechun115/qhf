/* 前端公共工具：请求封装、登录态、渲染小工具 */
(function () {
  const TOKEN_KEY = 'qb_token';
  const USER_KEY = 'qb_user';

  const Auth = {
    token: () => localStorage.getItem(TOKEN_KEY),
    user: () => {
      try {
        return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
      } catch (e) {
        return null;
      }
    },
    save(token, user) {
      localStorage.setItem(TOKEN_KEY, token);
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    },
    clear() {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
    requireLogin() {
      if (!Auth.token()) {
        location.href = '/index.html?next=' + encodeURIComponent(location.pathname + location.search);
        return false;
      }
      return true;
    },
  };

  async function api(path, options) {
    const opt = options || {};
    const headers = { 'Content-Type': 'application/json' };
    if (opt.auth !== false && Auth.token()) headers.Authorization = 'Bearer ' + Auth.token();

    const res = await fetch('/api' + path, {
      method: opt.method || 'GET',
      headers,
      body: opt.body === undefined ? undefined : JSON.stringify(opt.body),
    });

    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }

    if (res.status === 401 && opt.auth !== false) {
      Auth.clear();
      location.href = '/index.html?next=' + encodeURIComponent(location.pathname + location.search);
      throw new Error('未登录');
    }
    if (!res.ok) {
      const msg = (data && data.error && data.error.message) || '请求失败（' + res.status + '）';
      const err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function el(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function toast(msg) {
    let node = document.querySelector('.toast');
    if (!node) {
      node = document.createElement('div');
      node.className = 'toast';
      document.body.appendChild(node);
    }
    node.textContent = msg;
    node.classList.add('show');
    clearTimeout(node._t);
    node._t = setTimeout(() => node.classList.remove('show'), 2000);
  }

  function fmtTime(v) {
    if (!v) return '';
    const d = new Date(v);
    const p = (n) => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function statusTag(status) {
    const map = { draft: ['草稿', 'draft'], published: ['已发布', 'published'], closed: ['已关闭', 'closed'] };
    const [label, cls] = map[status] || [status, ''];
    return '<span class="tag ' + cls + '">' + label + '</span>';
  }

  function query(name) {
    return new URLSearchParams(location.search).get(name);
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('已复制到剪贴板');
    } catch (e) {
      window.prompt('请手动复制：', text);
    }
  }

  window.App = { Auth, api, el, esc, toast, fmtTime, statusTag, query, copy };

  /* 「更多」下拉：全局委托，页面只写结构不写交互。
     点按钮切换自己、点别处或按 Esc 关闭，同时只允许展开一个。 */
  function closeMenus(except) {
    document.querySelectorAll('.more.open').forEach((m) => {
      if (m !== except) m.classList.remove('open');
    });
  }
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.more > button');
    if (trigger) {
      const box = trigger.parentElement;
      const willOpen = !box.classList.contains('open');
      closeMenus();
      box.classList.toggle('open', willOpen);
      return;
    }
    // 点了菜单项就收起（菜单项自己的 click 已经在冒泡前触发）
    if (!e.target.closest('.more-list')) closeMenus();
    else setTimeout(() => closeMenus(), 0);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenus();
  });
})();
