import { useState } from 'react';
import { api } from '../api';
import { setAuth } from '../api/client';
import { rsaEncryptPassword } from '../api/crypto';

export default function Login({ onAuth }: { onAuth: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!email || !password) { setErr('请填写邮箱和密码'); return; }
    setLoading(true);
    setErr('');
    try {
      // 先取 RSA 公钥，用公钥加密密码后再发送（密码不明文过网）
      const pk = await api.publicKey();
      const encrypted = await rsaEncryptPassword(pk.public_key, password);
      const res = await api.login(email, encrypted);
      setAuth(res.token, res.admin);
      onAuth();
    } catch (e: any) {
      setErr(e.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <h1>🥇 咸鱼小市场</h1>
        <div className="sub">独立管理后台 · 管理员登录</div>
        <label>管理员邮箱</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)}
               placeholder="admin@example.com" autoComplete="username" />
        <label>密码</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
               placeholder="请输入密码" autoComplete="current-password"
               onKeyDown={(e) => e.key === 'Enter' && submit()} />
        <div className="err">{err}</div>
        <button style={{ width: '100%', marginTop: 6 }} onClick={submit} disabled={loading}>
          {loading ? '登录中...' : '登录'}
        </button>
      </div>
    </div>
  );
}