const api = require('../../utils/api.js');
const app = getApp();
const { iconOf } = require('../../utils/category-icons.js');
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
    if (!app.ensureReady()) return;
    const user = api.getUser();
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

  goInvite() {
    if (!this.data.orgId) return;
    wx.navigateTo({ url: `/pages/org/invite/invite?orgId=${this.data.orgId}` });
  },

  goOrgManage() {
    if (!this.data.orgId) return;
    wx.navigateTo({ url: `/pages/org/manage/manage?orgId=${this.data.orgId}` });
  },

  goFish() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  goAichat() {
    wx.navigateTo({ url: '/pages/aichat/aichat' });
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
            emoji: iconOf(i.category),
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