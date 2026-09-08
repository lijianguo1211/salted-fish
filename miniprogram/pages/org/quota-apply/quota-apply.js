const api = require('../../../utils/api.js');
const { BASE_URL } = require('../../../config.js');

Page({
  data: {
    quota: { used: 0, limit: 3, default_limit: 3 },
    requestedLimit: '5',
    reason: '',
    proofs: [], // 完整可预览 URL
    proofPaths: [], // 服务器相对路径 /uploads/xxx
  },

  onShow() {
    if (!api.getToken()) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    api.request('/orgs/create-quota')
      .then((q) => {
        const next = Math.min(50, (q.limit || 3) + 2);
        this.setData({
          quota: q,
          requestedLimit: String(next),
        });
      })
      .catch(() => {});
  },

  onLimit(e) { this.setData({ requestedLimit: e.detail.value }); },
  onReason(e) { this.setData({ reason: e.detail.value }); },

  addProof() {
    wx.chooseMedia({
      count: 5 - this.data.proofs.length,
      mediaType: ['image'],
      success: (res) => {
        const files = (res.tempFiles || []).map((f) => f.tempFilePath);
        if (!files.length) return;
        wx.showLoading({ title: '上传中...' });
        api.uploadFileAll(files)
          .then((urls) => {
            wx.hideLoading();
            const full = urls.map((u) => (u.startsWith('http') ? u : BASE_URL + u));
            this.setData({
              proofs: this.data.proofs.concat(full),
              proofPaths: this.data.proofPaths.concat(urls),
            });
          })
          .catch((err) => {
            wx.hideLoading();
            wx.showToast({ title: (err && err.detail) || '上传失败', icon: 'none' });
          });
      },
    });
  },

  delProof(e) {
    const i = e.currentTarget.dataset.i;
    const proofs = this.data.proofs.slice();
    const proofPaths = this.data.proofPaths.slice();
    proofs.splice(i, 1);
    proofPaths.splice(i, 1);
    this.setData({ proofs, proofPaths });
  },

  submit() {
    const reason = this.data.reason.trim();
    const requested = parseInt(this.data.requestedLimit, 10);
    if (!requested || requested <= (this.data.quota.limit || 0)) {
      wx.showToast({ title: '申请上限须大于当前额度', icon: 'none' });
      return;
    }
    if (reason.length < 20) {
      wx.showToast({ title: '原因请写满至少 20 字', icon: 'none' });
      return;
    }
    if (!this.data.proofPaths.length) {
      wx.showToast({ title: '请上传证明材料', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '提交中...' });
    api.request('/orgs/quota-applications', {
      method: 'POST',
      data: {
        reason,
        proof_urls: this.data.proofPaths,
        requested_limit: requested,
      },
    }).then(() => {
      wx.hideLoading();
      wx.showToast({ title: '已提交，等待审核', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 800);
    }).catch((err) => {
      wx.hideLoading();
      wx.showToast({ title: (err && err.detail) || '提交失败', icon: 'none' });
    });
  },
});
