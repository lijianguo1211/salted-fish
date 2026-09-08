// 腾讯云开发 AI（wx.cloud.extend.AI）统一封装
// 腾讯 AI 只能在小程序云环境里调用（自建 FastAPI 后端不允许），
// 所以把它收敛在本文件，业务页只关心「给 prompt，拿回文本/JSON」。
//
// 依赖：app.js 里已完成 wx.cloud.init({ env: CLOUD_ENV })
// 文档：https://docs.cloudbase.net/ai/model/miniprogram-access
const { AI_MODEL, AI_VISION_MODEL } = require('../config.js');

// 模型实例（lazy，避免在 wx.cloud 未就绪时创建）
let _model = null;
function model() {
  if (!wx.cloud || !wx.cloud.extend || !wx.cloud.extend.AI) {
    return null;
  }
  if (!_model) {
    _model = wx.cloud.extend.AI.createModel('cloudbase');
  }
  return _model;
}

function isAvailable() {
  return !!(wx.cloud && wx.cloud.extend && wx.cloud.extend.AI);
}

/**
 * 非流式文本生成：一次性拿回完整结果（适合自动分类、匹配、短问答）。
 * @param {string|Array} messagesOrPrompt 一条提示词，或 OpenAI 风格 messages 数组
 * @param {object} opts { system, model, temperature }
 * @returns {Promise<{ok:boolean, text:string, error?:string}>}
 */
async function generateText(messagesOrPrompt, opts = {}) {
  const m = model();
  if (!m) {
    return { ok: false, text: '', error: '云开发 AI 不可用（wx.cloud.extend.AI 未就绪）' };
  }
  const { model: modelName = AI_MODEL } = opts;
  const messages =
    typeof messagesOrPrompt === 'string'
      ? [
          ...(opts.system ? [{ role: 'system', content: opts.system }] : []),
          { role: 'user', content: messagesOrPrompt },
        ]
      : messagesOrPrompt;

  try {
    const res = await m.generateText({
      model: modelName,
      messages,
    });
    const text = (res && res.choices && res.choices[0] && res.choices[0].message
      && res.choices[0].message.content) || '';
    return { ok: !!text, text: (text || '').trim(), error: text ? '' : '模型返回为空' };
  } catch (e) {
    return { ok: false, text: '', error: (e && e.errMsg) || (e && e.message) || String(e) };
  }
}

/**
 * 多模态（看图）：消息 content 用对象数组，图片传公网 URL 或 base64 dataURL。
 * 视觉模型需在云开发控制台开启（推荐 glm-5v-turbo）。
 */
async function generateVision(prompt, imageUrls = [], opts = {}) {
  const m = model();
  if (!m) {
    return { ok: false, text: '', error: '云开发服务不可用' };
  }
  const content = [
    { type: 'text', text: prompt },
    ...(imageUrls || []).map((u) => ({
      type: 'image_url',
      image_url: { url: u },
    })),
  ];
  try {
    const res = await m.generateText({
      model: opts.model || AI_VISION_MODEL,
      messages: [
        ...(opts.system ? [{ role: 'system', content: opts.system }] : []),
        { role: 'user', content },
      ],
    });
    const text = (res && res.choices && res.choices[0] && res.choices[0].message
      && res.choices[0].message.content) || '';
    return { ok: !!text, text: text.trim(), error: text ? '' : '模型返回为空' };
  } catch (e) {
    return {
      ok: false,
      text: '',
      error: (e && e.errMsg) || (e && e.message) || String(e),
    };
  }
}

/** 从模型文本里解析出第一个 JSON 对象（兼容 ```json 包裹） */
function parseJson(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (e) {
    const m = text.match(/\{[\s\S]*\}/);
    if (m) {
      try {
        return JSON.parse(m[0]);
      } catch (e2) { /* ignore */ }
    }
  }
  return null;
}

module.exports = {
  isAvailable,
  generateText,
  generateVision,
  parseJson,
};