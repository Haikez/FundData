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

# 0. 确保日志目录存在
mkdir -p "$LOG_DIR"

# 1. 安装 Python 依赖
echo "[1/4] 安装 Python 依赖..."
if ! command -v python3 &>/dev/null; then
    echo "  → 安装 Python3..."
    apt update && apt install -y python3 2>/dev/null || {
        echo "  ❌ 无法安装 Python3，请检查网络"
        exit 1
    }
fi

# 尝试在线安装 pip + requests
INSTALL_OK=0

# 方案A: pip3 在线安装
if command -v pip3 &>/dev/null; then
    echo "  → 尝试 pip3 在线安装..."
    pip3 install -r "${PROJECT_DIR}/requirements.txt" 2>/dev/null && INSTALL_OK=1
fi

# 方案B: 尝试 python3 -m pip
if [ "$INSTALL_OK" -eq 0 ]; then
    if python3 -m pip --version &>/dev/null; then
        echo "  → 尝试 python3 -m pip 在线安装..."
        python3 -m pip install -r "${PROJECT_DIR}/requirements.txt" 2>/dev/null && INSTALL_OK=1
    fi
fi

# 方案C: 离线安装 (使用同目录下的 pip_packages/*.whl)
if [ "$INSTALL_OK" -eq 0 ]; then
    if ls "${PROJECT_DIR}/pip_packages/"*.whl &>/dev/null 2>&1; then
        echo "  → 离线安装 (从 pip_packages 解压)..."
        python3 -c "
import zipfile, glob, os
site_pkg = '/usr/local/lib/python3.11/dist-packages'
if not os.path.exists(site_pkg):
    site_pkg = '/usr/lib/python3/dist-packages'
wheels = sorted(glob.glob('${PROJECT_DIR}/pip_packages/*.whl'))
for w in wheels:
    print(f'  解压 {os.path.basename(w)}...')
    with zipfile.ZipFile(w) as zf:
        zf.extractall(site_pkg)
" 2>/dev/null && INSTALL_OK=1
    fi
fi

# 方案D: 尝试安装 pip 后再安装
if [ "$INSTALL_OK" -eq 0 ]; then
    echo "  → 尝试安装 pip..."
    apt install -y python3-pip 2>/dev/null || python3 -m ensurepip 2>/dev/null || true
    if command -v pip3 &>/dev/null; then
        pip3 install -r "${PROJECT_DIR}/requirements.txt" 2>/dev/null && INSTALL_OK=1
    fi
fi

if [ "$INSTALL_OK" -eq 0 ]; then
    echo "  ⚠️  依赖安装失败，尝试最后手段: 直接解压到 site-packages"
    # 用 python 自己解压 wheel 到 site-packages
    python3 -c "
import zipfile, glob, os, sys
# 查找 site-packages
paths = ['/usr/local/lib/python3.11/dist-packages', '/usr/lib/python3/dist-packages', '/usr/lib/python3.11/dist-packages']
site_pkg = None
for p in paths:
    if os.path.isdir(p):
        site_pkg = p
        break
if not site_pkg:
    # 自动检测
    import site as _site
    site_pkg = _site.getsitepackages()[0]
print(f'  目标路径: {site_pkg}')
wheels = sorted(glob.glob('${PROJECT_DIR}/pip_packages/*.whl'))
if not wheels:
    print('  无离线包可用，将尝试 pip 在线')
    sys.exit(1)
for w in wheels:
    name = os.path.basename(w)
    print(f'  解压 {name}...')
    with zipfile.ZipFile(w) as zf:
        zf.extractall(site_pkg)
print('  完成')
" 2>&1 && INSTALL_OK=1
fi

if [ "$INSTALL_OK" -eq 1 ]; then
    echo "  ✅ Python 依赖就绪"
else
    echo "  ❌ 依赖安装失败，请手动执行: pip3 install requests"
fi

# 2. 创建日志目录
echo "[2/4] 创建日志目录..."
mkdir -p "$LOG_DIR"
echo "  ✅ 日志目录: $LOG_DIR"

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
    echo "  ⚠️  未检测到 OneCloud LED 设备，请确认是否在 OneCloud 上运行"
    echo "  脚本仍可执行，但 LED 控制会静默跳过"
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
echo "  执行频率:"
echo "    - 交易日 15:30 → 爬虫+LED"
echo "    - 每天 22:00   → 熄灯"
echo "    - 每天 07:00   → 恢复灯色"
echo ""
echo "  📗 低估 = 🟢 绿灯    📙 合理 = 🔵 蓝灯    📕 高估 = 🔴 红灯"
echo "  交易日 15:30 后:   涨 = 🔴 红灯   跌 = 🟢 绿灯   平 = 🔵 蓝灯"
echo ""
echo "  手动运行:  cd ${PROJECT_DIR} && python3 fund_crawler.py"
echo "  查看日志:  tail -f ${LOG_DIR}/crawler.log"
echo "============================================"
