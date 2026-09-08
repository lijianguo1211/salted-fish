const api = require('../../../utils/api.js');
const entry = require('../../../utils/entry.js');
const app = getApp();

Page({
  data: {
    code: '',
    fromLink: false,
    autoStatus: '', // joining | done | ''
  },

  onLoad(q) {
    entry.setIntent('member');
    if (q && q.code) {
      const code = String(q.code).toUpperCase().trim();
      this.setData({ code, fromLink: true });
      wx.setStorageSync('sf_pending_invite', code);
    }
  },

  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    // 带邀请码进入：自动提交加入（免审则直接进组织）
    if (this.data.fromLink && this.data.code && !this._autoTried) {
      this._autoTried = true;
      this.autoJoin();
    }
  },

  onCode(e) { this.setData({ code: e.detail.value }); },

  autoJoin() {
    this.setData({ autoStatus: 'joining' });
    this.doJoin(true);
  },

  submit() {
    this.doJoin(false);
  },

  doJoin(silent) {
    const code = this.data.code.trim().toUpperCase();
    if (!code) {
      if (!silent) wx.showToast({ title: '请输入邀请码', icon: 'none' });
      this.setData({ autoStatus: '' });
      return;
    }
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    entry.setIntent('member');
    if (!silent) wx.showLoading({ title: '提交中...' });
    api.request('/orgs/join', { method: 'POST', data: { invite_code: code } })
      .then((res) => {
        if (!silent) wx.hideLoading();
        const mem = res && res.membership;
        wx.removeStorageSync('sf_pending_invite');
        this.setData({ autoStatus: 'done' });
        wx.showToast({ title: (res && res.message) || '已提交', icon: 'none' });
        setTimeout(() => {
          if (mem && mem.status === 'active') {
            api.request('/auth/me').then((u) => {
              api.setSession(api.getToken(), u);
              app.globalData.user = u;
              app.routeAfterAuth(u);
            }).catch(() => {
              wx.redirectTo({ url: '/pages/org/list/list' });
            });
          } else {
            wx.redirectTo({ url: '/pages/org/list/list' });
          }
        }, 600);
      })
      .catch((err) => {
        if (!silent) wx.hideLoading();
        this.setData({ autoStatus: '' });
        // 已是成员：直接进组织
        const detail = (err && err.detail) || '';
        if (typeof detail === 'string' && detail.indexOf('已是该组织成员') >= 0) {
          wx.removeStorageSync('sf_pending_invite');
          api.request('/auth/me').then((u) => {
            api.setSession(api.getToken(), u);
            app.globalData.user = u;
            app.routeAfterAuth(u);
          }).catch(() => {
            wx.showToast({ title: detail, icon: 'none' });
          });
          return;
        }
        wx.showToast({ title: detail || '加入失败', icon: 'none' });
      });
  },
});
