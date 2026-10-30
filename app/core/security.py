# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""认证安全原语：scrypt 密码哈希与 HMAC 会话签名。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import settings

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_runtime_secret = secrets.token_urlsafe(48)


def _now() -> int:
    """集中暴露当前时间，便于测试过期路径。"""
    return int(time.time())


def _auth_secret() -> bytes:
    """优先使用显式配置；未配置时退化为进程级随机密钥。"""
    return (settings.auth_secret_key or _runtime_secret).encode("utf-8")


def hash_password(password: str) -> str:
    """使用 scrypt 生成带参数和随机盐的密码哈希。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码；格式异常、空哈希或不匹配时统一返回 False。"""
    try:
        algorithm, n, r, p, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(*, user_id: int, username: str) -> str:
    """生成有签名的登录会话 Token。"""
    payload = {
        "sub": user_id,
        "username": username,
        "exp": _now() + settings.auth_session_ttl_seconds,
    }
    body = _b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signature = hmac.new(_auth_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def read_session_token(token: str) -> dict[str, Any] | None:
    """校验并读取会话 Token；签名错误或过期返回 None。"""
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_auth_secret(), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature), expected):
            return None
        payload = json.loads(_b64decode(body))
        if int(payload["exp"]) < _now():
            return None
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
