"""独立后台登录的 RSA 非对称加密。

流程：
- 后端持 RSA-2048 私钥，公开对应的公钥（SPKI PEM）。
- 前端登录时用公钥把密码 RSA-OAEP(SHA-256) 加密，base64 传给后端。
- 后端用私钥解出明文密码，再走 PBKDF2 校验/存储。

私钥持久化在本机文件里（首次启动自动生成），路径可经 ADMIN_RSA_KEY_PATH 配置；
生产环境请妥善保管私钥文件。
"""
import base64
import logging
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger("salted_fish.admin_crypto")

_KEYS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keys")
_KEY_PATH = os.environ.get("ADMIN_RSA_KEY_PATH", os.path.join(_KEYS_DIR, "admin_rsa.pem"))

# RSA-2048 OAEP 分组最多加密 (2048/8 - 2*hash_len - 2) = 190 字节，密码足够
_RSA_BITS = 2048


def _load_or_create_key():
    """读取私钥；不存在则生成 RSA-2048 并对持久化。"""
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=_RSA_BITS)
    os.makedirs(os.path.dirname(_KEY_PATH), exist_ok=True)
    # 私钥权限尽量收窄
    with open(_KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    try:
        os.chmod(_KEY_PATH, 0o600)
    except OSError:  # 非 POSIX 平台忽略
        pass
    logger.info("已生成 RSA 私钥：%s（请妥善保管）", _KEY_PATH)
    return private_key


_private_key = _load_or_create_key()


def public_key_pem() -> str:
    """返回 PEM 编码的公钥（SPKI），供前端导入。"""
    pub = _private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pub.decode()


def encrypt_with_public(pem_pub: bytes, data: bytes) -> bytes:
    """用给定的 PEM 公钥加密（供测试/联调用公钥做加密验证）。"""
    pub = serialization.load_pem_public_key(pem_pub)
    return pub.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def decrypt_password(enc_b64: str) -> str:
    """用私钥解密前端传来的 RSA-OAEP 密文，返回明文密码。失败抛 ValueError。"""
    try:
        ciphertext = base64.b64decode(enc_b64)
    except Exception as e:  # noqa: BLE001
        raise ValueError("密文不是合法 base64") from e
    try:
        plaintext = _private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception as e:  # noqa: BLE001
        raise ValueError("解密失败（密钥不匹配或密文损坏）") from e
    return plaintext.decode("utf-8")


def key_path() -> str:
    return _KEY_PATH