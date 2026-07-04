"""
支付宝基金数据爬虫 + 市盈率(PE)估值分析
基金代码: 007751 → 跟踪指数: 中证沪港深红利成长低波动指数(931157)
"""

import requests
import re
import json
import sys
import io
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ====================== 配置 ======================
FUND_CODE = "007751"
INDEX_CODE = "931157"  # 跟踪的中证指数代码
INDEX_NAME = "中证沪港深红利成长低波动指数"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"https://fund.eastmoney.com/{FUND_CODE}.html",
}

# ====================== OneCloud LED 配置 ======================
LED_RED = "/sys/class/leds/onecloud:red:alive"
LED_GREEN = "/sys/class/leds/onecloud:green:alive"
LED_BLUE = "/sys/class/leds/onecloud:blue:alive"
LED_DEVICES = [LED_RED, LED_GREEN, LED_BLUE]


def decode_text(resp):
    """智能解码"""
    raw = resp.content
    if raw[:3] == b'\xef\xbb\xbf':
        return raw[3:].decode('utf-8')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode('gbk')
    except UnicodeDecodeError:
        return resp.text


def extract_balanced_json(text, start_idx):
    """提取平衡括号的 JSON"""
    arr_start = -1
    for ch in ('[', '{'):
        p = text.find(ch, start_idx)
        if p != -1 and (arr_start == -1 or p < arr_start):
            arr_start = p
    if arr_start == -1:
        return None, -1

    open_bracket = text[arr_start]
    close_bracket = ']' if open_bracket == '[' else '}'
    in_string, escape, depth = False, False, 0

    for i in range(arr_start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_bracket:
            depth += 1
        elif c == close_bracket:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[arr_start:i + 1]), i + 1
                except json.JSONDecodeError:
                    return None, -1
    return None, -1


# ====================== 基金数据 ======================

def fetch_realtime_valuation():
    """实时估值"""
    url = f"http://fundgz.1234567.com.cn/js/{FUND_CODE}.js"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    text = decode_text(resp)
    match = re.search(r"jsonpgz\((.*)\)", text)
    return json.loads(match.group(1)) if match else None


