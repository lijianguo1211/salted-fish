const api = require('../../utils/api.js');

Page({
  data: {
    podium: [],
    rest: [],
    loaded: false,
    me: null,
  },

  onShow() {
    const app = getApp();
    if (!app.ensureReady()) return;
    const me = api.getUser();
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