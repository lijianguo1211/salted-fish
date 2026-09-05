const api = require('../../../utils/api.js');

Page({
  data: { orgId: 0, inviteCode: '', pending: [], items: [] },

  onLoad(q) {
    this.setData({ orgId: Number(q.orgId || 0) });
  },

  onShow() {
    if (!this.data.orgId) return;
    this.reload();
  },

  reload() {
    const id = this.data.orgId;
    api.request('/orgs/current').then((res) => {
      if (res.org && res.org.id === id) {
        this.setData({ inviteCode: res.org.invite_code || '' });
      }
    }).catch(() => {});
    api.request(`/orgs/${id}/members`, { data: { status: 'pending' } })
      .then((list) => this.setData({ pending: list || [] }))
      .catch(() => this.setData({ pending: [] }));
    api.request(`/orgs/${id}/items`, { data: { status: 'all' } })
      .then((list) => this.setData({ items: list || [] }))
      .catch(() => this.setData({ items: [] }));
    // 若 current 不是本组织，单独拉 invite：用 members 接口鉴权后靠 refresh 展示
    api.request(`/orgs/mine`).then((res) => {
      const m = (res.memberships || []).find((x) => x.org_id === id && x.invite_code);
      if (m) this.setData({ inviteCode: m.invite_code });
    }).catch(() => {});
  },

  copyCode() {
    if (!this.data.inviteCode) return;
    wx.setClipboardData({ data: this.data.inviteCode });
  },

  refreshCode() {
    const id = this.data.orgId;
    wx.showLoading({ title: '刷新中...' });
    api.request(`/orgs/${id}/invite/refresh`, { method: 'POST' })
      .then((res) => {
        wx.hideLoading();
        this.setData({ inviteCode: res.invite_code || '' });
        wx.showToast({ title: '已刷新', icon: 'none' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '失败', icon: 'none' });
      });
  },

  handleMem(e) {
    const { id, action } = e.currentTarget.dataset;
    const orgId = this.data.orgId;
    wx.showLoading({ title: '处理中...' });
    api.request(`/orgs/${orgId}/members/${id}`, {
      method: 'POST',
      data: { action, note: '' },
    }).then(() => {
      wx.hideLoading();
      this.reload();
    }).catch((err) => {
      wx.hideLoading();
      wx.showToast({ title: (err && err.detail) || '失败', icon: 'none' });
    });
  },

  removeItem(e) {
    const itemId = e.currentTarget.dataset.id;
    const orgId = this.data.orgId;
    wx.showModal({
      title: '下架确认',
      content: '确定下架该闲置？组织内将不再展示。',
      success: (r) => {
        if (!r.confirm) return;
        api.request(`/orgs/${orgId}/items/${itemId}/remove`, {
          method: 'POST',
          data: { reason: '组织管理员下架' },
        }).then(() => {
          wx.showToast({ title: '已下架', icon: 'none' });
          this.reload();
        }).catch((err) => {
          wx.showToast({ title: (err && err.detail) || '失败', icon: 'none' });
        });
      },
    });
  },
});
