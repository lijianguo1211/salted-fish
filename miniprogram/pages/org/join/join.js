const api = require('../../../utils/api.js');

Page({
  data: { code: '' },
  onCode(e) { this.setData({ code: e.detail.value }); },
  submit() {
    const code = this.data.code.trim();
    if (!code) {
      wx.showToast({ title: '请输入邀请码', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '提交中...' });
    api.request('/orgs/join', { method: 'POST', data: { invite_code: code } })
      .then((res) => {
        wx.hideLoading();
        wx.showToast({ title: (res && res.message) || '已提交', icon: 'none' });
        setTimeout(() => wx.navigateBack(), 800);
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '加入失败', icon: 'none' });
      });
  },
});
