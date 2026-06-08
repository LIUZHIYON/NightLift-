"""
低光照增强引擎 — 纯 OpenCV 实现
==================================
提供多种低光照增强算法，从简单到复杂：

1. CLAHE (自适应直方图均衡) — LAB 空间，最常用，效果稳健
2. Gamma 校正 — 非线性亮度提升
3. 自动色阶拉伸 — 直方图拉伸
4. MSRCP (带色彩保持的多尺度 Retinex) — 高级算法
5. 综合增强管线 — 多种方法组合，效果最优
"""

import cv2
import numpy as np


# ═══════════════════════════════════════════════════════════════
# 方法 1: CLAHE — 限制对比度自适应直方图均衡 (最常用)
# ═══════════════════════════════════════════════════════════════

def enhance_clahe(img: np.ndarray, clip_limit: float = 2.0, tile_grid: tuple = (8, 8)) -> np.ndarray:
    """
    在 LAB 色彩空间的 L 通道上应用 CLAHE。
    这是低光照增强中最经典、最常用的方法。

    参数:
        img:        输入 BGR 图像
        clip_limit: 对比度裁剪阈值 (越大对比度越强)
        tile_grid:  网格大小
    返回:
        增强后的 BGR 图像
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    l_eq = clahe.apply(l)

    lab_eq = cv2.merge([l_eq, a, b])
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)


# ═══════════════════════════════════════════════════════════════
# 方法 2: Gamma 校正
# ═══════════════════════════════════════════════════════════════

def enhance_gamma(img: np.ndarray, gamma: float = 0.5) -> np.ndarray:
    """
    Gamma 校正: 对暗区进行非线性提亮。
    gamma < 1: 提亮暗区
    gamma > 1: 压暗亮区

    参数:
        img:   输入 BGR 图像
        gamma: Gamma 值 (默认 0.5 适合低光照)
    返回:
        增强后的 BGR 图像
    """
    table = (np.arange(256) / 255.0) ** gamma * 255.0
    table = np.clip(table, 0, 255).astype(np.uint8)
    return cv2.LUT(img, table)


# ═══════════════════════════════════════════════════════════════
# 方法 3: 自动色阶拉伸
# ═══════════════════════════════════════════════════════════════

def enhance_auto_levels(img: np.ndarray, low_percent: float = 0.5,
                        high_percent: float = 99.5) -> np.ndarray:
    """
    自动色阶: 将直方图拉伸到 [0, 255] 范围。
    截断两端的极端像素以避免噪声放大。

    参数:
        img:          输入 BGR 图像
        low_percent:  低端截断百分比
        high_percent: 高端截断百分比
    返回:
        增强后的 BGR 图像
    """
    result = np.zeros_like(img)
    for c in range(3):
        channel = img[:, :, c]
        low_val = np.percentile(channel, low_percent)
        high_val = np.percentile(channel, high_percent)
        if high_val <= low_val:
            high_val = low_val + 1
        stretched = (channel.astype(np.float32) - low_val) / (high_val - low_val) * 255.0
        result[:, :, c] = np.clip(stretched, 0, 255).astype(np.uint8)
    return result


# ═══════════════════════════════════════════════════════════════
# 方法 4: MSRCP (带色彩保持的多尺度 Retinex)
# ═══════════════════════════════════════════════════════════════

def enhance_msrcp(img: np.ndarray, scales: tuple = (15, 80, 250),
                  alpha: float = 125.0, beta: float = 46.0) -> np.ndarray:
    """
    多尺度 Retinex with Chromaticity Preservation.
    基于 Jobson 等人的经典论文，纯 OpenCV 实现。

    算法思路:
        1. 提取原始图像的色彩比例 (chromaticity)
        2. 对强度通道做多尺度 Retinex 增强
        3. 将色彩比例重新应用到增强后的强度上

    参数:
        img:    输入 BGR 图像
        scales: 高斯模糊尺度 (小、中、大)
        alpha:  强度调整参数
        beta:   偏移参数
    返回:
        增强后的 BGR 图像
    """
    img_f = img.astype(np.float32) + 1.0  # +1 防止 log(0)

    # 提取强度 (Intensity)
    intensity = np.sum(img_f, axis=2) / 3.0

    # 色彩比例 (chromaticity)
    intensity_safe = intensity.copy()
    intensity_safe[intensity_safe < 1.0] = 1.0
    chromaticity = img_f / np.dstack([intensity_safe] * 3)

    # 多尺度 Retinex
    retinex = np.zeros_like(intensity)
    for scale in scales:
        blurred = cv2.GaussianBlur(intensity, (0, 0), scale)
        blurred[blurred < 1.0] = 1.0
        retinex += np.log(intensity) - np.log(blurred)
    retinex /= len(scales)

    # 强度校正
    intensity_enhanced = np.exp(retinex * alpha / 255.0 + np.log(beta))

    # 归一化到 [0, 255]
    i_min = intensity_enhanced.min()
    i_max = intensity_enhanced.max()
    if i_max > i_min:
        intensity_enhanced = (intensity_enhanced - i_min) / (i_max - i_min) * 255.0
    else:
        intensity_enhanced[:] = 128.0

    # 将色彩比例应用回来
    result = intensity_enhanced[:, :, np.newaxis] * chromaticity
    result = np.clip(result, 0, 255).astype(np.uint8)

    return result


# ═══════════════════════════════════════════════════════════════
# 方法 5: 自动白平衡 (Gray World 假设)
# ═══════════════════════════════════════════════════════════════

def auto_white_balance(img: np.ndarray) -> np.ndarray:
    """
    基于 Gray-World 假设的自动白平衡。
    假设场景的平均颜色是灰色的，据此调整各通道增益。
    """
    result = img.astype(np.float32)
    avg_b = result[:, :, 0].mean()
    avg_g = result[:, :, 1].mean()
    avg_r = result[:, :, 2].mean()

    gray = (avg_b + avg_g + avg_r) / 3.0
    if avg_b > 0:
        result[:, :, 0] *= gray / avg_b
    if avg_g > 0:
        result[:, :, 1] *= gray / avg_g
    if avg_r > 0:
        result[:, :, 2] *= gray / avg_r

    return np.clip(result, 0, 255).astype(np.uint8)


def auto_white_balance_perfect_reflector(img: np.ndarray) -> np.ndarray:
    """
    基于完美反射假设的自动白平衡。
    假设图像中最亮的像素是白色的。
    """
    result = img.astype(np.float32)
    max_b = np.percentile(result[:, :, 0], 99)
    max_g = np.percentile(result[:, :, 1], 99)
    max_r = np.percentile(result[:, :, 2], 99)

    scale = 255.0
    if max_b > 0:
        result[:, :, 0] *= scale / max_b
    if max_g > 0:
        result[:, :, 1] *= scale / max_g
    if max_r > 0:
        result[:, :, 2] *= scale / max_r

    return np.clip(result, 0, 255).astype(np.uint8)


# ═══════════════════════════════════════════════════════════════
# 方法 6: 亮度/对比度自适应调整
# ═══════════════════════════════════════════════════════════════

def enhance_brightness_contrast(img: np.ndarray, brightness: int = 30,
                                contrast: float = 1.3) -> np.ndarray:
    """
    亮度和对比度调整。

    参数:
        img:        输入 BGR 图像
        brightness: 亮度增量 (-127 ~ 127)
        contrast:   对比度乘数 (0 ~ 3)
    返回:
        增强后的 BGR 图像
    """
    result = img.astype(np.float32) * contrast + brightness
    return np.clip(result, 0, 255).astype(np.uint8)


# ═══════════════════════════════════════════════════════════════
# 方法 7: 基于 Retinex 的单尺度 SSR
# ═══════════════════════════════════════════════════════════════

def enhance_ssr(img: np.ndarray, sigma: float = 80.0) -> np.ndarray:
    """
    单尺度 Retinex (SSR)。
    反射分量 = log(原图) - log(高斯模糊)

    参数:
        img:   输入 BGR 图像
        sigma: 高斯模糊 sigma
    返回:
        增强后的 BGR 图像
    """
    img_f = img.astype(np.float32) + 1.0
    blurred = cv2.GaussianBlur(img_f, (0, 0), sigma)
    blurred[blurred < 1.0] = 1.0

    retinex = np.log(img_f) - np.log(blurred)

    # 各通道独立归一化
    result = np.zeros_like(img_f)
    for c in range(3):
        channel = retinex[:, :, c]
        c_min = channel.min()
        c_max = channel.max()
        if c_max > c_min:
            result[:, :, c] = (channel - c_min) / (c_max - c_min) * 255.0
        else:
            result[:, :, c] = 128.0

    return result.astype(np.uint8)


# ═══════════════════════════════════════════════════════════════
# 方法 8: 去雾算法 — 暗通道先验 (Dark Channel Prior)
# ═══════════════════════════════════════════════════════════════

def enhance_dehaze(img: np.ndarray, omega: float = 0.85,
                   window_size: int = 15, t0: float = 0.1) -> np.ndarray:
    """
    基于暗通道先验的去雾/增强算法。
    对低光照图像也有较好的增强效果，因为它能消除"雾感"并提升对比度。

    参考文献: He et al., "Single Image Haze Removal Using Dark Channel Prior", CVPR 2009

    参数:
        img:         输入 BGR 图像
        omega:       去雾强度 (0~1)
        window_size: 暗通道滤波窗口大小
        t0:          最小透射率
    返回:
        增强后的 BGR 图像
    """
    img_f = img.astype(np.float64) / 255.0

    # 暗通道
    dark_channel = np.min(img_f, axis=2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (window_size, window_size))
    dark_channel = cv2.erode(dark_channel, kernel)

    # 大气光估计 — 取暗通道最亮的前 0.1% 像素的原图均值
    num_pixels = dark_channel.size
    num_brightest = max(int(num_pixels * 0.001), 1)
    flat_dark = dark_channel.ravel()
    indices = np.argpartition(flat_dark, -num_brightest)[-num_brightest:]
    atmospheric_light = np.zeros(3)
    for c in range(3):
        atmospheric_light[c] = np.max(img_f[:, :, c].ravel()[indices])

    # 透射率
    transmission = 1.0 - omega * dark_channel
    transmission = np.clip(transmission, t0, 1.0)

    # 引导滤波细化透射率 (简化版: 使用双边滤波代替)
    transmission = cv2.bilateralFilter(
        transmission.astype(np.float32), 9, 75, 75)

    # 恢复
    result = np.zeros_like(img_f)
    for c in range(3):
        result[:, :, c] = (
            (img_f[:, :, c] - atmospheric_light[c]) /
            np.maximum(transmission, t0) + atmospheric_light[c]
        )

    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    return result


# ═══════════════════════════════════════════════════════════════
# 图像分析器 — 自动检测暗度等级，决定最佳参数
# ═══════════════════════════════════════════════════════════════

def analyze_image(img: np.ndarray) -> dict:
    """
    分析图像的光照状况，返回量化指标。

    指标:
        mean_lum:     平均亮度 (0-255)
        median_lum:   中位数亮度 (0-255)
        dark_ratio:   暗像素占比 (<50), 比例越高越暗
        contrast:     RMS 对比度
        dyn_range:    动态范围 (P95 - P5)

    暗度等级判定:
        极端暗: dark_ratio > 0.7  且 mean_lum < 40
        很暗:   dark_ratio > 0.5  或 mean_lum < 60
        偏暗:   dark_ratio > 0.3  或 mean_lum < 90
        正常:   其余情况
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    mean_lum = float(gray.mean())
    median_lum = float(np.median(gray))
    dark_ratio = float((gray < 50).sum() / gray.size)
    bright_ratio = float((gray > 200).sum() / gray.size)

    # RMS 对比度
    contrast = float(gray.std())

    # 动态范围
    low = np.percentile(gray, 5)
    high = np.percentile(gray, 95)
    dyn_range = float(high - low)

    # 判定暗度等级
    if dark_ratio > 0.7 and mean_lum < 40:
        level = 'extreme'    # 极端低光照
    elif dark_ratio > 0.5 or mean_lum < 60:
        level = 'severe'     # 很暗
    elif dark_ratio > 0.3 or mean_lum < 90:
        level = 'moderate'   # 偏暗
    else:
        level = 'mild'       # 轻微暗/正常

    return {
        'mean_lum': mean_lum,
        'median_lum': median_lum,
        'dark_ratio': dark_ratio,
        'bright_ratio': bright_ratio,
        'contrast': contrast,
        'dyn_range': dyn_range,
        'level': level,
    }


