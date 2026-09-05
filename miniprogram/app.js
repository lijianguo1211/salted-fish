const api = require('./utils/api.js');
const { REAL_LOGIN } = require('./config.js');

App({
  globalData: {
    user: null,
  },

  onLaunch() {
    // 静默尝试使用已存 token
    this.restoreUser();
  },

  restoreUser() {
    const user = api.getUser();
    if (user) {
      this.globalData.user = user;
    }
  },

  // 登录
  // 真实模式：先 wx.login 拿 code，再调后端 /auth/login
  // 演示模式：code 直接传昵称（对应后端 DEMO_MODE=1）
  login(nickname, gradeClass, school) {
    const doLogin = (code) =>
      api.request('/auth/login', {
        method: 'POST',
        data: { code, nickname, grade_class: gradeClass, school },
        auth: false,
      });

    const proceed = (res) => {
      api.setSession(res.token, res.user);
      this.globalData.user = res.user;
      return res;
    };

    if (!REAL_LOGIN) {
      return doLogin(nickname).then(proceed);
    }
    // 真实微信：拿 code
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

  logout() {
    api.clearSession();
    this.globalData.user = null;
  },

  isLoggedIn() {
    return !!api.getToken();
  },
});