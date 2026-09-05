import { request } from './client';

export const api = {
  // 登录（RSA-OAEP 加密密码传输 + email）
  login: (email: string, encryptedPassword: string) =>
    request('/admin-auth/login', { method: 'POST', body: { email, encrypted_password: encryptedPassword } }),
  publicKey: () => request<{ public_key: string }>('/admin-auth/public-key'),
  me: () => request('/admin-auth/me'),

  // 分类
  categories: () => request('/admin/categories'),
  createCategory: (body: any) => request('/admin/categories', { method: 'POST', body }),
  updateCategory: (id: number, body: any) =>
    request(`/admin/categories/${id}`, { method: 'PUT', body }),
  deleteCategory: (id: number) =>
    request(`/admin/categories/${id}`, { method: 'DELETE' }),

  // 举报
  reports: (status = 'pending') =>
    request('/admin/reports', { query: { status } }),
  handleReport: (id: number, body: any) =>
    request(`/admin/reports/${id}`, { method: 'POST', body }),

  // 物品
  items: (params: any) => request('/admin/items/all', { query: params }),
  setItemStatus: (id: number, status: string) =>
    request(`/admin/item/${id}/status`, { method: 'POST', query: { status } }),
  removeItem: (id: number) =>
    request(`/admin/item/${id}/remove`, { method: 'POST' }),

  // 孩子/积分
  users: (params: any) => request('/admin/users', { query: params }),
  toggleUser: (id: number) =>
    request(`/admin/user/${id}/toggle`, { method: 'POST' }),

  // 组织创建审核（日常管理在小程序）
  orgs: (status = 'pending') => request('/admin/orgs', { query: { status } }),
  reviewOrg: (id: number, body: any) =>
    request(`/admin/orgs/${id}/review`, { method: 'POST', body }),,

  // 大模型多 Key
  llmVendors: () => request('/admin/llm/vendors'),
  llmProviders: () => request('/admin/llm/providers'),
  createLlm: (body: any) => request('/admin/llm/providers', { method: 'POST', body }),
  updateLlm: (id: number, body: any) =>
    request(`/admin/llm/providers/${id}`, { method: 'PUT', body }),
  deleteLlm: (id: number) =>
    request(`/admin/llm/providers/${id}`, { method: 'DELETE' }),
  testLlm: (id: number) =>
    request(`/admin/llm/providers/${id}/test`, { method: 'POST' }),
};
