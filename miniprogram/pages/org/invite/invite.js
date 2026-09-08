const api = require('../../../utils/api.js');
const app = getApp();

Page({
  data: {
    orgId: 0,
    orgName: '',
    inviteCode: '',
    shareText: '',
    inviteEnabled: true,
    joinNeedReview: true,
  },

  onLoad(q) {
    const orgId = Number(q.orgId || 0);
    this.setData({ orgId });
  },

  onShow() {
    if (!app.ensureReady()) return;
    let orgId = this.data.orgId;
    const user = api.getUser() || {};
    if (!orgId) orgId = user.active_org_id || 0;
    if (!orgId) {
      wx.showToast({ title: '请先选择组织', icon: 'none' });
      return;
    }
    this.setData({ orgId });
    this.load();
  },

  load() {
    const id = this.data.orgId;
    api.request(`/orgs/${id}/invite`)
      .then((res) => {
        this.setData({
          orgName: res.org_name || '',
          inviteCode: res.invite_code || '',
          shareText: res.share_text || '',
          inviteEnabled: !!res.invite_enabled,
          joinNeedReview: res.join_need_review !== false,
        });
      })
      .catch((err) => {
        wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' });
      });
  },

  copyCode() {
    if (!this.data.inviteCode) return;
    wx.setClipboardData({ data: this.data.inviteCode });
  },

  copyShare() {
    const text = this.data.shareText || this.data.inviteCode;
    if (!text) return;
    wx.setClipboardData({ data: text });
  },

  onShareAppMessage() {
    const code = this.data.inviteCode;
    const name = this.data.orgName || '组织';
    const needReview = this.data.joinNeedReview;
    return {
      title: needReview
        ? `邀请你加入「${name}」，点开即可申请`
        : `邀请你加入「${name}」，点开即可进入`,
      path: `/pages/org/join/join?code=${code || ''}`,
    };
  },
});
