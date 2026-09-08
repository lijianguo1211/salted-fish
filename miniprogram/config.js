// 全局配置
// 端口必须与你后端实际监听端口一致（当前后端在 30089，看 backend/.env 的 SALTED_FISH_PORT）
//  - 开发者工具模拟器：http://127.0.0.1:30089（当前用这个；后端 0.0.0.0 监听从本机可直连）
//  - 真机/局域网：http://<本机局域网IP>:30089（真机联调时改回局域网 IP）
const BASE_URL = 'http://127.0.0.1:30089';  // ← 当前在微信开发者工具里测，用本机地址
const COIN_NAME = '咸鱼币';

// true = 真实微信登录（wx.login 拿 code；需后端 SALTED_FISH_DEMO=0 + WECHAT_APPID）
// false = 演示模式（本地设备 ID，不调微信）
// 真机联调请保持 true
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