# ═══════════════════════════════════════════════════════════════
# 综合增强管线 (推荐使用 — 效果最好)
# ═══════════════════════════════════════════════════════════════

def enhance_comprehensive(img: np.ndarray) -> np.ndarray:
    """
    综合增强管线，组合多种方法以达到最佳效果:
    1. 自动白平衡 (Gray World)
    2. CLAHE (轻度, 平衡直方图)
    3. Gamma 校正 (提亮暗部)
    4. 轻微锐化

    这是推荐的默认增强方法。
    """
    # Step 1: 自动白平衡
    img = auto_white_balance(img)

    # Step 2: CLAHE 增强 L 通道 — 轻度增强
    img = enhance_clahe(img, clip_limit=1.5, tile_grid=(8, 8))

    # Step 3: Gamma 校正 — 提亮暗部
    img = enhance_gamma(img, gamma=0.7)

    # Step 4: 轻微锐化 (unsharp masking)
    blurred = cv2.GaussianBlur(img, (0, 0), 2.0)
    img = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)
    img = np.clip(img, 0, 255).astype(np.uint8)

    return img


def enhance_strong(img: np.ndarray) -> np.ndarray:
    """
    强力增强 — 用于极端低光照场景。
    组合: MSRCP + CLAHE + Gamma
    """
    # Step 1: MSRCP 恢复细节
    img = enhance_msrcp(img, scales=(10, 60, 180), alpha=140.0, beta=50.0)

    # Step 2: CLAHE 增强对比度
    img = enhance_clahe(img, clip_limit=2.5, tile_grid=(8, 8))

    # Step 3: Gamma 提亮
    img = enhance_gamma(img, gamma=0.6)

    return img


