#!/bin/bash
# =============================================================
# OneCloud 部署脚本 - 基金007751 LED看板
# 用法: bash setup.sh
# =============================================================

set -e

PROJECT_DIR="/opt/fund007751"
LOG_DIR="/var/log/fund007751"

echo "============================================"
echo "  基金 007751 LED 看板 - OneCloud 部署脚本"
echo "============================================"
echo ""

# 1. 安装 Python 依赖
echo "[1/4] 安装 Python 依赖..."
if ! command -v python3 &>/dev/null; then
    echo "  → 安装 Python3..."
    apt update && apt install -y python3 python3-pip
fi
pip3 install -r "${PROJECT_DIR}/requirements.txt" || true
echo "  ✅ Python 依赖就绪"

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

# 4. 设置定时任务 (交易日 15:30 执行)
echo "[4/4] 设置定时任务..."
CRON_JOB="30 15 * * 1-5 cd ${PROJECT_DIR} && python3 fund_crawler.py >> ${LOG_DIR}/crawler.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "fund_crawler.py"; then
    echo "  → 定时任务已存在，跳过"
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "  ✅ 已添加定时任务: 每个交易日 15:30 执行"
fi

echo ""
echo "============================================"
echo "  🎉 部署完成！"
echo "============================================"
echo "  项目路径: ${PROJECT_DIR}"
echo "  日志路径: ${LOG_DIR}/crawler.log"
echo "  执行频率: 交易日 15:30 (定时任务)"
echo ""
echo "  📗 低估 = 绿灯   📙 合理 = 蓝灯   📕 高估 = 红灯"
echo ""
echo "  手动运行:  cd ${PROJECT_DIR} && python3 fund_crawler.py"
echo "  查看日志:  tail -f ${LOG_DIR}/crawler.log"
echo "============================================"
