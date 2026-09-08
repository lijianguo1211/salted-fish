const api = require('../../utils/api.js');
const cloudAI = require('../../utils/cloud-ai.js');

// 默认兜底分类（后端未返回时用；正常由管理员在后台配置）
const { FALLBACK_CATS } = require('../../utils/category-icons.js');
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
    aiPricingEnabled: true,
    aiModerationEnabled: false,
    aiFilling: false,
  },

  onShow() {
    const app = getApp();
    if (!app.ensureReady()) return;
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
    api
      .request('/items/ai-settings', { auth: false })
      .then((s) => {
        this.setData({
          aiPricingEnabled: s.ai_pricing_enabled !== false,
          aiModerationEnabled: !!s.ai_moderation_enabled,
        });
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

  // 接入点 A：腾讯混元 AI 智能填写（自动分类 + 成色 + “想换”推荐）
  aiFill() {
    if (!cloudAI.isAvailable()) {
      wx.showModal({
        title: 'AI 暂不可用',
        content: '云开发 AI 未就绪：请确认已开通云开发并在 app.js/config.js 配好环境 ID。',
        showCancel: false,
      });
      return;
    }
    if (!this.data.name.trim()) {
      wx.showToast({ title: '先填物品名称，AI 才好识别', icon: 'none' });
      return;
    }
    this.setData({ aiFilling: true });
    wx.showLoading({ title: 'AI 智能填写中...' });
    const catOptions = this.data.cats.join('、');
    const system = [
      '你是「咸鱼小市场」的闲置描述助手，面向小学生以物换物平台。',
      '根据物品名称（可选成色）自动判断：类别、成色、以及合理的"想换"建议。',
      `可选类别严格限定为：${catOptions}。成色在：崭新、九成新、八成新、七成新、有磨损 里选。`,
      '只输出一个 JSON 对象，不要任何多余文字：',
      '{"category":"类别","condition":"成色","want":"一句话想换什么","reason":"一句话说明"}',
    ].join('\n');
    const user = `物品名称：${this.data.name}\n成色：${this.data.condition || '未知'}\n请返回 JSON。`;

    cloudAI
      .generateText(user, { system })
      .then((res) => {
        if (!res.ok) {
          throw { detail: res.error || 'AI 填写失败' };
        }
        const obj = cloudAI.parseJson(res.text);
        if (!obj) throw { detail: 'AI 返回格式异常，请稍后再试' };
        // 分类严格匹配下拉选项
        let catIndex = this.data.catIndex;
        if (obj.category) {
          const idx = this.data.cats.indexOf(obj.category);
          if (idx >= 0) catIndex = idx;
        }
        const conditions = this.data.conditions;
        let condition = this.data.condition;
        if (obj.condition && conditions.indexOf(obj.condition) >= 0) {
          condition = obj.condition;
        }
        const patch = { aiFilling: false, catIndex, condition };
        if (obj.want && !this.data.wantTagsText) patch.wantTagsText = obj.want;
        this.setData(patch);
        wx.hideLoading();
        wx.showToast({
          title: obj.reason ? '✅ ' + obj.reason : 'AI 已帮您填好了',
          icon: 'none',
        });
      })
      .catch((err) => {
        this.setData({ aiFilling: false });
        wx.hideLoading();
        wx.showToast({ title: (err && err.detail) || '填写失败，请重试', icon: 'none' });
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
    if (!this.data.aiPricingEnabled) {
      wx.showToast({ title: '平台未开启 AI 估值', icon: 'none' });
      return;
    }
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

    wx.showLoading({ title: this.data.aiModerationEnabled ? '合规检测中...' : '上架中...' });
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
        const detail = (err && err.detail) || '上架失败';
        if (typeof detail === 'string' && detail.length > 20) {
          wx.showModal({ title: '无法上架', content: detail, showCancel: false });
        } else {
          wx.showToast({ title: detail, icon: 'none' });
        }
      });
  },
});