const cloudAI = require('../../utils/cloud-ai.js');
const { COIN_NAME } = require('../../config.js');

// 面向家长 / 老师的 AI 问答助手
// 接入点 B：用腾讯混元（wx.cloud.extend.AI）回答问题，回答前先讲清产品规则

const SYSTEM = [
  '你是「咸鱼小市场」的官方 AI 小助手，回答面向小学生家长和班主任关于这个以物换物平台的问题。',
  '产品规则（务必依据以下规则回答）：',
  '1. 这是孩子们“以物换物”的平台，不是买卖：只能用自家的闲置换别人的闲置，不接受“掏钱”买卖。',
  `2. ${COIN_NAME}是荣誉积分，不可兑现金、不可转账、不可买商品；完成一次交换双方各 +10。`,
  '3. 安全：每一次交换发起和接收，双方家长都要在弹出的“家长双确认”里确认才算数；异常取消会有扣分治理。',
  '4. 内容安全：上架物品会经过合规审核，烟酒、毒品、暴力等一律禁止；孩子资料只显示昵称和班级，保护隐私。',
  '5. 平台定位是“校园 / 邻里共建”的闲置互换，帮助培养分享与环保意识。',
  '回答要简短亲切（3–6 句），面向家长答疑即可。',
].join('\n');

const QUICK_QUESTIONS = [
  '怎么帮孩子开始用咸鱼小市场？',
  '家长怎么确认交换？',
  COIN_NAME + '能兑换现金吗？',
  '孩子想换别人的东西，流程是什么？',
];

Page({
  data: {
    messages: [],
    input: '',
    loading: false,
    quickQuestions: QUICK_QUESTIONS,
  },

  onLoad() {
    if (!cloudAI.isAvailable()) {
      this.append({
        role: 'assistant',
        content:
          '👋 你好，我是咸鱼小市场的 AI 小助手。\n（当前云开发 AI 未就绪，请先确认 config.js 里的环境 ID，以及云开发已开通、模型已开启。）',
      });
      return;
    }
    this.append({
      role: 'assistant',
      content:
        '👋 你好，我是「咸鱼小市场」的 AI 小助手。\n可以问我：如何物换物、家长怎么确认、咸鱼币是什么等等。',
    });
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  useQuick(e) {
    this.send(e.currentTarget.dataset.q);
  },

  //
  send(question) {
    // bindtanp / bindconfirm 会把 event 对象作为 question 传入，快捷按钮则传字符串。
    // 统一识别：是字符串就用它，否则退回输入框内容。
    const userText = typeof question === 'string' ? question : (this.data.input || '');
    const q = String(userText || '').trim();
    if (!q || this.data.loading) return;
    this.setData({ input: '', loading: true });

    // 1) 界面先展示用户消息
    this.append({ role: 'user', content: q });

    // 2) 组装多轮上下文：[system, ...历史(user+assistant)]
    const history = (this.data.messages || []).map((m) => ({
      role: m.role,
      content: m.content,
    }));
    const full = [{ role: 'system', content: SYSTEM }, ...history];

    // 3) 若非流式，一次性拿回答
    cloudAI
      .generateText(full, { temperature: 0.6 })
      .then((res) => {
        const text = res.ok ? res.text : '抱歉，我暂时回答不了，请稍后再试。';
        this.append({ role: 'assistant', content: text });
        this.setData({ loading: false });
      })
      .catch(() => {
        this.append({
          role: 'assistant',
          content: '抱歉，我暂时回答不了，请稍后再试。',
        });
        this.setData({ loading: false });
      });
  },

  append(m) {
    const messages = (this.data.messages || []).concat(m);
    this.setData({ messages });
    const page = this;
    setTimeout(() => {
      wx.createSelectorQuery()
        .select('#msgScroll')
        .boundingClientRect((r) => {
          if (r) wx.pageScrollTo({ scrollTop: r.height, duration: 200 });
        })
        .exec();
    }, 30);
  },
});