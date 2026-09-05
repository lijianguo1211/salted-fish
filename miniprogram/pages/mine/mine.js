const api = require('../../utils/api.js');
const app = getApp();
const EMOJI = {
  '奥特曼卡': '🃏', '绘本/课外书': '📚', '玩具': '🧸',
  '文具': '✏️', '体育用品': '⚽', '其他': '🎁',
};
const ITEM_STATUS = { on_shelf: '上架中', off_shelf: '已下架', swapping: '交换中', swapped: '已换出' };

Page({
  data: {
    user: null,
    rules: [],
    myItems: [],
    ledger: [],
    isOrgAdmin: false,
    orgId: 0,
    orgName: '',
  },

  onShow() {
    const user = api.getUser();
    if (!user) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    if (!user.active_org_id) {
      wx.redirectTo({ url: '/pages/org/list/list' });
      return;
    }
    this.setData({ user, isOrgAdmin: false });
    this.refreshAll();
    this.loadMine();
    this.loadOrgAdmin();
  },

  loadOrgAdmin() {
    api.request('/orgs/current').then((res) => {
      const mem = res.membership;
      const isOrgAdmin = !!(mem && (mem.role === 'owner' || mem.role === 'admin'));
      this.setData({
        isOrgAdmin,
        orgId: (res.org && res.org.id) || 0,
        orgName: (res.org && res.org.name) || '',
      });
    }).catch(() => {});
  },

  goOrgs() {
    wx.navigateTo({ url: '/pages/org/list/list' });
  },

  goOrgManage() {
    if (!this.data.orgId) return;
    wx.navigateTo({ url: `/pages/org/manage/manage?orgId=${this.data.orgId}` });
  },

  refreshAll() {
    api.request('/auth/me').then((u) => {
      this.setData({ user: u });
      app.globalData.user = u;
      api.setSession(api.getToken(), u);
    });
  },

  loadMine() {
    api.request('/coins/rules').then((rules) => this.setData({ rules })).catch(() => {});
    api
      .request('/items/mine')
      .then((items) => {
        this.setData({
          myItems: (items || []).map((i) => ({
            ...i,
            emoji: EMOJI[i.category] || '🎁',
            statusText: ITEM_STATUS[i.status] || i.status,
          })),
        });
      })
      .catch(() => {});
    api
      .request('/coins/ledger')
      .then((ledger) => this.setData({ ledger }))
      .catch(() => {});
  },

  goItem(e) {
    wx.navigateTo({ url: `/pages/item-detail/item-detail?id=${e.currentTarget.dataset.id}` });
  },

  goAdmin() {
    wx.navigateTo({ url: '/pages/admin/admin' });
  },

  logout() {
    app.logout();
    wx.redirectTo({ url: '/pages/login/login' });
  },
});