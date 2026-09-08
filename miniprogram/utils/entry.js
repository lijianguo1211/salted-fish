/** 进门意图：organizer | member（本地记忆，不锁死身份） */
const KEY = 'sf_entry_intent';

function getIntent() {
  return wx.getStorageSync(KEY) || '';
}

function setIntent(intent) {
  if (intent === 'organizer' || intent === 'member') {
    wx.setStorageSync(KEY, intent);
  }
}

function clearIntent() {
  wx.removeStorageSync(KEY);
}

/** 是否展示「申请创建组织」 */
function canCreateOrg({ created = [], activeMembers = [], intent } = {}) {
  const i = intent !== undefined ? intent : getIntent();
  if ((activeMembers || []).some((m) => m.role === 'owner' || m.role === 'admin')) {
    return true;
  }
  if ((created || []).length > 0) return true;
  if (i === 'organizer') return true;
  return false;
}

module.exports = { getIntent, setIntent, clearIntent, canCreateOrg };
