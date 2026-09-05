// FastAPI 请求封装：自动处理 base、token、错误。

const TOKEN_KEY = 'xianyu_admin_token';
const ADMIN_KEY = 'xianyu_admin_info';

// 生产可用 VITE_API_BASE 配置；开发走 /api 代理
const BASE = (import.meta.env.VITE_API_BASE as string) || '/api';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}
export function setAuth(token: string, admin: unknown): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ADMIN_KEY, JSON.stringify(admin));
}
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ADMIN_KEY);
}
export function getStoredAdmin(): any {
  try {
    return JSON.parse(localStorage.getItem(ADMIN_KEY) || 'null');
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : '请求失败');
    this.status = status;
    this.detail = detail;
  }
}

export async function request<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; query?: Record<string, any> } = {},
): Promise<T> {
  const token = getToken();
  const params: Record<string, string> = {};
  if (token) params.token = token;
  Object.entries(opts.query || {})
    .filter(([, v]) => v !== '' && v != null)
    .forEach(([k, v]) => (params[k] = String(v)));
  const qs = '?' + new URLSearchParams(params).toString();
  const res = await fetch(BASE + path + qs, {
    method: opts.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let detail: any = res.statusText;
    try {
      const j = await res.json();
      detail = (j && (j.detail || j.message)) || res.statusText;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}