# ═══════════════════════════════════════════════════════════════
# 自动模式 — 分析图像后自适应选择最佳参数
# ═══════════════════════════════════════════════════════════════

def enhance_auto(img: np.ndarray, analysis: dict = None) -> np.ndarray:
    """
    一键增强 — 自动分析图像暗度，自适应选择最优参数。
    用户无需选择任何参数，直接得到最佳结果。

    策略:
        extreme  极端暗 → 强力管线: MSRCP + 强 CLAHE + 强 Gamma
        severe   很暗   → 强化管线: Mid CLAHE + Mid Gamma + 锐化
        moderate 偏暗   → 标准管线: 白平衡 + 轻 CLAHE + 轻 Gamma
        mild     轻微   → 轻量管线: 仅白平衡 + 轻 CLAHE
    """
    if analysis is None:
        analysis = analyze_image(img)

    level = analysis['level']
    dark_ratio = analysis['dark_ratio']
    mean_lum = analysis['mean_lum']

    if level == 'extreme':
        # 极端暗: 激进提亮，最大化可见度
        gamma_val = 0.35
        clahe_clip = 3.0
        img = auto_white_balance(img)
        img = enhance_msrcp(img, scales=(8, 50, 150), alpha=160.0, beta=55.0)
        img = enhance_clahe(img, clip_limit=clahe_clip, tile_grid=(8, 8))
        img = enhance_gamma(img, gamma=gamma_val)

    elif level == 'severe':
        # 很暗: 较强提亮
        gamma_val = 0.45
        clahe_clip = 2.5
        img = auto_white_balance(img)
        img = enhance_clahe(img, clip_limit=clahe_clip, tile_grid=(8, 8))
        img = enhance_gamma(img, gamma=gamma_val)
        # 适度锐化
        blurred = cv2.GaussianBlur(img, (0, 0), 2.5)
        img = cv2.addWeighted(img, 1.4, blurred, -0.4, 0)
        img = np.clip(img, 0, 255).astype(np.uint8)

    elif level == 'moderate':
        # 偏暗: 标准增强
        gamma_val = 0.55 + dark_ratio * 0.2
        clahe_clip = 1.5 + dark_ratio * 1.0
        img = auto_white_balance(img)
        img = enhance_clahe(img, clip_limit=clahe_clip, tile_grid=(8, 8))
        img = enhance_gamma(img, gamma=gamma_val)
        blurred = cv2.GaussianBlur(img, (0, 0), 2.0)
        img = cv2.addWeighted(img, 1.3, blurred, -0.3, 0)
        img = np.clip(img, 0, 255).astype(np.uint8)

    else:  # mild
        # 轻微暗: 轻量处理，避免过曝
        img = auto_white_balance(img)
        img = enhance_clahe(img, clip_limit=1.2, tile_grid=(8, 8))
        gamma_val = 0.75
        if mean_lum < 100:
            img = enhance_gamma(img, gamma=gamma_val)

    return img


