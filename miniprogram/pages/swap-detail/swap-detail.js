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
  data: { swap: null, steps: [] },
  onLoad(o) { this.id = o.id; },
  onShow() { this.load(); },

  load() {
    api
      .request(`/swaps/${this.id}`)
      .then((s) => {
        const me = api.getUser();
        let mySide = '';
        if (me) {
          if (me.id === s.initiator_item.owner_id) mySide = 'initiator';
          else if (me.id === s.receiver_item.owner_id) mySide = 'receiver';
        }
        const myConfirmed =
          mySide === 'initiator' ? s.initiator_parent_confirmed : s.receiver_parent_confirmed;
        const myCompleted =
          mySide === 'initiator' ? s.initiator_parent_completed : s.receiver_parent_completed;
        const activeStatus = ['pending_parent', 'pending_peer', 'accepted'].includes(s.status);

        const swap = {
          ...s,
          initiator_item: { ...s.initiator_item, emoji: iconOf(s.initiator_item.category) },
          receiver_item: { ...s.receiver_item, emoji: iconOf(s.receiver_item.category) },
          mySide,
          statusText: STATUS_TEXT[s.status] || s.status,
          needMyConfirm: activeStatus && !myConfirmed,
          needMyComplete: s.status === 'accepted' && mySide && !myCompleted,
          canCancel: activeStatus,
        };
        const steps = [
          { key: 'req', title: '发起交换请求', done: true, time: s.created_at },
          { key: 'init', title: '发起方家长确认', done: s.initiator_parent_confirmed, time: '' },
          { key: 'rec', title: '接收方家长确认', done: s.receiver_parent_confirmed, time: '' },
          { key: 'swapped', title: '线下当面交换', done: s.status === 'completed', time: s.completed_at },
          {
            key: 'ok',
            title: '双方点「交换完成」',
            done: s.initiator_parent_completed && s.receiver_parent_completed,
            time: s.completed_at,
          },
        ];
        this.setData({ swap, steps });
      })
      .catch((err) => wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' }));
  },

  do(action, tip) {
    wx.showLoading({ title: tip });
    api
      .request(`/swaps/${this.id}/actions`, { method: 'POST', data: { action } })
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '操作成功 ✔', icon: 'success' });
        this.load();
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '操作失败', icon: 'none' });
      });
  },
  confirm() { this.do('parent_confirm', '确认中...'); },
  complete() { this.do('complete', '提交中...'); },
  cancel() {
    wx.showModal({
      title: '取消交换？',
      content: '发起方取消会扣 2 咸鱼币',
      success: (r) => r.confirm && this.do('cancel', '取消中...'),
    });
  },
});