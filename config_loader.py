# -*- coding: utf-8 -*-
"""读.env配置"""
import os

_loaded = False

def load():
    """加载.env到环境变量"""
    global _loaded
    if _loaded:
        return

    base = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(base, ".env")

    if not os.path.exists(env_file):
        _loaded = True
        return

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if k and k not in os.environ:
                os.environ[k] = v

    _loaded = True

def get(key, default=""):
    """获取配置"""
    load()
    return os.environ.get(key, default)
