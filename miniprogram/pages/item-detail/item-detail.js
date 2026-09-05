const api = require('../../utils/api.js');
const EMOJI = {
  '奥特曼卡': '🃏', '绘本/课外书': '📚', '玩具': '🧸',
  '文具': '✏️', '体育用品': '⚽', '其他': '🎁',
};

Page({
  data: {
    item: null,
    wantTags: [],
    isMine: false,
    showPicker: false,
    myItems: [],
    user: null,
    // 举报
    showReport: false,
    reportReasons: [],
    reportReason: '',
    reportReasonIndex: -1,
    reportNote: '',
    // 修改价值
    showEditValue: false,
    editCoins: 0,
  },

  onLoad(options) {
    this.id = options.id;
  },

  onShow() {
    this.loadItem();
  },

  loadItem() {
    const user = api.getUser();
    this.setData({ user });
    api
      .request(`/items/${this.id}`)
      .then((item) => {
        const wantTags = item.want_tags || [];
        const tagsText = wantTags.join('、') || '什么都行';
        this.setData({
          item: {
            ...item,
            emoji: EMOJI[item.category] || '🎁',
            want_tags_text: tagsText,
            images: (item.images || []).map((u) => api.BASE_URL + u),
          },
          wantTags,
          isMine: user && user.id === item.owner_id,
        });
      })
      .catch((err) => wx.showToast({ title: (err.detail) || '加载失败', icon: 'none' }));
  },

  // ---- 举报 ----
  openReport() {
    if (this.data.reportReasons.length === 0) {
      api.request('/items/report-reasons').then((res) => {
        this.setData({
          reportReasons: res.reasons || [],
          showReport: true,
        });
      }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }));
    } else {
      this.setData({ showReport: true });
    }
  },

  closeReport() { this.setData({ showReport: false }); },
  pickReason(e) {
    const idx = e.currentTarget.dataset.idx;
    this.setData({ reportReason: this.data.reportReasons[idx], reportReasonIndex: idx });
  },
  onReportNote(e) { this.setData({ reportNote: e.detail.value }); },

  submitReport() {
    if (this.data.reportReasonIndex < 0) {
      wx.showToast({ title: '请先选择举报理由', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '提交中...' });
    api
      .request(`/items/${this.id}/report`, {
        method: 'POST',
        data: { reason: this.data.reportReason, note: this.data.reportNote },
      })
      .then(() => {
        wx.hideLoading();
        this.setData({ showReport: false });
        wx.showToast({ title: '已提交，管理员会尽快处理', icon: 'none' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '举报失败', icon: 'none' });
      });
  },

  openSwap() {
    // 加载我的闲置
    api
      .request('/items/mine')
      .then((items) => {
        const mine = items
          .filter((i) => i.status === 'on_shelf' && i.id !== this.id)
          .map((i) => ({
            ...i,
            emoji: EMOJI[i.category] || '🎁',
            want_tags_text: (i.want_tags || []).join('、') || '什么都行',
          }));
        this.setData({ myItems: mine, showPicker: true });
      })
      .catch(() => wx.showToast({ title: '加载失败', icon: 'none' }));
  },

  closePicker() { this.setData({ showPicker: false }); },
  noop() {},

  confirmSwap(e) {
    const initiatorItemId = e.currentTarget.dataset.id;
    const receiverItemId = this.id;
    wx.showLoading({ title: '发起中...' });
    api
      .request('/swaps', {
        method: 'POST',
        data: { initiator_item_id: initiatorItemId, receiver_item_id: receiverItemId, note: '' },
      })
      .then(() => {
        wx.hideLoading();
        this.setData({ showPicker: false });
        wx.showModal({
          title: '交换请求已发出 🎉',
          content: '已通知对方家长确认。你这边也记得让家长在「交换」页点确认哦。',
          showCancel: false,
          confirmText: '知道了',
          success: () => wx.switchTab({ url: '/pages/swap-list/swap-list' }),
        });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '发起失败', icon: 'none' });
      });
  },

  removeItem() {
    wx.showModal({
      title: '下架这件闲置？',
      content: '下架后其他人就无法再浏览啦',
      success: (res) => {
        if (res.confirm) {
          api
            .request(`/items/${this.id}`, { method: 'PUT', data: { status: 'off_shelf' } })
            .then(() => {
              wx.showToast({ title: '已下架', icon: 'success' });
              setTimeout(() => wx.navigateBack(), 700);
            })
            .catch((err) => wx.showToast({ title: (err.detail) || '失败', icon: 'none' }));
        }
      },
    });
  },

  // ---- 修改自己的闲置价值 ----
  openEditValue() {
    this.setData({ showEditValue: true, editCoins: this.data.item.value_coins || 0 });
  },
  closeEditValue() { this.setData({ showEditValue: false }); },
  evDec() {
    if (this.data.editCoins > 0) this.setData({ editCoins: this.data.editCoins - 1 });
  },
  evInc() {
    if (this.data.editCoins < 15) this.setData({ editCoins: this.data.editCoins + 1 });
  },
  saveValue() {
    wx.showLoading({ title: '保存中...' });
    api
      .request(`/items/${this.id}`, { method: 'PUT', data: { value_coins: this.data.editCoins } })
      .then((item) => {
        wx.hideLoading();
        this.setData({
          showEditValue: false,
          item: { ...this.data.item, value_coins: item.value_coins },
        });
        wx.showToast({ title: '价值已更新', icon: 'success' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '保存失败', icon: 'none' });
      });
  },
});