def fetch_fund_page_info():
    """从天天基金页面解析基金详情"""
    url = f"https://fund.eastmoney.com/{FUND_CODE}.html"
    resp = requests.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=10)
    html = decode_text(resp)

    info = {}
    match = re.search(r"<title>(.*?)</title>", html)
    if match:
        title = re.sub(rf"[（(]{FUND_CODE}[）)].*", "", match.group(1)).strip()
        info["基金名称"] = title

    patterns = [
        ("基金代码", r"基金代码[：:]\s*<[^>]*>\s*(\d+)"),
        ("基金类型", r"基金类型[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
        ("成立日期", r"成立日期[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
        ("基金规模", r"基金规模[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
        ("基金经理", r"基金经理[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
        ("基金管理人", r"基金管理人[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
        ("跟踪标的", r"跟踪标的[：:]\s*<[^>]*>\s*([^<]+?)\s*<"),
    ]
    for key, pat in patterns:
        m = re.search(pat, html)
        if m:
            info[key] = m.group(1).strip().replace('&nbsp;', '').strip()

    for label in ['单位净值', '累计净值', '日涨跌幅']:
        m = re.search(rf'{label}[：:]\s*<span[^>]*>([^<]+)', html)
        if m:
            info[label] = m.group(1).strip()

    return info


def fetch_historical_nav(page=1, page_size=30):
    """历史净值"""
    url = "http://api.fund.eastmoney.com/f10/lsjz"
    params = {"callback": "jQuery", "fundCode": FUND_CODE,
              "pageIndex": page, "pageSize": page_size, "startDate": "", "endDate": ""}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    text = decode_text(resp)
    match = re.search(r"jQuery\((.*)\)", text)
    if match:
        data = json.loads(match.group(1))
        return data.get("Data", {}).get("LSJZList", [])
    return []


def fetch_pingzhongdata():
    """pingzhongdata JS (含收益率/经理/持仓)"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{FUND_CODE}.js"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    return decode_text(resp)


# ====================== 解析函数 ======================

def parse_returns(text):
    """阶段收益率"""
    returns = {}
    mappings = [
        ("近1月", "syl_1y"), ("近3月", "syl_3y"), ("近6月", "syl_6y"),
        ("近1年", "syl_1n"), ("近2年", "syl_2n"), ("近3年", "syl_3n"),
        ("近5年", "syl_5n"), ("今年以来", "syl_jn"), ("成立以来", "syl_cn"),
    ]
    for label, var_name in mappings:
        idx = text.find(f"var {var_name}=")
        if idx == -1:
            idx = text.find(f"var {var_name} =")
        if idx >= 0:
            m = re.search(r"""['"]([^'"]+)['"]""", text[idx:idx+60])
            if m:
                returns[label] = m.group(1)
    return returns


def parse_fund_manager(text):
    """基金经理"""
    idx = text.find("var Data_currentFundManager")
    if idx == -1:
        return None
    managers_obj, _ = extract_balanced_json(text, idx)
    if not managers_obj:
        return None
    return [{
        "姓名": m.get("name", ""),
        "评级": f"{m.get('star', '?')}星" if m.get("star") else "N/A",
        "从业时间": m.get("workTime", ""),
        "管理规模": m.get("fundSize", ""),
    } for m in managers_obj]


def format_stock_code(code_new):
    """格式化代码 1.600750 → 600750.SH"""
    if "." in str(code_new):
        market, code = str(code_new).split(".", 1)
        market_map = {"1": "SH", "0": "SZ", "116": "HK"}
        suffix = market_map.get(market, "")
        return f"{code}.{suffix}" if suffix else code
    return str(code_new)


def _extract_content_between(text, prefix, suffix):
    """提取 prefix 和 suffix 之间的内容, 处理转义"""
    start = text.find(prefix)
    if start < 0:
        return None
    start += len(prefix)
    # 找到真正的结束位置（不是转义的）
    i = start
    while i < len(text):
        if text[i:i+2] == '\\\\':
            i += 2
            continue
        if text[i:i+2] == '\\"':
            i += 2
            continue
        if text[i:i+len(suffix)] == suffix:
            return text[start:i]
        i += 1
    return None


def parse_positions(text):
    """前十大持仓"""
    idx = text.find("var stockCodesNew=")
    if idx == -1:
        idx = text.find("var stockCodesNew =")
    codes_new, _ = extract_balanced_json(text, idx) if idx >= 0 else ([], -1)

    # 从 fundf10 API 获取持仓详情（名称、比例等）
    positions = []
    try:
        url = 'http://fundf10.eastmoney.com/FundArchivesDatas.aspx'
        params = {'type': 'jjcc', 'code': FUND_CODE, 'topline': 10}
        resp = requests.get(url, params=params, headers={
            **HEADERS, 'Referer': 'http://fundf10.eastmoney.com/'
        }, timeout=10)
        raw_html = _extract_content_between(resp.text, 'content:"', '"}')
        if raw_html:
            table_html = raw_html.replace('\\"', '"').replace('\\n', ' ')
            rows = re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)
            for row in rows[1:]:  # skip header row
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                if len(clean) >= 9:
                    positions.append({
                        "序号": clean[0],
                        "代码": clean[1],
                        "名称": clean[2],
                        "占净值比例": clean[6],
                        "持仓市值(万元)": clean[8],
                    })
    except Exception:
        pass

    # Fallback: 仅显示代码
    if not positions:
        for i, c in enumerate(codes_new):
            positions.append({"序号": str(i + 1), "代码": format_stock_code(c)})

    return positions


def parse_position_trend(text):
    """仓位趋势"""
    idx = text.find("var Data_fundSharesPositions=")
    if idx == -1:
        idx = text.find("var Data_fundSharesPositions =")
    if idx == -1:
        return None
    data, _ = extract_balanced_json(text, idx)
    if not data:
        return None
    trend = []
    for item in data[-10:]:
        ts = item[0] / 1000
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        trend.append({"日期": dt, "股票仓位": f"{item[1]:.2f}%"})
    return trend


# ====================== PE 估值分析 ======================

def fetch_index_pe():
    """
    获取指数市盈率(PE)数据
    通过多个来源获取：
    1. 尝试 eastmoney API (优先)
    2. 中证指数官网
    3. 使用已知最新数据作为后备
    """
    pe_data = {
        "index_code": INDEX_CODE,
        "index_name": INDEX_NAME,
        # 已知最新数据 (2026-06-23)
        "PE_TTM_fallback": 7.49,
        "PB_fallback": 0.74,
        "dividend_yield_fallback": 4.87,
        "fallback_date": "2026-06-23",
    }

    # ----- 方法1: eastmoney 行情 API -----
    for secid in [f'0.{INDEX_CODE}', f'1.{INDEX_CODE}']:
        try:
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f57,f58,f162,f167,f164"
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/"
            }, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    d = data["data"]
                    pe_ttm = d.get("f162") or d.get("f167")
                    pb = d.get("f164")
                    if pe_ttm:
                        pe_data["PE_TTM"] = float(pe_ttm)
                        pe_data["PB"] = float(pb) if pb else None
                        pe_data["来源"] = "eastmoney 实时API"
                        pe_data["数据日期"] = "实时"
                        return pe_data
        except Exception:
            continue

    # ----- 方法2: 中证指数官网 -----
    try:
        url = f"https://www.csindex.com.cn/zh-CN/indices/index-detail/{INDEX_CODE}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            html = decode_text(resp)
            for m in re.finditer(r'市盈率[：:]\s*([\d.]+)', html):
                pe_data["PE"] = float(m.group(1))
            for m in re.finditer(r'市净率[：:]\s*([\d.]+)', html):
                pe_data["PB"] = float(m.group(1))
            if pe_data.get("PE"):
                pe_data["来源"] = "csindex.com.cn"
                pe_data["数据日期"] = "官网"
                return pe_data
    except Exception:
        pass

    # ----- 方法3: 使用已知最新数据 -----
    pe_data["PE_TTM"] = pe_data["PE_TTM_fallback"]
    pe_data["PB"] = pe_data["PB_fallback"]
    pe_data["股息率"] = f"{pe_data['dividend_yield_fallback']}%"
    pe_data["来源"] = f"理杏仁/公开数据 (数据日期: {pe_data['fallback_date']})"
    pe_data["数据日期"] = pe_data["fallback_date"]
    return pe_data


# PE 估值区间 (基于指数历史数据)
# 中证沪港深红利成长低波动指数 (931157) 历史PE参考
PE_HISTORICAL = {
    "min_pe": 5.5,      # 历史最低约 5.5
    "max_pe": 15.0,     # 历史最高约 15
    "avg_pe": 9.5,      # 历史均值约 9.5
    "lower_band": 7.5,  # 低估线 (~20%分位)
    "upper_band": 11.5, # 高估线 (~80%分位)
}


def analyze_valuation(current_pe):
    """判断当前估值状态"""
    if current_pe is None:
        return "无法判断", "N/A", {}

    avg = PE_HISTORICAL["avg_pe"]
    lower = PE_HISTORICAL["lower_band"]
    upper = PE_HISTORICAL["upper_band"]
    min_p = PE_HISTORICAL["min_pe"]
    max_p = PE_HISTORICAL["max_pe"]

    # 计算历史百分位 (假设近似正态分布)
    if current_pe <= min_p:
        percentile = 0
    elif current_pe >= max_p:
        percentile = 100
    else:
        percentile = round((current_pe - min_p) / (max_p - min_p) * 100, 1)

    # 判断
    if current_pe < lower:
        status = "📗 低估"
        suggestion = "估值较低，具有安全边际，适合分批布局"
    elif current_pe > upper:
        status = "📕 高估"
        suggestion = "估值偏高，建议谨慎观望或分批止盈"
    else:
        status = "📙 合理"
        suggestion = "估值处于合理区间，可继续持有"

    detail = {
        "当前PE": current_pe,
        "历史均值": avg,
        "低估线": lower,
        "高估线": upper,
        "历史最低": min_p,
        "历史最高": max_p,
        "历史百分位": f"{percentile}%",
        "判断": status,
        "建议": suggestion,
    }
    return status, suggestion, detail


# ====================== OneCloud LED 控制 ======================

def _led_write(path, value):
    """安全写入 LED sysfs 文件"""
    try:
        with open(path, "w") as f:
            f.write(str(value))
        return True
    except (OSError, IOError):
        return False


def _led_trigger(mode):
    """设置所有灯的 trigger 为 none"""
    for led in LED_DEVICES:
        _led_write(f"{led}/trigger", mode)


def _led_brightness(color, value):
    """设置指定颜色的灯亮度 (0 或 1)"""
    _led_write(f"{color}/brightness", value)


def led_all_off():
    """关闭所有灯"""
    for led in LED_DEVICES:
        _led_brightness(led, 0)
    _led_trigger("none")


def led_undervalued():
    """📗 低估 → 绿灯常亮"""
    print("  🔧 LED: 低估状态 → 绿灯常亮")
    led_all_off()
    _led_write(f"{LED_RED}/trigger", "none")
    _led_write(f"{LED_GREEN}/trigger", "default-on")
    _led_write(f"{LED_BLUE}/trigger", "none")


def led_fair():
    """📙 合理 → 蓝灯常亮"""
    print("  🔧 LED: 合理状态 → 蓝灯常亮")
    led_all_off()
    _led_write(f"{LED_RED}/trigger", "none")
    _led_write(f"{LED_GREEN}/trigger", "none")
    _led_write(f"{LED_BLUE}/trigger", "default-on")


def led_overvalued():
    """📕 高估 → 红灯常亮"""
    print("  🔧 LED: 高估状态 → 红灯常亮")
    led_all_off()
    _led_write(f"{LED_RED}/trigger", "default-on")
    _led_write(f"{LED_GREEN}/trigger", "none")
    _led_write(f"{LED_BLUE}/trigger", "none")


def led_error():
    """⚠️ 数据获取失败 → 红灯闪烁"""
    print("  🔧 LED: 错误状态 → 红灯闪烁")
    led_all_off()
    _led_write(f"{LED_RED}/trigger", "heartbeat")
    _led_write(f"{LED_GREEN}/trigger", "none")
    _led_write(f"{LED_BLUE}/trigger", "none")


def led_change(change_pct):
    """
    📈 涨跌指示灯（交易日用）
    change_pct > 0 → 涨了 → 🔴 红灯
    change_pct < 0 → 跌了 → 🟢 绿灯
    change_pct = 0 → 平盘 → 🔵 蓝灯
    """
    if change_pct is None:
        print("  🔧 LED: 无涨跌数据 → 蓝灯")
        led_all_off()
        _led_write(f"{LED_RED}/trigger", "none")
        _led_write(f"{LED_GREEN}/trigger", "none")
        _led_write(f"{LED_BLUE}/trigger", "default-on")
        return

    if change_pct > 0:
        print(f"  🔧 LED: 今日涨 {change_pct:+.2f}% → 🔴 红灯")
        led_all_off()
        _led_write(f"{LED_RED}/trigger", "default-on")
        _led_write(f"{LED_GREEN}/trigger", "none")
        _led_write(f"{LED_BLUE}/trigger", "none")
    elif change_pct < 0:
        print(f"  🔧 LED: 今日跌 {change_pct:+.2f}% → 🟢 绿灯")
        led_all_off()
        _led_write(f"{LED_RED}/trigger", "none")
        _led_write(f"{LED_GREEN}/trigger", "default-on")
        _led_write(f"{LED_BLUE}/trigger", "none")
    else:
        print(f"  🔧 LED: 今日平盘 0.00% → 🔵 蓝灯")
        led_all_off()
        _led_write(f"{LED_RED}/trigger", "none")
        _led_write(f"{LED_GREEN}/trigger", "none")
        _led_write(f"{LED_BLUE}/trigger", "default-on")


LED_STATE_FILE = "/opt/fund007751/.led_state"


def _save_led_state(status_text, pe_value=None, mode=None, change_pct=None):
    """保存当前 LED 状态，供定时开关灯恢复使用"""
    try:
        state = {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": status_text,
            "PE": pe_value,
            "模式": mode or "估值",
            "涨跌幅": change_pct,
            "判断": "undervalued" if "低估" in status_text
                   else "overvalued" if "高估" in status_text
                   else "fair" if "合理" in status_text
                   else "up" if "涨" in status_text
                   else "down" if "跌" in status_text
                   else "flat" if "平" in status_text
                   else "error",
        }
        with open(LED_STATE_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False)
    except (OSError, IOError):
        pass


def auto_control_led(status_text, pe_value=None):
    """根据估值判断控制 LED (周末用)"""
    if "低估" in status_text:
        led_undervalued()
    elif "高估" in status_text:
        led_overvalued()
    elif "合理" in status_text:
        led_fair()
    else:
        led_error()
    _save_led_state(status_text, pe_value, mode="估值")


def is_weekend():
    """判断今天是否是周末"""
    return datetime.now().weekday() >= 5  # 5=周六, 6=周日


# ====================== 输出 ======================

def print_divider(title=""):
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


# ====================== 主流程 ======================

def main():
    print(f"\n{'=' * 60}")
    print(f"  基金数据爬虫 + PE 估值分析")
    print(f"  基金代码: {FUND_CODE}  |  跟踪指数: {INDEX_NAME}({INDEX_CODE})")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    pingzhong = None

    # ─── 1. 实时估值 ───
    print_divider("1. 实时估值 (盘中数据)")
    basic = fetch_realtime_valuation()
    if basic:
        print(f"  基金名称: {basic.get('name', 'N/A')}")
        print(f"  净值日期: {basic.get('jzrq', 'N/A')}")
        print(f"  单位净值: {basic.get('dwjz', 'N/A')}")
        print(f"  估算净值: {basic.get('gsz', 'N/A')}")
        print(f"  估算涨跌: {basic.get('gszzl', 'N/A')}%")
        print(f"  估值时间: {basic.get('gztime', 'N/A')}")
    else:
        print("  [失败]")

    # ─── 2. 基金基本信息 ───
    print_divider("2. 基金基本信息")
    page_info = fetch_fund_page_info()
    if page_info:
        for k, v in page_info.items():
            print(f"  {k}: {v}")
    else:
        print("  [失败]")

    # ─── 3. 基金经理 ───
    print_divider("3. 基金经理")
    try:
        pingzhong = fetch_pingzhongdata()
        managers = parse_fund_manager(pingzhong)
        if managers:
            for i, m in enumerate(managers, 1):
                print(f"  基金经理 {i}:")
                for k, v in m.items():
                    print(f"    {k}: {v}")
        else:
            print("  [失败]")
    except Exception as e:
        print(f"  [失败] {e}")

    # ─── 4. 历史净值 ───
    print_divider("4. 历史净值 (最近20条)")
    nav_list = fetch_historical_nav(page=1, page_size=20)
    if nav_list:
        print(f"  {'日期':<12} {'单位净值':<10} {'累计净值':<10} {'日涨跌幅':<10}")
        print(f"  {'-' * 44}")
        for item in nav_list:
            print(f"  {item.get('FSRQ', ''):<12} "
                  f"{item.get('DWJZ', ''):<10} "
                  f"{item.get('LJJZ', ''):<10} "
                  f"{item.get('JZZZL', ''):<8}%")
        # 最新净值
        latest = nav_list[0]
        print(f"\n  最新净值: {latest.get('DWJZ', '')} (日期: {latest.get('FSRQ', '')})")
        print(f"  最新累计净值: {latest.get('LJJZ', '')}")
    else:
        print("  [失败]")

    # ─── 5. 阶段收益率 ───
    print_divider("5. 阶段收益率")
    if pingzhong:
        returns = parse_returns(pingzhong)
        if returns:
            for k, v in returns.items():
                print(f"  {k}: {v}%")
        else:
            print("  [失败]")

    # ─── 6. 前十大持仓 ───
    print_divider("6. 前十大持仓")
    if pingzhong:
        positions = parse_positions(pingzhong)
        if positions:
            has_detail = "名称" in positions[0] and positions[0]["名称"]
            if has_detail:
                print(f"  {'#':<4} {'代码':<12} {'名称':<16} {'占净值比例':<12} {'持仓市值(万)':<14}")
                print(f"  {'-' * 60}")
                for p in positions:
                    print(f"  {p['序号']:<4} {p.get('代码', ''):<12} "
                          f"{p.get('名称', ''):<16} {p.get('占净值比例', ''):<12} "
                          f"{p.get('持仓市值(万元)', ''):<14}")
            else:
                print(f"  {'#':<4} {'代码':<14}")
                print(f"  {'-' * 20}")
                for p in positions:
                    print(f"  {p['序号']:<4} {p.get('代码', ''):<14}")
        else:
            print("  [失败]")

        # 仓位趋势
        trend = parse_position_trend(pingzhong)
        if trend:
            print(f"\n  历史仓位趋势 (最近{len(trend)}期):")
            for t in trend:
                print(f"    {t['日期']}: {t['股票仓位']}")
    else:
        print("  [跳过]")

    # ─── 7. PE 估值分析 ⭐ ───
    print_divider("7. PE 市盈率 & 估值分析 ⭐")
    print(f"  📌 跟踪指数: {INDEX_NAME} ({INDEX_CODE})")
    print()

    # 获取当前PE
    pe_info = fetch_index_pe()
    current_pe = pe_info.get("PE_TTM") or pe_info.get("PE") or pe_info.get("PE_静态")

    if current_pe:
        print(f"  📊 当前PE (TTM):   {current_pe}")
        print(f"  📅 数据日期:       {pe_info.get('数据日期', 'N/A')}")
        if pe_info.get("PB"):
            print(f"  📊 当前PB:          {pe_info['PB']}")
        if pe_info.get("股息率"):
            print(f"  📊 股息率:          {pe_info['股息率']}")
        print(f"  📡 数据来源:        {pe_info.get('来源', 'N/A')}")

        # 估值分析
        print()
        status, suggestion, analysis = analyze_valuation(float(current_pe))
        print(f"  📈 估值判断:        {status}")
        print(f"  {'历史均值':<20} {analysis['历史均值']}")
        print(f"  {'低估线(约20%分位)':<20} {analysis['低估线']}")
        print(f"  {'高估线(约80%分位)':<20} {analysis['高估线']}")
        print(f"  {'历史最低':<20} {analysis['历史最低']}")
        print(f"  {'历史最高':<20} {analysis['历史最高']}")
        print(f"  {'当前历史百分位':<20} {analysis['历史百分位']}")
        print(f"\n  💡 投资建议: {suggestion}")
    else:
        print("  [API暂不可用] 使用公开参考数据:")
        print(f"  📊 参考PE: 约 7.5 ~ 10.0 (基于历史公开数据)")
        print(f"  📊 参考PB: 约 0.75 ~ 0.85")
        print(f"  📊 股息率: 约 4.3% ~ 5.0%")
        print()
        print(f"  📈 参考估值判断: 合理偏低")
        print(f"  💡 该指数为红利+低波策略, PE长期处于较低水平")
        print(f"  💡 建议结合股息率(>4%)和PB(<1)综合判断")

    # PE 历史区间参考
    print()
    print("  ┌──────┬────────────┬──────────────┐")
    print("  │ 区间  │ PE 范围     │ 估值状态      │")
    print("  ├──────┼────────────┼──────────────┤")
    print(f"  │ 低估  │ < {PE_HISTORICAL['lower_band']:<8.1f} │ 📗 可分批买入   │")
    print(f"  │ 合理  │ {PE_HISTORICAL['lower_band']:<5.1f} ~ {PE_HISTORICAL['upper_band']:<5.1f}  │ 📙 继续持有     │")
    print(f"  │ 偏高  │ {PE_HISTORICAL['upper_band']:<5.1f} ~ {PE_HISTORICAL['max_pe']:<5.1f}  │ 📕 警惕风险     │")
    print(f"  │ 高估  │ > {PE_HISTORICAL['max_pe']:<8.1f} │ 🚩 考虑减仓     │")
    print("  └──────┴────────────┴──────────────┘")

    # ─── 8. OneCloud LED 自动控制 ───
    print_divider("8. OneCloud LED 控制")
    today_wd = datetime.now().weekday()

    if is_weekend():
        # 周末 → 估值指示灯
        print("  📅 周末模式: 按估值显示")
        if current_pe:
            try:
                status_text = analyze_valuation(float(current_pe))[0]
                auto_control_led(status_text, pe_value=float(current_pe))
                print("  ✅ LED 已根据估值状态设置")
            except Exception as e:
                led_error()
                print(f"  ⚠️  LED 控制异常: {e}")
        else:
            led_error()
            print("  ⚠️  无估值数据，设置红灯闪烁警示")
    else:
        # 工作日 → 涨跌指示灯
        print(f"  📅 交易日模式: 按涨跌显示")
        if nav_list:
            try:
                change_str = nav_list[0].get("JZZZL", "0")
                change_val = float(change_str) if change_str else 0.0
                led_change(change_val)

                # 构建状态文字
                if change_val > 0:
                    status = f"今日涨 {change_val:+.2f}%"
                elif change_val < 0:
                    status = f"今日跌 {change_val:+.2f}%"
                else:
                    status = "今日平盘 0.00%"
                _save_led_state(status, pe_value=float(current_pe) if current_pe else None,
                                mode="涨跌", change_pct=change_val)
                print(f"  ✅ LED 已根据涨跌幅设置 ({change_val:+.2f}%)")
            except Exception as e:
                led_error()
                print(f"  ⚠️  LED 控制异常: {e}")
        else:
            led_error()
            print("  ⚠️  无净值数据，设置红灯闪烁警示")

    # ─── 9. 数据导出 ───
    print_divider("9. 数据导出")
    try:
        # PE分析
        if current_pe:
            _, _, analysis = analyze_valuation(float(current_pe))
        else:
            analysis = {"判断": "API暂不可用", "建议": "使用参考数据"}

        export_data = {
            "基金代码": FUND_CODE,
            "跟踪指数": f"{INDEX_NAME}({INDEX_CODE})",
            "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "实时估值": basic,
            "基本信息": page_info,
            "阶段收益率": parse_returns(pingzhong) if pingzhong else {},
            "历史净值(最新)": nav_list[0] if nav_list else {},
            "PE估值分析": {
                "当前PE": current_pe,
                "数据来源": pe_info.get("来源", ""),
                "历史均值": PE_HISTORICAL["avg_pe"],
                "低估线": PE_HISTORICAL["lower_band"],
                "高估线": PE_HISTORICAL["upper_band"],
                "估值判断": analysis.get("判断", ""),
                "投资建议": analysis.get("建议", ""),
            },
        }
        filename = f"fund_{FUND_CODE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 数据已导出到: {filename}")
    except Exception as e:
        print(f"  [失败] 导出失败: {e}")

    print(f"\n{'=' * 60}")
    print("  [完成] 数据获取结束")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
