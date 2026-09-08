const api = require('../../utils/api.js');
const cloudAI = require('../../utils/cloud-ai.js');
const { iconOf } = require('../../utils/category-icons.js');

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
    // AI 撮合建议
    aiMatchLoading: false,
    aiAdvice: '',
    aiSuggestions: [],
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
            emoji: iconOf(item.category),
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
            emoji: iconOf(i.category),
            want_tags_text: (i.want_tags || []).join('、') || '什么都行',
          }));
        this.setData({ myItems: mine, showPicker: true });
      })
      .catch(() => wx.showToast({ title: '加载失败', icon: 'none' }));
  },

  closePicker() { this.setData({ showPicker: false }); },
  noop() {},

  // 接入点 C：AI 换物撮合建议 —— 我拿哪件闲置换眼前这件最合适
  aiSwapAdvice() {
    if (!cloudAI.isAvailable()) {
      wx.showModal({
        title: 'AI 暂不可用',
        content: '云开发 AI 未就绪：请确认已配置环境 ID 并开通云开发。',
        showCancel: false,
      });
      return;
    }
    if (!this.data.item) return;
    this.setData({ aiMatchLoading: true, aiAdvice: '', aiSuggestions: [] });
    wx.showLoading({ title: 'AI 撮合思考中...' });

    const target = this.data.item;
    // 我的闲置（含想要标签）
    const mineReq = api
      .request('/items/mine')
      .then((items) => (items || []).filter((i) => i.status === 'on_shelf'))
      .catch(() => []);

    mineReq.then((mine) => {
        const targetDesc =
          `对方物品：${target.name}（${target.category}，成色 ${target.condition || '未知'}，咸鱼币 ${target.value_coins || '?'}）` +
          `\n对方想换：${(target.want_tags || []).join('、') || '什么都行'}`;
        const mineDesc = mine.length
          ? mine
              .map(
                (i, idx) =>
                  `${idx + 1}. ${i.name}（${i.category}，${i.condition || '未知'}，币 ${i.value_coins || '?'}，我想换${(i.want_tags || []).join('、') || '什么都行'} | id:${i.id}）`
              )
              .join('\n')
          : '（我当前没有在架闲置）';
        const system =
          '你是「咸鱼小市场」的公平撮合助手，面向小学生以物换物平台。\n' +
          '根据“对方物品/对方想换”与“我方闲置/我方想换”，判断用哪件我方闲置去交换最合适、是否【公平】。\n' +
          '咸鱼币是荣誉积分（0–15），不是钱；交换要双方都受益才推荐。\n' +
          '只输出一个 JSON 对象：\n' +
          '{"match": 0到100的整数, "advice": "一句话建议", "suggestions": [{"id": 数字,"match": 0到100,"reason": "为什么推荐这件"}]}';
        const user =
          targetDesc + '\n---\n我的闲置：\n' + mineDesc + '\n请推荐用哪件闲置交换，返回 JSON。';

        return cloudAI
          .generateText(user, { system, temperature: 0.3 })
          .then((res) => {
            wx.hideLoading();
            this.setData({ aiMatchLoading: false });
            if (!res.ok) {
              wx.showToast({ title: res.error || 'AI 撮合失败', icon: 'none' });
              return;
            }
            const obj = cloudAI.parseJson(res.text);
            if (!obj) {
              wx.showToast({ title: 'AI 返回格式异常', icon: 'none' });
              return;
            }
            // 把 suggestion.id 对齐成可直接发起交换的闲置
            const suggestions = (obj.suggestions || [])
              .filter((s) => mine.some((m) => m.id === s.id))
              .map((s) => {
                const mi = mine.find((m) => m.id === s.id);
                return {
                  id: s.id,
                  name: mi.name,
                  reason: s.reason || '',
                  match: typeof s.match === 'number' ? s.match : 0,
                };
              });
            this.setData({
              aiAdvice: obj.advice || `综合匹配度 ${obj.match}%`,
              aiMatchLoading: false,
              aiSuggestions: suggestions,
              showPicker: false,
            });
          })
          .catch((err) => {
            wx.hide();
            this.setData({ aiMatchLoading: false });
            wx.showToast({ title: (err && err.detail) || '撮合失败，请重试', icon: 'none' });
          });
      });
  },

  // 点 AI 建议：直接用这件闲置发起交换
  aiUseSuggestion(e) {
    const id = e.currentTarget.dataset.id;
    if (!id || id === this.id) return;
    this.setData({ myItems: [] });
    wx.showLoading({ title: '发起中...' });
    api
      .request('/swaps', {
        method: 'POST',
        data: { initiator_item_id: id, receiver_item_id: this.id, note: '' },
      })
      .then(() => {
        wx.hideLoading();
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
          item: {
            ...this.data.item,
            value_coins: item.value_coins,
            ai_value_coins: item.ai_value_coins,
          },
        });
        wx.showToast({ title: '我的估值已更新', icon: 'success' });
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '保存失败', icon: 'none' });
      });
  },
});