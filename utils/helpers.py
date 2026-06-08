"""
工具函数模块
"""
import os
import uuid
import time
from datetime import datetime


def generate_id() -> str:
    """生成唯一的任务 ID"""
    return uuid.uuid4().hex[:12]


def make_output_dir(base: str, sub: str) -> str:
    """创建输出目录并返回路径"""
    p = os.path.join(base, sub)
    os.makedirs(p, exist_ok=True)
    return p


def timestamp_str() -> str:
    """返回当前时间字符串"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def format_size(bytes_val: int) -> str:
    """将字节数转换为可读大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}" if unit != 'B' else f"{bytes_val} B"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"
