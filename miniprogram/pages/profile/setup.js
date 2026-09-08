const api = require('../../utils/api.js');
const app = getApp();

Page({
  data: {
    nickname: '',
    gradeClass: '',
    school: '',
  },

  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    api
      .request('/auth/me')
      .then((user) => {
        api.setSession(api.getToken(), user);
        app.globalData.user = user;
        if (!user.active_org_id) {
          wx.redirectTo({ url: '/pages/org/gate/gate' });
          return;
        }
        if (user.profile_completed) {
          app.enterHomeByRole(user);
          return;
        }
        this.setData({
          nickname:
            user.nickname && user.nickname !== '小咸鱼' && !/^demo-/i.test(user.nickname)
              ? user.nickname
              : '',
          gradeClass: user.grade_class || '',
          school: user.school || (user.active_org_name || ''),
        });
      })
      .catch(() => {
        wx.redirectTo({ url: '/pages/login/login' });
      });
  },

  onNickname(e) { this.setData({ nickname: e.detail.value }); },
  onGradeClass(e) { this.setData({ gradeClass: e.detail.value }); },
  onSchool(e) { this.setData({ school: e.detail.value }); },

  submit() {
    const nickname = this.data.nickname.trim();
    const gradeClass = this.data.gradeClass.trim();
    const school = this.data.school.trim();
    if (!nickname || nickname === '小咸鱼' || /^demo-/i.test(nickname)) {
      wx.showToast({ title: '请填写真实昵称', icon: 'none' });
      return;
    }
    if (!gradeClass) {
      wx.showToast({ title: '请填写真实班级', icon: 'none' });
      return;
    }
    if (!school) {
      wx.showToast({ title: '请填写真实学校', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '保存中...' });
    api
      .request('/auth/profile', {
        method: 'PUT',
        data: {
          nickname,
          grade_class: gradeClass,
          school,
        },
      })
      .then((u) => {
        api.setSession(api.getToken(), u);
        app.globalData.user = u;
        wx.hideLoading();
        app.enterHomeByRole(u);
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '保存失败', icon: 'none' });
      });
  },
});
