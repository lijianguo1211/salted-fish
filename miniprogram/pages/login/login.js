const app = getApp();
const api = require('../../utils/api.js');
const { REAL_LOGIN } = require('../../config.js');

// 同意状态存本地，记住用户已同意过协议/隐私政策
const AGREED_KEY = 'sf_agreed';
const AGREED_VALUE = '2026-09-07'; // 改协议内容后自增，可强制老用户重新同意

Page({
  data: {
    realLogin: REAL_LOGIN,
    agreed: false,          // 底部勾选状态
    showAgreeModal: false,  // 首登协议/隐私确认弹窗
  },

  onShow() {
    // 真机真实登录：清掉旧演示 token，避免一进来就跳到资料页
    if (REAL_LOGIN) {
      const token = api.getToken() || '';
      if (token.startsWith('demo-token-')) {
        app.logout();
      }
    }

    // 只有「组织 + 资料都齐」的完整会话，才自动进鱼塘；
    // 否则必须停在登录页，先点微信授权（符合：先登录 → 再组织/资料）
    const user = api.getUser();
    if (api.getToken() && user && user.active_org_id && user.profile_completed) {
      app.routeAfterAuth(user);
      return;
    }

    const hasAgreed = wx.getStorageSync(AGREED_KEY) === AGREED_VALUE;
    if (!hasAgreed) {
      this.setData({ showAgreeModal: true, agreed: false });
    } else {
      this.setData({ agreed: true });
    }
  },

  // 拦截弹窗内的滚动冒泡，避免穿透
  noop() {},

  // 勾选/取消勾选
  toggleAgree() {
    this.setData({ agreed: !this.data.agreed });
  },

  // 弹窗内同意：写入本地记录 + 勾选 + 关闭弹窗
  confirmModalAgree() {
    wx.setStorageSync(AGREED_KEY, AGREED_VALUE);
    this.setData({ agreed: true, showAgreeModal: false });
  },

  // 查看协议 / 隐私政策详情
  openUserAgree() {
    wx.navigateTo({ url: '/pages/legal/agree' });
  },
  openPrivacy() {
    wx.navigateTo({ url: '/pages/legal/privacy' });
  },

  // 登录前的合规校验：未勾选则提示
  ensureAgreed() {
    if (!this.data.agreed) {
      wx.showToast({ title: '请先阅读并同意用户协议与隐私政策', icon: 'none' });
      return false;
    }
    wx.setStorageSync(AGREED_KEY, AGREED_VALUE);
    return true;
  },

  doWechatLogin() {
    if (!this.ensureAgreed()) return;
    wx.showLoading({ title: '授权中...' });
    app
      .wechatLogin()
      .then((res) => {
        wx.hideLoading();
        // 登录成功后再分流：无组织 → 选组织；有组织未完善资料 → 填资料
        app.routeAfterAuth(res.user);
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '登录失败', icon: 'none' });
      });
  },
});
