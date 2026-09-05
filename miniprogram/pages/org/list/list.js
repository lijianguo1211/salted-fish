const api = require('../../../utils/api.js');
const app = getApp();

const ORG_TYPE = { school: '学校', community: '小区', other: '其他' };
const STATUS = { pending: '待平台审核', approved: '已通过', rejected: '未通过' };
const ROLE = { owner: '组织管理员', admin: '组织管理员', member: '成员' };

Page({
  data: {
    activeOrgId: 0,
    activeMembers: [],
    pendingMembers: [],
    created: [],
  },

  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    this.load();
  },

  load() {
    api.request('/orgs/mine').then((res) => {
      const memberships = res.memberships || [];
      const activeMembers = memberships
        .filter((m) => m.status === 'active' && m.org_status === 'approved')
        .map((m) => ({
          ...m,
          orgTypeText: ORG_TYPE[m.org_type] || m.org_type,
          roleText: ROLE[m.role] || m.role,
        }));
      const pendingMembers = memberships.filter((m) => m.status === 'pending');
      const created = (res.created || []).map((o) => ({
        ...o,
        statusText: STATUS[o.status] || o.status,
      }));
      this.setData({
        activeOrgId: res.active_org_id || 0,
        activeMembers,
        pendingMembers,
        created,
      });
    }).catch((err) => {
      wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' });
    });
  },

  switchOrg(e) {
    const id = e.currentTarget.dataset.id;
    if (id === this.data.activeOrgId) {
      this.goFish();
      return;
    }
    wx.showLoading({ title: '切换中...' });
    api.request('/orgs/switch', { method: 'POST', data: { org_id: id } })
      .then(() => api.request('/auth/me'))
      .then((u) => {
        api.setSession(api.getToken(), u);
        app.globalData.user = u;
        wx.hideLoading();
        wx.switchTab({ url: '/pages/index/index' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '切换失败', icon: 'none' });
      });
  },

  onCreatedTap(e) {
    const { id, status } = e.currentTarget.dataset;
    if (status === 'approved') {
      const mem = this.data.activeMembers.find((m) => m.org_id === id);
      if (mem && (mem.role === 'owner' || mem.role === 'admin')) {
        wx.navigateTo({ url: `/pages/org/manage/manage?orgId=${id}` });
      } else {
        this.switchOrg({ currentTarget: { dataset: { id } } });
      }
    }
  },

  goApply() { wx.navigateTo({ url: '/pages/org/apply/apply' }); },
  goJoin() { wx.navigateTo({ url: '/pages/org/join/join' }); },
  goFish() { wx.switchTab({ url: '/pages/index/index' }); },
});
