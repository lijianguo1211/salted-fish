const api = require('../../../utils/api.js');
const entry = require('../../../utils/entry.js');
const TYPES = ['school', 'community', 'other'];
const LABELS = ['学校', '小区', '其他'];

Page({
  data: {
    name: '',
    description: '',
    typeIndex: 0,
    typeLabels: LABELS,
    quota: { used: 0, limit: 3, remaining: 3, can_create: true, default_limit: 3 },
  },

  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    entry.setIntent('organizer');
    this.loadQuota();
  },

  loadQuota() {
    api.request('/orgs/create-quota')
      .then((q) => this.setData({ quota: q }))
      .catch(() => {});
  },

  onName(e) { this.setData({ name: e.detail.value }); },
  onDesc(e) { this.setData({ description: e.detail.value }); },
  onType(e) { this.setData({ typeIndex: Number(e.detail.value) }); },

  goQuota() {
    wx.navigateTo({ url: '/pages/org/quota-apply/quota-apply' });
  },

  submit() {
    if (!this.data.quota.can_create) {
      wx.showToast({ title: '额度已满，请先申请提额', icon: 'none' });
      return;
    }
    const name = this.data.name.trim();
    if (name.length < 2) {
      wx.showToast({ title: '名称至少 2 个字', icon: 'none' });
      return;
    }
    entry.setIntent('organizer');
    wx.showLoading({ title: '提交中...' });
    api.request('/orgs/apply', {
      method: 'POST',
      data: {
        name,
        org_type: TYPES[this.data.typeIndex],
        description: this.data.description.trim(),
      },
    }).then(() => {
      wx.hideLoading();
      wx.showToast({ title: '已提交，等待审核', icon: 'none' });
      setTimeout(() => {
        wx.redirectTo({ url: '/pages/org/list/list' });
      }, 800);
    }).catch((err) => {
      wx.hideLoading();
      const detail = (err && err.detail) || '提交失败';
      wx.showToast({ title: detail, icon: 'none' });
      if (typeof detail === 'string' && detail.indexOf('用满') >= 0) {
        this.loadQuota();
      }
    });
  },
});
