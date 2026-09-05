const api = require('../../utils/api.js');

Page({
  data: {
    podium: [],
    rest: [],
    loaded: false,
    me: null,
  },

  onShow() {
    const me = api.getUser();
    if (!me) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    if (!me.active_org_id) {
      wx.redirectTo({ url: '/pages/org/list/list' });
      return;
    }
    this.setData({ me });
    api
      .request('/coins/leaderboard')
      .then((res) => {
        const board = res.leaderboard || [];
        this.setData({
          podium: board.slice(0, 3),
          rest: board.slice(3).map((r, i) => ({ ...r, key: i })),
          loaded: true,
        });
      })
      .catch(() => this.setData({ loaded: true, podium: [], rest: [] }));
  },
});