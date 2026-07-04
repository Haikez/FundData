#!/bin/bash
# =============================================================
# OneCloud 部署脚本 - 基金007751 LED看板
# 用法: bash setup.sh
# =============================================================

PROJECT_DIR="/opt/fund007751"
LOG_DIR="/var/log/fund007751"

echo "============================================"
echo "  基金 007751 LED 看板 - OneCloud 部署脚本"
echo "============================================"
echo ""

# 1. 确保日志目录
echo "[1/4] 创建日志目录..."
mkdir -p "$LOG_DIR"
echo "  ✅ $LOG_DIR"

# 2. 离线安装 Python 依赖
echo "[2/4] 安装 Python 依赖..."
if ! command -v python3 &>/dev/null; then
    echo "  ❌ 未找到 python3，请先安装"
    exit 1
fi
echo "  ✓ python3: $(python3 --version)"

WHEEL_DIR="${PROJECT_DIR}/pip_packages"
if ls "$WHEEL_DIR"/*.whl &>/dev/null 2>&1; then
    # 写一个离线安装脚本到临时目录，避免 zsh 转义问题
    cat > /tmp/install_wheels.py << 'PYEOF'
import zipfile, glob, os, sys

# 查找 site-packages
paths = ["/usr/local/lib/python3.11/dist-packages",
         "/usr/lib/python3/dist-packages",
         "/usr/lib/python3.11/dist-packages"]
site_pkg = next((p for p in paths if os.path.isdir(p)), None)
if not site_pkg:
    import site as _site
    site_pkg = _site.getsitepackages()[0]

wheel_dir = "/opt/fund007751/pip_packages"
wheels = sorted(glob.glob(os.path.join(wheel_dir, "*.whl")))

if not wheels:
    print("  ❌ 未找到 wheel 包")
    sys.exit(1)

for w in wheels:
    name = os.path.basename(w)
    print(f"  解压 {name}...")
    with zipfile.ZipFile(w) as zf:
        zf.extractall(site_pkg)

# 验证
try:
    import requests
    print(f"  ✅ requests {requests.__version__} 安装成功")
except Exception as e:
    print(f"  ❌ 安装失败: {e}")
    sys.exit(1)
PYEOF

    python3 /tmp/install_wheels.py
    rm -f /tmp/install_wheels.py
else
    echo "  ⚠️  pip_packages/ 目录为空或不存在，请先获取 wheel 包"
    echo "     在本地执行: pip download requests -d pip_packages --only-binary=:all: --platform=any"
fi

# 3. 校验 LED 设备
echo "[3/4] 校验 LED 设备..."
LED_OK=0
for led in /sys/class/leds/onecloud:*; do
    if [ -d "$led" ]; then
        echo "  ✅ 检测到: $led"
        LED_OK=1
    fi
done
if [ "$LED_OK" -eq 0 ]; then
    echo "  ⚠️  未检测到 OneCloud LED 设备，LED 控制会静默跳过"
fi

# 4. 设置定时任务
echo "[4/4] 设置定时任务..."
CRON_JOBS=(
    "30 15 * * 1-5 cd ${PROJECT_DIR} && python3 fund_crawler.py >> ${LOG_DIR}/crawler.log 2>&1"
    "0 22 * * * cd ${PROJECT_DIR} && python3 led_scheduler.py off >> ${LOG_DIR}/led.log 2>&1"
    "0 7 * * * cd ${PROJECT_DIR} && python3 led_scheduler.py on >> ${LOG_DIR}/led.log 2>&1"
)

EXISTING_CRON=$(crontab -l 2>/dev/null || true)
for job in "${CRON_JOBS[@]}"; do
    if echo "$EXISTING_CRON" | grep -qF "$job"; then
        echo "  → 已存在: ${job:0:30}..."
    else
        (echo "$EXISTING_CRON"; echo "$job") | crontab -
        EXISTING_CRON=$(crontab -l 2>/dev/null)
        echo "  ✅ 添加: ${job:0:30}..."
    fi
done

echo ""
echo "============================================"
echo "  🎉 部署完成！"
echo "============================================"
echo "  项目路径: ${PROJECT_DIR}"
echo "  日志路径: ${LOG_DIR}/crawler.log"
echo ""
echo "  手动运行:  cd ${PROJECT_DIR} && python3 fund_crawler.py"
echo "  查看日志:  tail -f ${LOG_DIR}/crawler.log"
echo "============================================"
