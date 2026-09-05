// 请求封装 + tokens 存储
// config.js 在 miniprogram/ 根目录，本文件在 utils/ 下，用 ../ 上跳一级
const { BASE_URL, REAL_LOGIN } = require('../config.js');

const TOKEN_KEY = 'sf_token';
const USER_KEY = 'sf_user';

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function setSession(token, user) {
  wx.setStorageSync(TOKEN_KEY, token);
  if (user) wx.setStorageSync(USER_KEY, JSON.stringify(user));
}

function getUser() {
  try {
    return JSON.parse(wx.getStorageSync(USER_KEY) || 'null');
  } catch (e) {
    return null;
  }
}

function clearSession() {
  wx.removeStorageSync(TOKEN_KEY);
  wx.removeStorageSync(USER_KEY);
}

// 通用请求
function request(path, { method = 'GET', data = {}, auth = true } = {}) {
  return new Promise((resolve, reject) => {
    const token = getToken();
    const query = auth
      ? `${path}${path.includes('?') ? '&' : '?'}token=${token}`
      : path;
    wx.request({
      url: BASE_URL + query,
      method,
      data,
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode === 401) {
          clearSession();
          // 需要重新登录
          wx.navigateTo({ url: '/pages/index/index?needLogin=1' });
          reject(res.data);
          return;
        }
        if (res.statusCode >= 400) {
          reject(res.data || { detail: '请求失败' });
          return;
        }
        resolve(res.data);
      },
      fail(err) {
        reject({ detail: `网络错误: ${err.errMsg}` });
      },
    });
  });
}

// 上传图片（本地临时路径 -> 服务器 URL）
function uploadFile(filePath) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE_URL + '/upload',
      filePath,
      name: 'file',
      header: { token: getToken() },
      success(res) {
        if (res.statusCode >= 400) {
          reject({ detail: '上传失败' });
          return;
        }
        try {
          const data = JSON.parse(res.data);
          resolve(data.url); // /uploads/xxx.png
        } catch (e) {
          reject({ detail: '上传返回异常' });
        }
      },
      fail(err) {
        reject({ detail: `上传网络错误: ${err.errMsg}` });
      },
    });
  });
}

// 批量上传多张图片，返回 URL 数组
async function uploadFileAll(filePaths) {
  const urls = [];
  for (const p of filePaths) {
    urls.push(await uploadFile(p));
  }
  return urls;
}

module.exports = {
  BASE_URL,
  TOKEN_KEY,
  USER_KEY,
  getToken,
  getUser,
  setSession,
  clearSession,
  request,
  uploadFile,
  uploadFileAll,
};