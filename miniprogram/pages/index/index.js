const api = require('../../utils/api.js');
const app = getApp();

const CATS = ['奥特曼卡', '绘本/课外书', '玩具', '文具', '体育用品', '其他'];
const EMOJI = {
  '奥特曼卡': '🃏',
  '绘本/课外书': '📚',
  '玩具': '🧸',
  '文具': '✏️',
  '体育用品': '⚽',
  '其他': '🎁',
};

Page({
  data: {
    user: null,
    orgName: '',
    items: [],
    loaded: false,
    activeCat: '',
    cats: CATS,
    // 举报弹层
    showReport: false,
    reportItemId: null,
    reportItemName: '',
    reportReasons: [],
    reportReason: '',
    reportReasonIndex: -1,
    reportNote: '',
  },

  onShow() {
    const user = app.globalData.user || api.getUser();
    if (!user) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    if (!user.active_org_id) {
      wx.redirectTo({ url: '/pages/org/list/list' });
      return;
    }
    this.setData({
      user,
      orgName: user.active_org_name || '当前组织',
    });
    // 刷新用户（组织名可能刚切换过）
    api.request('/auth/me').then((u) => {
      api.setSession(api.getToken(), u);
      app.globalData.user = u;
      if (!u.active_org_id) {
        wx.redirectTo({ url: '/pages/org/list/list' });
        return;
      }
      this.setData({ user: u, orgName: u.active_org_name || '当前组织' });
    }).catch(() => {});
    this.loadCategories();
    this.loadItems();
  },

  goOrgs() {
    wx.navigateTo({ url: '/pages/org/list/list' });
  },

  // 分类存数据库，管理员可配置；拉最新并保持当前选中有效
  loadCategories() {
    api
      .request('/items/categories')
      .then((res) => {
        const list = (res && res.categories) || [];
        if (list.length) {
          this.setData({ cats: list.map((c) => c.name) });
        }
      })
      .catch(() => {});
  },

  setCat(e) {
    const cat = e.currentTarget.dataset.cat;
    const activeCat = this.data.activeCat === cat ? '' : cat;
    this.setData({ activeCat }, () => {
      this.loadItems();
    });
  },

  goSearch() {
    wx.navigateTo({ url: '/pages/publish/publish?search=1' });
  },

  openItem(e) {
    wx.navigateTo({ url: `/pages/item-detail/item-detail?id=${e.currentTarget.dataset.id}` });
  },

  goPublish() {
    wx.navigateTo({ url: '/pages/publish/publish' });
  },

  // ---- 列表页举报 ----
  openReportList(e) {
    const id = e.currentTarget.dataset.id;
    const name = e.currentTarget.dataset.name;
    if (this.data.reportReasons.length === 0) {
      api.request('/items/report-reasons').then((res) => {
        this.setData({
          reportItemId: id,
          reportItemName: name,
          reportReasons: res.reasons || [],
          showReport: true,
        });
      }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }));
    } else {
      this.setData({ reportItemId: id, reportItemName: name, showReport: true });
    }
  },

  closeReport() { this.setData({ showReport: false }); },
  noop() {},
  pickReason(e) {
    const idx = e.currentTarget.dataset.idx;
    this.setData({ reportReason: this.data.reportReasons[idx], reportReasonIndex: idx });
  },
  onReportNote(e) { this.setData({ reportNote: e.detail.value }); },

  submitReportList() {
    if (!this.data.reportItemId) { wx.showToast({ title: '请先选择物品', icon: 'none' }); return; }
    if (this.data.reportReasonIndex < 0) { wx.showToast({ title: '请先选择举报理由', icon: 'none' }); return; }
    wx.showLoading({ title: '提交中...' });
    api
      .request(`/items/${this.data.reportItemId}/report`, {
        method: 'POST',
        data: { reason: this.data.reportReason, note: this.data.reportNote },
      })
      .then(() => {
        wx.hideLoading();
        this.setData({ showReport: false, reportNote: '' });
        wx.showToast({ title: '已提交，管理员会处理', icon: 'none' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '举报失败', icon: 'none' });
      });
  },

  loadItems() {
    const cat = this.data.activeCat;
    const token = api.getToken();
    api
      .request('/items', { data: { category: cat, status: 'on_shelf' } })
      .then((items) => {
        // 合并 want_tags 展示 + 补全图片绝对地址
        const list = (items || []).map((it) => {
          const tags = it.want_tags || [];
          let txt = tags.join('、');
          if (!txt) txt = '什么都行';
          return {
            ...it,
            want_tags_text: txt.length > 16 ? txt.slice(0, 16) + '…' : txt,
            emoji: EMOJI[it.category] || '🎁',
            images: (it.images || []).map((u) => api.BASE_URL + u),
          };
        });
        this.setData({ items: list, loaded: true });
      })
      .catch(() => {
        this.setData({ items: [], loaded: true });
      });
  },
});