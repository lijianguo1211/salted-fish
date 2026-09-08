const api = require('../../../utils/api.js');
const entry = require('../../../utils/entry.js');

Page({
  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    // 已有组织关系时，进列表枢纽，不再卡在选身份
    api.request('/orgs/mine').then((res) => {
      const memberships = res.memberships || [];
      const hasActive = memberships.some(
        (m) => m.status === 'active' && m.org_status === 'approved'
      );
      const hasPending = memberships.some((m) => m.status === 'pending');
      const hasCreated = (res.created || []).length > 0;
      if (hasActive || hasPending || hasCreated) {
        wx.redirectTo({ url: '/pages/org/list/list' });
      }
    }).catch(() => {});
  },

  chooseOrganizer() {
    entry.setIntent('organizer');
    wx.navigateTo({ url: '/pages/org/apply/apply' });
  },

  chooseMember() {
    entry.setIntent('member');
    wx.navigateTo({ url: '/pages/org/join/join' });
  },
});
