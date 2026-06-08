"""
低光照增强 Web 应用
Flask + OpenCV 实现
"""
import os
import sys
import threading
import traceback

from flask import (
    Flask, render_template, request, jsonify,
    send_from_directory
)
from werkzeug.utils import secure_filename

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.enhancer import METHODS, enhance_image, analyze_image
from utils.helpers import generate_id, timestamp_str

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 上传限制

UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
OUTPUT_IMG_DIR = os.path.join(BASE_DIR, 'output', 'images')
OUTPUT_VID_DIR = os.path.join(BASE_DIR, 'output', 'videos')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMG_DIR, exist_ok=True)
os.makedirs(OUTPUT_VID_DIR, exist_ok=True)

ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'webp'}
ALLOWED_VID = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'}

# 任务状态存储 (简单内存字典)
tasks = {}
tasks_lock = threading.Lock()


def allowed_file(filename: str, allowed_set: set) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


# ═══════════════════════════════════════════════════════════════
# 路由: 页面
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """主页"""
    return render_template('index.html', methods=METHODS)


@app.route('/output/<path:subpath>')
def serve_output(subpath):
    """提供输出文件的静态访问"""
    return send_from_directory(os.path.join(BASE_DIR, 'output'), subpath)


@app.route('/uploads/<filename>')
def serve_upload(filename):
    """提供上传文件的静态访问"""
    return send_from_directory(UPLOAD_DIR, filename)


# ═══════════════════════════════════════════════════════════════
# API: 获取方法列表
# ═══════════════════════════════════════════════════════════════

@app.route('/api/methods')
def api_methods():
    """返回所有可用的增强方法"""
    result = {}
    for key, val in METHODS.items():
        result[key] = {
            'name': val['name'],
            'desc': val['desc'],
        }
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
# API: 图片增强
# ═══════════════════════════════════════════════════════════════

@app.route('/api/enhance/image', methods=['POST'])
def api_enhance_image():
    """
    接收上传图片 → 增强 → 保存 → 返回结果
    """
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    if not allowed_file(file.filename, ALLOWED_IMG):
        return jsonify({'error': f'不支持的图片格式。支持: {", ".join(ALLOWED_IMG)}'}), 400

    method = request.form.get('method', 'comprehensive')
    if method not in METHODS:
        return jsonify({'error': f'未知方法: {method}'}), 400

    task_id = generate_id()

    # 保存上传文件
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_name = f"{task_id}.{ext}"
    upload_path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(upload_path)

    # get method (defaults to auto)
    method = request.form.get('method', 'auto')

    # 在线程中处理
    def process():
        import cv2
        try:
            img = cv2.imread(upload_path)
            if img is None:
                with tasks_lock:
                    tasks[task_id] = {'status': 'error', 'error': 'Unable to read image'}
                return

            analysis = analyze_image(img)
            enhanced = enhance_image(img, method)

            out_name = f"{task_id}_enhanced.{ext}"
            out_path = os.path.join(OUTPUT_IMG_DIR, out_name)
            cv2.imwrite(out_path, enhanced)

            orig_url = f"/uploads/{safe_name}"
            enh_url = f"/output/images/{out_name}"
            with tasks_lock:
                tasks[task_id] = {
                    'status': 'done',
                    'original': orig_url,
                    'enhanced': enh_url,
                    'original_name': file.filename,
                    'method': method,
                    'method_name': METHODS[method]['name'],
                    'analysis': {
                        'mean_lum': round(analysis['mean_lum'], 1),
                        'median_lum': round(analysis['median_lum'], 1),
                        'dark_ratio': round(analysis['dark_ratio'], 4),
                        'contrast': round(analysis['contrast'], 1),
                        'dyn_range': round(analysis['dyn_range'], 1),
                        'level': analysis['level'],
                    },
                }
        except Exception as e:
            traceback.print_exc()
            with tasks_lock:
                tasks[task_id] = {'status': 'error', 'error': str(e)}

    with tasks_lock:
        tasks[task_id] = {'status': 'processing'}

    threading.Thread(target=process, daemon=True).start()
    return jsonify({'task_id': task_id})


# ═══════════════════════════════════════════════════════════════
# API: 视频增强
# ═══════════════════════════════════════════════════════════════

@app.route('/api/enhance/video', methods=['POST'])
def api_enhance_video():
    """
    接收上传视频 → 逐帧增强 → 合成视频 → 返回结果
    """
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    if not allowed_file(file.filename, ALLOWED_VID):
        return jsonify({'error': f'不支持的视频格式。支持: {", ".join(ALLOWED_VID)}'}), 400

    method = request.form.get('method', 'auto')
    if method not in METHODS:
        return jsonify({'error': f'Unknown method: {method}'}), 400

    task_id = generate_id()

    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_name = f"{task_id}.{ext}"
    upload_path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(upload_path)

    def process():
        import cv2
        cap = None
        writer = None
        try:
            cap = cv2.VideoCapture(upload_path)
            if not cap.isOpened():
                with tasks_lock:
                    tasks[task_id] = {'status': 'error', 'error': '无法读取视频文件'}
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 如果无法获取帧数则设为 -1
            if total_frames <= 0:
                total_frames = -1

            out_name = f"{task_id}_enhanced.mp4"
            out_path = os.path.join(OUTPUT_VID_DIR, out_name)

            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264
            writer = cv2.VideoWriter(out_path, fourcc, fps if fps > 0 else 25, (width, height))

            processed = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                enhanced = enhance_image(frame, method)
                writer.write(enhanced)
                processed += 1

                # 每 50 帧更新进度
                if processed % 50 == 0:
                    with tasks_lock:
                        if task_id in tasks:
                            tasks[task_id]['progress'] = processed
                            if total_frames > 0:
                                tasks[task_id]['progress_pct'] = round(processed / total_frames * 100, 1)

            cap.release()
            writer.release()

            orig_url = f"/uploads/{safe_name}"
            enh_url = f"/output/videos/{out_name}"
            with tasks_lock:
                tasks[task_id] = {
                    'status': 'done',
                    'original': orig_url,
                    'enhanced': enh_url,
                    'original_name': file.filename,
                    'method': method,
                    'method_name': METHODS[method]['name'],
                    'total_frames': processed,
                }
        except Exception as e:
            traceback.print_exc()
            try:
                if cap:
                    cap.release()
                if writer:
                    writer.release()
            except Exception:
                pass
            with tasks_lock:
                tasks[task_id] = {'status': 'error', 'error': str(e)}

    with tasks_lock:
        tasks[task_id] = {
            'status': 'processing',
            'progress': 0,
            'progress_pct': 0,
        }

    threading.Thread(target=process, daemon=True).start()
    return jsonify({'task_id': task_id})


# ═══════════════════════════════════════════════════════════════
# API: 任务状态查询
# ═══════════════════════════════════════════════════════════════

@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    """轮询任务状态"""
    with tasks_lock:
        task = tasks.get(task_id)
    if task is None:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify(task)


# ═══════════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("  Low-Light Enhancement System")
    print("  Available methods:")
    for k, v in METHODS.items():
        name = v['name'].encode('ascii', errors='replace').decode('ascii')
        print(f"    {k:20s} -> {name}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8128, debug=True)
