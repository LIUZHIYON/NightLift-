# NightLift — 低光照增强系统

基于 **Flask + OpenCV** 的低光照图像/视频增强 Web 应用，纯 OpenCV 实现，提供多种经典增强算法。

## 功能特性

- 🖼️ **图片增强** — 上传低光照图片，一键增强
- 🎬 **视频增强** — 上传低光照视频，逐帧增强后合成输出
- 🔍 **自动分析** — 分析图像的亮度、对比度、暗像素占比等指标，自动判定暗度等级
- 🤖 **Auto 模式** — 自适应参数选择，根据图像暗度自动选择最优增强策略
- 📊 **多种算法** — 内置 8 种经典增强算法 + 3 种组合管线
- 🔎 **灯箱预览** — 点击图片可全屏放大查看，半透明遮罩 + 模糊背景
- ⌨️ **键盘操作** — ← → 键在灯箱中切换原图和增强图，ESC 关闭灯箱
- 📐 **Side by Side 对比** — 左右并排对比原图和增强效果

## 增强方法

| 方法 | 说明 |
|------|------|
| **Auto** (一键增强) | 自动分析暗度，自适应选择最佳参数 |
| **CLAHE** | LAB 色彩空间 L 通道的 Contrast Limited Adaptive Histogram Equalization |
| **Gamma** | Gamma 校正，非线性亮度提升 |
| **Auto Levels** | 自动色阶拉伸，直方图拉伸到 [0, 255] |
| **MSRCP** | Multi-Scale Retinex with Chromaticity Preservation，色彩保持的多尺度 Retinex |
| **SSR** | Single-Scale Retinex，单尺度 Retinex |
| **Dehaze** | Dark Channel Prior 暗通道先验去雾 |
| **White Balance** | Gray World / Perfect Reflector 自动白平衡 |
| **Brightness/Contrast** | 亮度/对比度自适应调整 |
| **Comprehensive** | 组合管线：自动白平衡 + CLAHE + Gamma + Unsharp Masking 锐化 |
| **Strong** | 强力管线：MSRCP + CLAHE + Gamma，针对极端低光照 |

## 暗度分析

系统会自动分析上传图像的以下指标：

- **Mean Luminance** — 平均亮度
- **Median Luminance** — 中位数亮度
- **Dark Ratio** — 暗像素占比（< 50）
- **RMS Contrast** — 均方根对比度
- **Dynamic Range** — 动态范围（P95 - P5）

根据分析结果将图像分为四个暗度等级：

| 等级 | 判定条件 | Auto 策略 |
|------|----------|-----------|
| **extreme** (极端暗) | dark_ratio > 0.7 且 mean_lum < 40 | MSRCP + 强 CLAHE + 强 Gamma |
| **severe** (很暗) | dark_ratio > 0.5 或 mean_lum < 60 | 白平衡 + 中 CLAHE + 中 Gamma + 锐化 |
| **moderate** (偏暗) | dark_ratio > 0.3 或 mean_lum < 90 | 白平衡 + 轻 CLAHE + 轻 Gamma |
| **mild** (轻微暗) | 其余情况 | 仅白平衡 + 轻 CLAHE |

## 快速开始

### 环境要求

- Python 3.8+
- OpenCV 4.8+
- Flask 3.0+

### 安装

```bash
# 克隆仓库
git clone git@github.com:LIUZHIYON/NightLift-.git
cd NightLift-

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python app.py
```

浏览器打开 `http://localhost:8128`，上传图片或视频即可。

### 依赖

```
flask>=3.0.0
opencv-python>=4.8.0
numpy>=1.24.0
Werkzeug>=3.0.0
```

## 项目结构

```
NightLift-/
├── app.py                  # Flask Web 应用入口
├── engine/
│   ├── __init__.py
│   └── enhancer.py         # 增强引擎：所有算法实现 + 方法注册表
├── utils/
│   ├── __init__.py
│   └── helpers.py          # 工具函数
├── templates/
│   └── index.html          # 前端页面
├── static/
│   ├── css/style.css       # 样式
│   ├── js/app.js           # 前端逻辑
│   └── uploads/            # 上传文件存储
├── output/
│   ├── images/             # 增强后图片输出
│   └── videos/             # 增强后视频输出
├── requirements.txt
└── README.md
```

## UI 交互

### 灯箱预览 (Lightbox)

在 Result 结果展示区或 Side by Side 对比区，**点击任意图片**即可进入全屏灯箱模式：

- 图片以原始比例最大化显示，带半透明黑色遮罩和模糊背景
- **←** 左箭头键 → 切换到上一张（Original）
- **→** 右箭头键 → 切换到下一张（Enhanced）
- **ESC** → 关闭灯箱
- 点击遮罩或右上角 ✕ 也可关闭
- 底部显示快捷键提示

### Side by Side 对比

图片增强完成后，页面下方会显示 Original 和 Enhanced 两张图片左右并排，方便直观对比效果差异。

## API

### `GET /api/methods`

获取所有可用的增强方法列表。

### `POST /api/enhance/image`

上传图片进行增强。

- `file`: 图片文件（multipart/form-data）
- `method`: 增强方法名（可选，默认 `auto`）

返回 `task_id`，可通过任务状态接口轮询结果。

### `POST /api/enhance/video`

上传视频进行增强。

- `file`: 视频文件（multipart/form-data）
- `method`: 增强方法名（可选，默认 `auto`）

### `GET /api/task/<task_id>`

查询任务状态。返回 JSON：

```json
{
  "status": "done",
  "original": "/uploads/xxx.jpg",
  "enhanced": "/output/images/xxx_enhanced.jpg",
  "method": "auto",
  "method_name": "Auto (一键增强)",
  "analysis": {
    "mean_lum": 45.2,
    "median_lum": 32.0,
    "dark_ratio": 0.65,
    "contrast": 28.5,
    "dyn_range": 120.3,
    "level": "severe"
  }
}
```

## 算法参考

- **CLAHE**: Zuiderveld, K. "Contrast Limited Adaptive Histogram Equalization." Graphics Gems IV, 1994.
- **MSRCP**: Jobson, D. J., et al. "A Multiscale Retinex for Bridging the Gap Between Color Images and the Human Observation of Scenes." IEEE TIP, 1997.
- **Dark Channel Prior**: He, K., et al. "Single Image Haze Removal Using Dark Channel Prior." CVPR, 2009.
- **Gray World**: Buchsbaum, G. "A Spatial Processor Model for Object Colour Perception." J. Franklin Institute, 1980.

## License

MIT
