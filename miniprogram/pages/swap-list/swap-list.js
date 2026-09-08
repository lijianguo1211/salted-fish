const api = require('../../utils/api.js');
const { iconOf } = require('../../utils/category-icons.js');
const STATUS_TEXT = {
  pending_parent: '等待发起方家长确认',
  pending_peer: '等待接收方家长确认',
  accepted: '已确认 · 待线下交换',
  completed: '已完成',
  cancelled: '已取消',
};

Page({
  data: {
    tab: 'all',
    swaps: [],
    loaded: false,
    user: null,
  },

  onShow() {
    const app = getApp();
    if (!app.ensureReady()) return;
    const user = api.getUser();
    this.setData({ user });
    this.load();
  },

  load() {
    const tab = this.data.tab;
    api
      .request('/swaps')
      .then((swaps) => {
        const me = this.data.user;
        const list = (swaps || [])
          .map((s) => this.decorate(s, me))
          .filter((s) => {
            if (tab === 'all') return true;
            if (tab === 'todo') return s.needMyConfirm && s.status !== 'cancelled';
            if (tab === 'doing') return s.status === 'accepted';
            if (tab === 'done') return s.status === 'completed';
            return true;
          });
        this.setData({ swaps: list, loaded: true });
      })
      .catch(() => this.setData({ swaps: [], loaded: true }));
  },

  decorate(s, me) {
    const ii = s.initiator_item;
    const ri = s.receiver_item;
    // 我的角色
    let mySide = '';
    if (me) {
      if (me.id === ii.owner_id) mySide = 'initiator';
      else if (me.id === ri.owner_id) mySide = 'receiver';
    }
    const initiator_ok = s.initiator_parent_confirmed;
    const receiverOk = s.receiver_parent_confirmed;
    const myConfirmed =
      mySide === 'initiator' ? s.initiator_parent_confirmed : s.receiver_parent_confirmed;
    const myCompleted =
      mySide === 'initiator' ? s.initiator_parent_completed : s.receiver_parent_completed;

    const activeStatus = ['pending_parent', 'pending_peer', 'accepted'].includes(s.status);
    const needMyConfirm = activeStatus && !myConfirmed;
    const canComplete = s.status === 'accepted' && mySide;
    const needMyComplete = canComplete && !myCompleted;

    return {
      ...s,
      mySide,
      initiator_item: { ...ii, emoji: iconOf(ii.category) },
      receiver_item: { ...ri, emoji: iconOf(ri.category) },
      initiator_ok,
      receiver_ok: receiverOk,
      statusText: STATUS_TEXT[s.status] || s.status,
      needMyConfirm,
      canComplete,
      needMyComplete,
      canCancel: activeStatus,
    };
  },

  setTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab }, () => this.load());
  },

  openDetail(e) {
    wx.navigateTo({ url: `/pages/swap-detail/swap-detail?id=${e.currentTarget.dataset.id}` });
  },

  // 家长确认
  confirmIt(e) {
    const { id } = e.currentTarget.dataset;
    wx.showLoading({ title: '确认中...' });
    api
      .request(`/swaps/${id}/actions`, { method: 'POST', data: { action: 'parent_confirm' } })
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '已确认 ✔', icon: 'success' });
        this.load();
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '确认失败', icon: 'none' });
      });
  },

  completeIt(e) {
    const { id } = e.currentTarget.dataset;
    wx.showLoading({ title: '提交中...' });
    api
      .request(`/swaps/${id}/actions`, { method: 'POST', data: { action: 'complete' } })
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '完成 ✔ +10🐟', icon: 'success' });
        this.load();
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '提交失败', icon: 'none' });
      });
  },

  cancelIt(e) {
    const { id } = e.currentTarget.dataset;
    wx.showModal({
      title: '取消这次交换？',
      content: '取消会解锁双方闲置。若你是发起方，会扣 2 枚咸鱼币。',
      success: (res) => {
        if (res.confirm) {
          api
            .request(`/swaps/${id}/actions`, {
              method: 'POST',
              data: { action: 'cancel', reason: '用户取消' },
            })
            .then(() => {
              wx.showToast({ title: '已取消', icon: 'none' });
              this.load();
            })
            .catch((err) =>
              wx.showToast({ title: (err && err.detail) || '取消失败', icon: 'none' })
            );
        }
      },
    });
  },
});