// 全局配置
// 生产：指向已备案/可访问的 HTTPS 后端域名（需在微信公众平台配置 request/uploadFile 合法域名）
// 本地调试可临时改回：http://127.0.0.1:30089
const BASE_URL = 'https://mini.program.lglg.xyz/api';
const COIN_NAME = '咸鱼币';

// true = 真实微信登录（wx.login 拿 code；需后端 SALTED_FISH_DEMO=0 + WECHAT_APPID）
// false = 演示模式（本地设备 ID，不调微信）
// 线上/真机保持 true
const REAL_LOGIN = true;

// 腾讯云开发环境 ID（wx.cloud.extend.AI 必须在小程序云环境里调用）
// 在「微信开发者工具 → 云开发」控制台或个人中心里查看；若与你实际 ID 不一致，改成你控制台里显示的完整环境 ID
const CLOUD_ENV = 'jay-d0gb1ox70d165ca25';

// 云开发 AI 默认模型（在云开发控制台「AI → 生文模型」里开启后才可调用）
// 文本多用 hy3（腾讯混元）；视觉看图用 glm-5v-turbo
const AI_MODEL = 'hy3';
const AI_VISION_MODEL = 'glm-5v-turbo';

module.exports = {
  BASE_URL,
  COIN_NAME,
  REAL_LOGIN,
  CLOUD_ENV,
  AI_MODEL,
  AI_VISION_MODEL,
};