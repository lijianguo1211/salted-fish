// 用后端的 RSA 公钥做 RSA-OAEP(SHA-256) 加密，把密码密文交给后端。
// 纯 Web Crypto API，无需第三方加密库。

function pemToArrayBuffer(pem: string): ArrayBuffer {
  const b64 = pem
    .replace(/-----BEGIN PUBLIC KEY-----/, '')
    .replace(/-----END PUBLIC KEY-----/, '')
    .replace(/\s+/g, '');
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function base64EncodeBuf(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

export async function rsaEncryptPassword(publicKeyPem: string, password: string): Promise<string> {
  const cryptoObj = globalThis.crypto;
  if (!cryptoObj?.subtle) throw new Error('当前环境不支持 Web Crypto');
  const spki = await cryptoObj.subtle.importKey(
    'spki',
    pemToArrayBuffer(publicKeyPem),
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['encrypt'],
  );
  const cipher = await cryptoObj.subtle.encrypt(
    { name: 'RSA-OAEP' },
    spki,
    new TextEncoder().encode(password),
  );
  return base64EncodeBuf(cipher);
}