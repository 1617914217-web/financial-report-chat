# -*- coding: utf-8 -*-
"""
简易 .env 加载器（零外部依赖）
从项目根目录的 .env 文件读取键值对，注入 os.environ
"""
import os

_ENV_LOADED = False


def load_env():
    """加载 .env 文件到 os.environ（仅执行一次）"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    # 项目根目录（本文件所在目录）
    base = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base, ".env")

    if not os.path.exists(env_path):
        _ENV_LOADED = True
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # 不覆盖已存在的环境变量
            if key and key not in os.environ:
                os.environ[key] = value

    _ENV_LOADED = True


def get(key: str, default: str = "") -> str:
    """获取环境变量，自动加载 .env"""
    load_env()
    return os.environ.get(key, default)
