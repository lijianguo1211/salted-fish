const api = require('../../../utils/api.js');
const TYPES = ['school', 'community', 'other'];
const LABELS = ['学校', '小区', '其他'];

Page({
  data: { name: '', description: '', typeIndex: 0, typeLabels: LABELS },
  onName(e) { this.setData({ name: e.detail.value }); },
  onDesc(e) { this.setData({ description: e.detail.value }); },
  onType(e) { this.setData({ typeIndex: Number(e.detail.value) }); },
  submit() {
    const name = this.data.name.trim();
    if (name.length < 2) {
      wx.showToast({ title: '名称至少 2 个字', icon: 'none' });
      return;
    }
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
      setTimeout(() => wx.navigateBack(), 800);
    }).catch((err) => {
      wx.hideLoading();
      wx.showToast({ title: (err && err.detail) || '提交失败', icon: 'none' });
    });
  },
});
