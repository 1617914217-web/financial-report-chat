# -*- coding: utf-8 -*-
"""
从ModelScope下载bge-large-zh-v1.5模型（国内镜像）
"""
import os
from modelscope import snapshot_download

base_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(base_dir, "models")
os.makedirs(models_dir, exist_ok=True)

print("开始从ModelScope下载 BAAI/bge-large-zh-v1.5 ...")
try:
    model_dir = snapshot_download(
        "BAAI/bge-large-zh-v1.5",
        cache_dir=models_dir,
        revision="master"
    )
    print(f"模型下载完成: {model_dir}")
except Exception as e:
    print(f"下载失败: {e}")
    print("尝试备用方案...")
