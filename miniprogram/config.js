// 全局配置
// 端口必须与你后端实际监听端口一致（当前后端在 30089，看 backend/.env 的 SALTED_FISH_PORT）
//  - 开发者工具模拟器：http://127.0.0.1:30089
//  - 真机/局域网：http://<本机局域网IP>:30089（后端需 0.0.0.0，已满足）
const BASE_URL = 'http://127.0.0.1:30089';  // ← 真机联调时改成 http://10.28.197.134:30089
const COIN_NAME = '咸鱼币';

// true = 真实微信登录（wx.login 拿 code；需后端 SALTED_FISH_DEMO=0 + WECHAT_APPID）
// false = 演示模式（code 传昵称；对应后端 SALTED_FISH_DEMO=1）
// 当前后端 DEMO_MODE=1，必须为 false
const REAL_LOGIN = false;

module.exports = {
  BASE_URL,
  COIN_NAME,
  REAL_LOGIN,
};