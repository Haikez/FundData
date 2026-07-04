#!/usr/bin/env python3
"""
LED 定时开关脚本
用法:
  python3 led_scheduler.py on    # 07:00 调用 → 恢复灯色
  python3 led_scheduler.py off   # 22:00 调用 → 关闭所有灯

工作日(07:00→15:29) → 估值灯    周末 → 估值灯
  低估→🟢  合理→🔵  高估→🔴      低估→🟢  合理→🔵  高估→🔴

工作日(15:30→22:00) → 涨跌灯     (由 fund_crawler.py 设置)
  涨→🔴  跌→🟢  平→🔵
"""
import json
import os
import sys
from datetime import datetime

LED_RED = "/sys/class/leds/onecloud:red:alive"
LED_GREEN = "/sys/class/leds/onecloud:green:alive"
LED_BLUE = "/sys/class/leds/onecloud:blue:alive"
LED_STATE_FILE = "/opt/fund007751/.led_state"

# 估值区间 (与 fund_crawler.py 保持一致)
PE_LOWER_BAND = 7.5
PE_UPPER_BAND = 11.5


def _led_write(path, value):
    try:
        with open(path, "w") as f:
            f.write(str(value))
        return True
    except (OSError, IOError):
        return False


def all_off():
    """关闭所有灯"""
    for led in [LED_RED, LED_GREEN, LED_BLUE]:
        _led_write(f"{led}/trigger", "none")
        _led_write(f"{led}/brightness", 0)
    print("[LED] 所有灯已关闭")


def set_red():
    _led_write(f"{LED_RED}/trigger", "default-on")
    _led_write(f"{LED_GREEN}/trigger", "none")
    _led_write(f"{LED_BLUE}/trigger", "none")
    print("[LED] 🔴 红灯")


def set_green():
    _led_write(f"{LED_RED}/trigger", "none")
    _led_write(f"{LED_GREEN}/trigger", "default-on")
    _led_write(f"{LED_BLUE}/trigger", "none")
    print("[LED] 🟢 绿灯")


def set_blue():
    _led_write(f"{LED_RED}/trigger", "none")
    _led_write(f"{LED_GREEN}/trigger", "none")
    _led_write(f"{LED_BLUE}/trigger", "default-on")
    print("[LED] 🔵 蓝灯")


def restore_valuation(pe_value):
    """根据 PE 估值判断设置灯色"""
    pe = float(pe_value) if pe_value else None
    if pe is None:
        print("[LED] 无PE数据 → 🟢 绿灯(默认)")
        set_green()
    elif pe < PE_LOWER_BAND:
        print(f"[LED] PE={pe} < {PE_LOWER_BAND} 低估 → 🟢 绿灯")
        set_green()
    elif pe > PE_UPPER_BAND:
        print(f"[LED] PE={pe} > {PE_UPPER_BAND} 高估 → 🔴 红灯")
        set_red()
    else:
        print(f"[LED] PE={pe} 合理 → 🔵 蓝灯")
        set_blue()


def restore():
    """从 .led_state 恢复灯色"""
    if not os.path.exists(LED_STATE_FILE):
        print("[LED] 无保存的状态 → 🟢 绿灯(默认)")
        all_off()
        set_green()
        return

    try:
        with open(LED_STATE_FILE) as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        print("[LED] 状态文件损坏 → 🟢 绿灯(默认)")
        all_off()
        set_green()
        return

    # daily mode: 07:00-15:29 & 周末 → 估值灯; 15:30后由爬虫切换为涨跌灯
    status = state.get("状态", "unknown")
    pe = state.get("PE")
    print(f"[LED] 恢复状态: {status} (PE={pe})")

    all_off()
    restore_valuation(pe)


def main():
    if len(sys.argv) != 2:
        print("用法: python3 led_scheduler.py {on|off}")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "off":
        all_off()
    elif cmd == "on":
        restore()
    else:
        print(f"未知命令: {cmd}")
        print("用法: python3 led_scheduler.py {on|off}")
        sys.exit(1)


if __name__ == "__main__":
    main()
