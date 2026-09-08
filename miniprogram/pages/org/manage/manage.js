const api = require('../../../utils/api.js');

Page({
  data: {
    orgId: 0,
    orgName: '',
    inviteCode: '',
    inviteEnabled: true,
    joinNeedReview: true,
    pending: [],
    items: [],
  },

  onLoad(q) {
    this.setData({ orgId: Number(q.orgId || 0) });
  },

  onShow() {
    if (!this.data.orgId) return;
    this.reload();
  },

  goFish() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  reload() {
    const id = this.data.orgId;
    api.request(`/orgs/${id}/invite`)
      .then((res) => {
        this.setData({
          orgName: res.org_name || '',
          inviteCode: res.invite_code || '',
          inviteEnabled: !!res.invite_enabled,
          joinNeedReview: !!res.join_need_review,
        });
      })
      .catch(() => {});
    api.request(`/orgs/${id}/members`, { data: { status: 'pending' } })
      .then((list) => this.setData({ pending: list || [] }))
      .catch(() => this.setData({ pending: [] }));
    api.request(`/orgs/${id}/items`, { data: { status: 'all' } })
      .then((list) => this.setData({ items: list || [] }))
      .catch(() => this.setData({ items: [] }));
  },

  saveSettings(patch) {
    const id = this.data.orgId;
    return api.request(`/orgs/${id}/settings`, { method: 'PUT', data: patch })
      .then((org) => {
        this.setData({
          inviteEnabled: !!org.invite_enabled,
          joinNeedReview: !!org.join_need_review,
          inviteCode: org.invite_code || '',
        });
      });
  },

  onInviteEnabled(e) {
    const on = !!e.detail.value;
    this.setData({ inviteEnabled: on });
    this.saveSettings({ invite_enabled: on })
      .then(() => wx.showToast({ title: on ? '已开启邀请' : '已关闭邀请', icon: 'none' }))
      .catch((err) => {
        this.setData({ inviteEnabled: !on });
        wx.showToast({ title: (err && err.detail) || '设置失败', icon: 'none' });
      });
  },

  onJoinNeedReview(e) {
    const on = !!e.detail.value;
    this.setData({ joinNeedReview: on });
    this.saveSettings({ join_need_review: on })
      .then(() => wx.showToast({ title: on ? '加入需审核' : '免审直接加入', icon: 'none' }))
      .catch((err) => {
        this.setData({ joinNeedReview: !on });
        wx.showToast({ title: (err && err.detail) || '设置失败', icon: 'none' });
      });
  },

  copyCode() {
    if (!this.data.inviteCode) return;
    wx.setClipboardData({ data: this.data.inviteCode });
  },

  refreshCode() {
    const id = this.data.orgId;
    wx.showModal({
      title: '换发邀请码',
      content: '旧邀请码将立即失效，确定换发？',
      success: (r) => {
        if (!r.confirm) return;
        wx.showLoading({ title: '换发中...' });
        api.request(`/orgs/${id}/invite/refresh`, { method: 'POST' })
          .then((res) => {
            wx.hideLoading();
            this.setData({
              inviteCode: res.invite_code || '',
              inviteEnabled: true,
            });
            wx.showToast({ title: '已换发', icon: 'none' });
          })
          .catch((err) => {
            wx.hideLoading();
            wx.showToast({ title: (err && err.detail) || '失败', icon: 'none' });
          });
      },
    });
  },

  invalidateCode() {
    if (!this.data.inviteCode) return;
    const id = this.data.orgId;
    wx.showModal({
      title: '使邀请码失效',
      content: '当前邀请码将清空，他人无法再用旧码加入。确定？',
      success: (r) => {
        if (!r.confirm) return;
        api.request(`/orgs/${id}/invite/invalidate`, { method: 'POST' })
          .then(() => {
            this.setData({ inviteCode: '' });
            wx.showToast({ title: '已失效', icon: 'none' });
          })
          .catch((err) => {
            wx.showToast({ title: (err && err.detail) || '失败', icon: 'none' });
          });
      },
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

  onShareAppMessage() {
    const code = this.data.inviteCode;
    const name = this.data.orgName || '组织';
    return {
      title: this.data.joinNeedReview
        ? `邀请你加入「${name}」，点开即可申请`
        : `邀请你加入「${name}」，点开即可进入`,
      path: `/pages/org/join/join?code=${code || ''}`,
    };
  },
});
