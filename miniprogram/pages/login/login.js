const app = getApp();

Page({
  data: {
    nickname: '',
    gradeClass: '三年级2班',
    school: '示范小学',
  },

  onNickname(e) { this.setData({ nickname: e.detail.value }); },
  onGradeClass(e) { this.setData({ gradeClass: e.detail.value }); },
  onSchool(e) { this.setData({ school: e.detail.value }); },

  doLogin() {
    const nickname = this.data.nickname.trim();
    if (!nickname) {
      wx.showToast({ title: '先给宝贝起个昵称吧', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '进入中...' });
    app
      .login(nickname, this.data.gradeClass, this.data.school)
      .then(() => {
        wx.hideLoading();
        // 登录后先进组织页：无组织需创建/加入，有组织可切换
        wx.redirectTo({ url: '/pages/org/list/list' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '登录失败', icon: 'none' });
      });
  },
});