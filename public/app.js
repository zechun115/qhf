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

  function toast(msg, kind) {
    let node = document.querySelector('.toast');
    if (!node) {
      node = document.createElement('div');
      node.className = 'toast';
      document.body.appendChild(node);
    }
    node.className = 'toast' + (kind === 'err' ? ' err' : '');
    node.textContent = msg;
    // 先移除再添加，保证连续多次提示也能重新触发入场过渡
    node.classList.remove('show');
    void node.offsetWidth;
    node.classList.add('show');
    clearTimeout(node._t);
    node._t = setTimeout(() => node.classList.remove('show'), kind === 'err' ? 3200 : 2000);
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

  function copy(text) {
    try {
      return navigator.clipboard.writeText(text).then(
        () => toast('已复制到剪贴板'),
        () => window.prompt('请手动复制：', text)
      );
    } catch (e) {
      window.prompt('请手动复制：', text);
    }
  }

  /* ------------------------------------------------------------
     按钮忙碌态：只加类，不 disable——disabled 会把按钮变成灰色，
     与像素风的「按下」观感冲突；这里用 pointer-events 挡住重复点击。
     ------------------------------------------------------------ */
  function busy(btn, on) {
    if (!btn) return btn;
    const flag = on !== false;
    btn.classList.toggle('busy', flag);
    btn.setAttribute('aria-busy', String(flag));
    return btn;
  }

  /* ------------------------------------------------------------
     像素风确认框：替代原生 confirm()。
     原生 confirm 会阻塞线程、样式与整站不统一（浏览器默认弹窗），
     这里返回 Promise，调用处写 if (!(await App.confirm(...))) return;
     ------------------------------------------------------------ */
  let confirmDone = null;

  function ensureConfirmBox() {
    let box = document.getElementById('app-confirm');
    if (box) return box;
    box = el(
      '<div class="modal hidden" id="app-confirm">' +
        '<div class="modal-box">' +
          '<div class="between" style="margin-bottom:2px">' +
            '<h3 id="ac-title">请确认</h3>' +
            '<button class="small" data-act="cancel" aria-label="取消">✕</button>' +
          '</div>' +
          '<p class="msg" id="ac-msg"></p>' +
          '<div class="actions">' +
            '<button data-act="cancel">取消</button>' +
            '<button class="primary" data-act="ok" id="ac-ok">确定</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
    document.body.appendChild(box);
    box.addEventListener('click', (e) => {
      if (e.target === box) return resolveConfirm(false);
      const act = e.target.closest('[data-act]');
      if (act) resolveConfirm(act.dataset.act === 'ok');
    });
    return box;
  }

  function resolveConfirm(val) {
    const box = document.getElementById('app-confirm');
    if (box) box.classList.add('hidden');
    syncModalLock();
    const done = confirmDone;
    confirmDone = null;
    if (done) done(val);
    // 关闭后把焦点还给触发它的按钮，键盘用户不会「跟丢」
    // （若触发按钮在下拉菜单里、菜单已收起，元素不可见就不再强行聚焦）
    const back = box && box._back;
    if (back && document.contains(back) && back.offsetParent !== null) {
      setTimeout(() => back.focus({ preventScroll: true }), 0);
    }
  }

  function confirmAsk(message, opts) {
    const o = opts || {};
    const box = ensureConfirmBox();
    box._back = document.activeElement;
    document.getElementById('ac-title').textContent = o.title || '请确认';
    document.getElementById('ac-msg').textContent = message || '';
    const ok = document.getElementById('ac-ok');
    ok.textContent = o.okText || '确定';
    ok.className = 'primary' + (o.danger ? ' danger' : '');
    box.classList.remove('hidden');
    syncModalLock();
    setTimeout(() => ok.focus(), 0);
    return new Promise((resolve) => {
      confirmDone = resolve;
    });
  }

  /* ------------------------------------------------------------
     弹窗通用行为：Esc 关闭最上层、打开时锁滚动、点击遮罩不穿透
     页面自己仍可用 classList.add('hidden') 关闭，这里只是兜底。
     ------------------------------------------------------------ */
  function openModals() {
    return Array.prototype.filter.call(
      document.querySelectorAll('.modal'),
      (m) => !m.classList.contains('hidden')
    );
  }

  function syncModalLock() {
    document.body.classList.toggle('modal-open', openModals().length > 0);
  }

  function watchModals() {
    const list = document.querySelectorAll('.modal');
    if (!list.length) return;
    const mo = new MutationObserver(syncModalLock);
    Array.prototype.forEach.call(list, (m) => mo.observe(m, { attributes: true, attributeFilter: ['class'] }));
    syncModalLock();
  }

  /* ------------------------------------------------------------
     导航：当前页高亮由路径推导，避免每个页面手写 class="active"
     （edit / stats 属于「我的问卷」这一支）。
     ------------------------------------------------------------ */
  function markNav() {
    const path = location.pathname.replace(/\/+$/, '') || '/index.html';
    Array.prototype.forEach.call(document.querySelectorAll('.nav .links a[href]'), (a) => {
      const href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#') return;
      const target = href.split('?')[0];
      const same = target === path;
      const sub = target === '/dashboard.html' && /^\/(edit|stats)\.html$/.test(path);
      a.classList.toggle('active', same || sub);
      if (same || sub) a.setAttribute('aria-current', 'page');
    });
  }

  function watchNavScroll() {
    const nav = document.querySelector('.nav');
    if (!nav) return;
    const update = () => nav.classList.toggle('scrolled', window.scrollY > 4);
    window.addEventListener('scroll', update, { passive: true });
    update();
  }

  window.App = {
    Auth, api, el, esc, toast, fmtTime, statusTag, query, copy, busy, confirm: confirmAsk,
  };

  document.addEventListener('DOMContentLoaded', () => {
    markNav();
    watchNavScroll();
    watchModals();
  });

  /* 「更多」下拉：全局委托，页面只写结构不写交互。
     点按钮切换自己、点别处关闭，同时只允许展开一个。 */
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
      if (willOpen) {
        const first = box.querySelector('.more-list button:not(:disabled), .more-list a');
        if (first) first.focus({ preventScroll: true });
      }
      return;
    }
    // 点了菜单项就收起（菜单项自己的 click 已经在冒泡前触发）
    if (!e.target.closest('.more-list')) closeMenus();
    else setTimeout(() => closeMenus(), 0);
  });

  /* Esc：先关最上层的弹窗，没有弹窗再收下拉菜单 */
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const modals = openModals();
    if (modals.length) {
      const top = modals[modals.length - 1];
      if (top.id === 'app-confirm') resolveConfirm(false);
      else top.classList.add('hidden');
      syncModalLock();
      return;
    }
    closeMenus();
  });
})();
