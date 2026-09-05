const api = require('../../utils/api.js');

Page({
  data: {
    tab: 'reports', // reports | categories
    reports: [],
    pendingCount: 0,
    // 分类管理
    categories: [],
    catFormShow: false,
    catId: null,
    catName: '',
    catCoins: 2,
    catNote: '',
    catOrder: 0,
    catActive: true,
    catSubmitting: false,
  },

  onShow() {
    if (this.data.tab === 'reports') this.loadReports();
    else this.loadCategories();
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ tab });
    if (tab === 'reports') this.loadReports();
    else this.loadCategories();
  },

  loadReports() {
    api
      .request('/admin/reports?status=pending')
      .then((reports) => {
        const list = (reports || []).map((r) => ({
          ...r,
          statusText: '待处理',
          item: r.item
            ? {
                ...r.item,
                images: (r.item.images || []).map((u) => api.BASE_URL + u),
              }
            : r.item,
        }));
        this.setData({ reports: list, pendingCount: list.length });
      })
      .catch((err) => wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' }));
  },

  // =================== 分类管理 ===================
  loadCategories() {
    api
      .request('/admin/categories')
      .then((categories) => {
        const list = (categories || []).map((c, i) => ({
          ...c,
          idx: String(i + 1),
          statusText: c.is_active ? '启用' : '停用',
        }));
        this.setData({ categories: list });
      })
      .catch((err) => wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' }));
  },

  openCatAdd() {
    this.setData({
      catFormShow: true,
      catId: null,
      catName: '',
      catCoins: 2,
      catNote: '',
      catOrder: 0,
      catActive: true,
      catSubmitting: false,
    });
  },

  openCatEdit(e) {
    const c = e.currentTarget.dataset.cat;
    this.setData({
      catFormShow: true,
      catId: c.id,
      catName: c.name,
      catCoins: c.value_base,
      catNote: c.note || '',
      catOrder: c.sort_order,
      catActive: c.is_active !== false,
      catSubmitting: false,
    });
  },

  closeCatForm() {
    this.setData({ catFormShow: false });
  },
  onCatName(e) { this.setData({ catName: e.detail.value }); },
  onCatCoins(e) { this.setData({ catCoins: Number(e.detail.value) || 0 }); },
  onCatNote(e) { this.setData({ catNote: e.detail.value }); },
  onCatOrder(e) { this.setData({ catOrder: Number(e.detail.value) || 0 }); },
  toggleCatActive(e) { this.setData({ catActive: e.detail.value }); },
  onCatKeep() {},

  saveCat() {
    const name = (this.data.catName || '').trim();
    if (!name) { wx.showToast({ title: '填个分类名', icon: 'none' }); return; }
    const payload = {
      name,
      value_base: this.data.catCoins,
      note: this.data.catNote,
      sort_order: this.data.catOrder,
      is_active: this.data.catActive,
    };
    this.setData({ catSubmitting: true });
    const url = this.data.catId
      ? `/admin/categories/${this.data.catId}`
      : '/admin/categories';
    api
      .request(url, { method: this.data.catId ? 'PUT' : 'POST', data: payload })
      .then(() => {
        this.setData({ catFormShow: false });
        wx.showToast({ title: '已保存', icon: 'success' });
        this.loadCategories();
      })
      .catch((err) => {
        this.setData({ catSubmitting: false });
        wx.showToast({ title: (err && err.detail) || '保存失败', icon: 'none' });
      });
  },

  deleteCat(e) {
    const c = e.currentTarget.dataset.cat;
    wx.showModal({
      title: '删除该分类？',
      content: '若有闲置仍在使用该分类，将无法删除（可改为停用）。确认删除？',
      confirmText: '删除',
      success: (res) => {
        if (!res.confirm) return;
        api
          .request(`/admin/categories/${c.id}`, { method: 'DELETE' })
          .then(() => {
            wx.showToast({ title: '已删除', icon: 'success' });
            this.loadCategories();
          })
          .catch((err) => wx.showToast({ title: (err && err.detail) || '删除失败', icon: 'none' }));
      },
    });
  },

  // =================== 举报处理 ===================
  rejectReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '驳回这条举报？',
      content: '驳回后，该物品会保持公开，且不再出现在待处理列表。',
      confirmText: '驳回',
      success: (res) => {
        if (!res.confirm) return;
        api
          .request(`/admin/reports/${id}`, {
            method: 'POST',
            data: { action: 'reject', reason: '管理员已核实，不构成违规' },
          })
          .then(() => {
            wx.showToast({ title: '已驳回', icon: 'success' });
            this.loadReports();
          })
          .catch((err) => wx.showToast({ title: (err && err.detail) || '操作失败', icon: 'none' }));
      },
    });
  },

  // 下架：移除该物品
  removeReport(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认下架？',
      content: '该物品将被下架，不再向其他人展示。',
      editable: true,
      placeholderText: '填一下下架原因（家长可见）',
      success: (res) => {
        if (!res.confirm) return;
        const reason = (res.content || '').trim() || '经管理员审核，内容不合规已下架';
        wx.showLoading({ title: '处理中...' });
        api
          .request(`/admin/reports/${id}`, {
            method: 'POST',
            data: { action: 'remove', reason },
          })
          .then(() => {
            wx.hideLoading();
            wx.showToast({ title: '已下架', icon: 'success' });
            this.loadReports();
          })
          .catch((err) => {
            wx.hideLoading();
            wx.showToast({ title: (err && err.detail) || '操作失败', icon: 'none' });
          });
      },
    });
  },
});