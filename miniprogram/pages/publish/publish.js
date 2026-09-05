const api = require('../../utils/api.js');

// 默认兜底分类（后端未返回时用；正常由管理员在后台配置）
const FALLBACK_CATS = ['奥特曼卡', '绘本/课外书', '玩具', '文具', '体育用品', '其他'];
const CONDITIONS = ['崭新', '九成新', '八成新', '七成新', '有磨损'];

Page({
  data: {
    cats: FALLBACK_CATS,
    conditions: CONDITIONS,
    catIndex: 0,
    imgs: [],
    name: '',
    condition: '九成新',
    wantTagsText: '',
    aiResult: null,
    coins: 3,
  },

  onShow() {
    const user = api.getUser();
    if (!user) {
      wx.redirectTo({ url: '/pages/login/login' });
      return;
    }
    if (!user.active_org_id) {
      wx.redirectTo({ url: '/pages/org/list/list' });
      return;
    }
    // 分类存数据库，管理员可配置；每次进来拉最新（含管理员停用后即时生效）
    api
      .request('/items/categories')
      .then((res) => {
        const list = (res && res.categories) || [];
        if (list.length) {
          const cats = list.map((c) => c.name);
          // 若当前选中下标超出，回退到 0
          this.setData({ cats, catIndex: this.data.catIndex < cats.length ? this.data.catIndex : 0 });
        }
      })
      .catch(() => {});
  },

  onName(e) { this.setData({ name: e.detail.value }); },
  onWant(e) { this.setData({ wantTagsText: e.detail.value }); },
  onCat(e) { this.setData({ catIndex: Number(e.detail.value) }); },
  setCondition(e) { this.setData({ condition: e.currentTarget.dataset.c }); },

  choosePhoto() {
    const remain = 3 - this.data.imgs.length;
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: (res) => {
        const paths = res.tempFiles.map((f) => f.tempFilePath);
        this.setData({ imgs: this.data.imgs.concat(paths) });
      },
    });
  },

  previewPhoto(e) {
    wx.previewImage({
      current: this.data.imgs[e.currentTarget.dataset.index],
      urls: this.data.imgs,
    });
  },

  delPhoto(e) {
    const i = e.currentTarget.dataset.index;
    const imgs = this.data.imgs.filter((_, idx) => idx !== i);
    this.setData({ imgs });
  },

  // AI 估价（携带已选图片一起送后端做视觉识别）
  aiEstimate() {
    if (!this.data.name.trim()) {
      wx.showToast({ title: '先填物品名称', icon: 'none' });
      return;
    }
    if (this.data.imgs.length && !this.data.uploaded) {
      // 先把临时图上传为可访问 URL，再送估值
      wx.showLoading({ title: '识别中...' });
      api
        .uploadFileAll(this.data.imgs)
        .then((urls) => {
          this.data.uploaded = urls;
          return this._callPricing(urls);
        })
        .then((res) => {
          wx.hideLoading();
          this.setData({ aiResult: res, coins: res.suggested_coins });
        })
        .catch((err) => {
          wx.hideLoading();
          wx.showToast({ title: (err && err.detail) || '估值失败', icon: 'none' });
        });
      return;
    }
    this._callPricing(this.data.uploaded || []).then((res) => {
      this.setData({ aiResult: res, coins: res.suggested_coins });
    });
  },

  _callPricing(imageUrls) {
    return api.request('/items/ai-pricing', {
      method: 'POST',
      data: {
        name: this.data.name,
        category: this.data.cats[this.data.catIndex],
        description: '',
        condition: this.data.condition,
        image_urls: imageUrls || [],
      },
    });
  },

  decCoins() {
    if (this.data.coins > 0) this.setData({ coins: this.data.coins - 1 });
  },
  incCoins() {
    if (this.data.coins < 15) this.setData({ coins: this.data.coins + 1 });
  },

  submit() {
    const { name, condition, imgs, wantTagsText, catIndex, coins } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '写个物品名称吧', icon: 'none' });
      return;
    }
    const wantTags = wantTagsText.split(/[、,，]/).map((s) => s.trim()).filter(Boolean);

    wx.showLoading({ title: '上架中...' });
    // 先上传图片（若还没上传过）
    const uploadPromise = this.data.uploaded
      ? Promise.resolve(this.data.uploaded)
      : imgs.length
        ? api.uploadFileAll(imgs)
        : Promise.resolve([]);

    uploadPromise
      .then((urls) =>
        api.request('/items', {
          method: 'POST',
          data: {
            name: name.trim(),
            category: this.data.cats[catIndex],
            condition,
            description: '',
            images: urls,
            want_tags: wantTags,
            value_coins: coins, // AI 建议值，可手动微调
          },
        })
      )
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '上架成功 ＋2🐟', icon: 'success' });
        setTimeout(() => wx.navigateBack({ delta: 1 }), 800);
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '上架失败', icon: 'none' });
      });
  },
});