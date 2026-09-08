const api = require('./utils/api.js');
const { REAL_LOGIN, CLOUD_ENV } = require('./config.js');

const DEMO_ID_KEY = 'sf_demo_id';

App({
  globalData: {
    user: null,
  },

  onLaunch() {
    // 初始化腾讯云开发环境，供 wx.cloud.extend.AI 调用大模型使用
    // （wx.cloud 仅存在于基础库支持且云开发已开通时）
    if (wx.cloud) {
      try {
        wx.cloud.init({
          env: CLOUD_ENV,
          traceUser: true,
        });
      } catch (e) {
        // 云开发未开通 / 环境 ID 不对时保持原有逻辑，不阻塞业务
        console.warn('wx.cloud.init 失败：', e);
      }
    }
    this.restoreUser();
    // 真机真实登录：丢弃旧演示会话，避免跳过微信授权
    if (REAL_LOGIN) {
      const token = api.getToken() || '';
      if (token.startsWith('demo-token-')) {
        this.logout();
      }
    }
    this.refreshSession();
  },

  restoreUser() {
    const user = api.getUser();
    if (user) {
      this.globalData.user = user;
    }
  },

  /** 用服务端最新资料覆盖本地缓存（避免 profile_completed 等标志过期） */
  refreshSession() {
    if (!api.getToken()) return;
    api
      .request('/auth/me')
      .then((user) => {
        api.setSession(api.getToken(), user);
        this.globalData.user = user;
      })
      .catch(() => {});
  },

  /** 登录后统一分流：组织入口 → 资料 → 管理台/鱼塘 */
  routeAfterAuth(user) {
    const u = user || api.getUser() || this.globalData.user;
    if (!u) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    if (!u.active_org_id) {
      const pending = wx.getStorageSync('sf_pending_invite');
      if (pending) {
        wx.redirectTo({
          url: `/pages/org/join/join?code=${encodeURIComponent(pending)}`,
        });
        return;
      }
      wx.redirectTo({ url: '/pages/org/gate/gate' });
      return;
    }
    if (!u.profile_completed) {
      wx.redirectTo({ url: '/pages/profile/setup' });
      return;
    }
    this.enterHomeByRole(u);
  },

  /** 组织管理员进管理台，普通成员进鱼塘 */
  enterHomeByRole(user) {
    const u = user || api.getUser() || this.globalData.user;
    const orgId = u && u.active_org_id;
    if (!orgId) {
      wx.redirectTo({ url: '/pages/org/gate/gate' });
      return;
    }
    api
      .request('/orgs/current')
      .then((res) => {
        const mem = res.membership;
        const isAdmin = !!(mem && (mem.role === 'owner' || mem.role === 'admin'));
        if (isAdmin) {
          wx.redirectTo({ url: `/pages/org/manage/manage?orgId=${orgId}` });
        } else {
          wx.switchTab({ url: '/pages/index/index' });
        }
      })
      .catch(() => {
        wx.switchTab({ url: '/pages/index/index' });
      });
  },

  /** 进入业务页前校验；未就绪则跳转并返回 false */
  ensureReady() {
    const u = api.getUser() || this.globalData.user;
    if (!api.getToken() || !u) {
      wx.redirectTo({ url: '/pages/login/login' });
      return false;
    }
    if (!u.active_org_id) {
      const pending = wx.getStorageSync('sf_pending_invite');
      if (pending) {
        wx.redirectTo({
          url: `/pages/org/join/join?code=${encodeURIComponent(pending)}`,
        });
      } else {
        wx.redirectTo({ url: '/pages/org/gate/gate' });
      }
      return false;
    }
    if (!u.profile_completed) {
      wx.redirectTo({ url: '/pages/profile/setup' });
      return false;
    }
    return true;
  },

  getDemoId() {
    let id = wx.getStorageSync(DEMO_ID_KEY);
    if (!id) {
      id = `demo-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      wx.setStorageSync(DEMO_ID_KEY, id);
    }
    return id;
  },

  /**
   * 微信授权登录（不填资料）。
   * 演示模式：用本地稳定 demoId 当 code。
   * 真实模式：wx.login 拿 code。
   */
  wechatLogin() {
    const doLogin = (code) =>
      api.request('/auth/login', {
        method: 'POST',
        data: { code },
        auth: false,
      });

    const proceed = (res) => {
      api.setSession(res.token, res.user);
      this.globalData.user = res.user;
      return res;
    };

    if (!REAL_LOGIN) {
      return doLogin(this.getDemoId()).then(proceed);
    }
    return new Promise((resolve, reject) => {
      wx.login({
        success: (r) => {
          if (!r.code) return reject({ detail: 'wx.login 未返回 code' });
          doLogin(r.code).then(proceed).then(resolve).catch(reject);
        },
        fail: (err) => reject({ detail: `wx.login 失败: ${err.errMsg}` }),
      });
    });
  },

  // 兼容旧调用：完善资料后仍可用（内部走 profile）
  login(nickname, gradeClass, school) {
    return this.wechatLogin().then((res) =>
      api
        .request('/auth/profile', {
          method: 'PUT',
          data: {
            nickname,
            grade_class: gradeClass || '',
            school: school || '',
          },
        })
        .then((user) => {
          api.setSession(api.getToken(), user);
          this.globalData.user = user;
          return { token: api.getToken(), user };
        })
    );
  },

  logout() {
    api.clearSession();
    this.globalData.user = null;
    try {
      wx.removeStorageSync('sf_entry_intent');
      wx.removeStorageSync('sf_pending_invite');
      // 切真实登录时一并清掉演示设备 ID，避免串号
      if (REAL_LOGIN) {
        wx.removeStorageSync(DEMO_ID_KEY);
      }
    } catch (e) { /* ignore */ }
  },

  isLoggedIn() {
    return !!api.getToken();
  },
});