# ═══════════════════════════════════════════════════════════════
# 方法注册表
# ═══════════════════════════════════════════════════════════════

METHODS = {
    'auto': {
        'name': 'Auto (一键增强)',
        'func': enhance_auto,
        'desc': '自动分析暗度，自适应选择最佳参数，一键出结果',
    },
    'comprehensive': {
        'name': 'Comprehensive',
        'func': enhance_comprehensive,
        'desc': '自动白平衡 + CLAHE + Gamma + 锐化',
    },
    'strong': {
        'name': 'Strong',
        'func': enhance_strong,
        'desc': 'MSRCP + CLAHE + Gamma，针对极端低光照',
    },
    'clahe': {
        'name': 'CLAHE',
        'func': lambda img: enhance_clahe(img, clip_limit=2.0, tile_grid=(8, 8)),
        'desc': 'LAB 空间 L 通道 CLAHE',
    },
    'msrcp': {
        'name': 'MSRCP',
        'func': lambda img: enhance_msrcp(img),
        'desc': '色彩保持的多尺度 Retinex',
    },
    'gamma': {
        'name': 'Gamma',
        'func': lambda img: enhance_gamma(img, gamma=0.4),
        'desc': '非线性亮度提升',
    },
    'dehaze': {
        'name': 'Dehaze',
        'func': lambda img: enhance_dehaze(img),
        'desc': '暗通道先验去雾',
    },
    'auto_levels': {
        'name': 'Auto Levels',
        'func': lambda img: enhance_auto_levels(img),
        'desc': '直方图拉伸',
    },
    'ssr': {
        'name': 'SSR',
        'func': lambda img: enhance_ssr(img, sigma=80.0),
        'desc': '单尺度 Retinex',
    },
}


def enhance_image(img: np.ndarray, method: str = 'comprehensive') -> np.ndarray:
    """
    统一的图像增强入口。

    参数:
        img:    输入 BGR 图像 (numpy array)
        method: 方法名 (见 METHODS 字典的 key)
    返回:
        增强后的 BGR 图像
    """
    if method not in METHODS:
        raise ValueError(f"未知方法: {method}。可用方法: {list(METHODS.keys())}")

    return METHODS[method]['func'](img)


def enhance_video_frame(frame: np.ndarray, method: str = 'comprehensive') -> np.ndarray:
    """增强单帧视频画面 (与 enhance_image 相同，提供明确命名)"""
    return enhance_image(frame, method)
