# Fund007751 LED 看板

> 支付宝基金 **007751（景顺长城沪港深红利成长低波指数A）** 数据爬虫 + PE 估值分析 + OneCloud（玩客云）LED 硬件指示灯

基于 Python 的基金数据爬虫，定时抓取天天基金/蚂蚁财富数据，分析 PE 估值，并通过 **OneCloud（玩客云）的 RGB LED** 直观显示基金状态。

---

## 📦 项目说明

### 文件清单

| 文件 | 说明 |
|------|------|
| `fund_crawler.py` | **主程序** — 数据爬取 + PE 估值分析 + LED 控制 |
| `led_scheduler.py` | **LED 定时开关** — 07:00 恢复灯色 / 22:00 熄灯 |
| `setup.sh` | OneCloud 一键部署脚本 |
| `deploy.sh` | 本地打包脚本（生成 `.tar.gz` 部署包） |
| `deploy_onecloud.py` | SSH 自动部署脚本 |
| `requirements.txt` | Python 依赖清单 |
| `pip_packages/` | **离线 wheel 包** — `requests` 及其依赖的 `.whl` 文件 |

### pip_packages/ 来源

```bash
pip download requests -d pip_packages --only-binary=:all: --platform=any
```

OneCloud（Armbian）可能无法访问 PyPI，安装方式为直接解压 `.whl` 到 `site-packages`，不依赖网络。

---

## 📋 LED 指示说明

### 交易日模式（周一至周五 15:30-22:00）

| 基金涨跌 | LED 颜色 | 含义 |
|---------|----------|------|
| 📈 涨 | 🔴 **红灯** | 今日净值上涨 |
| 📉 跌 | 🟢 **绿灯** | 今日净值下跌 |
| ➖ 平 | 🔵 **蓝灯** | 今日净值持平 |

### 周末 / 非交易时段模式（07:00-15:30 & 周六日）

| PE 估值 | LED 颜色 | 含义 |
|---------|----------|------|
| 📗 PE < 7.5 | 🟢 **绿灯** | 低估，可分批买入 |
| 📙 PE 7.5 ~ 11.5 | 🔵 **蓝灯** | 合理，继续持有 |
| 📕 PE > 11.5 | 🔴 **红灯** | 高估，注意风险 |
| ⚠️ 异常 | 🔴 **红灯闪烁** | 数据获取失败 |

### 每日时间线

```
 07:00 ─── 恢复估值灯（🟢低估 / 🔵合理 / 🔴高估）
 09:30 ─── A 股开盘
 15:00 ─── A 股收盘
 15:30 ─── 爬虫运行 → 切换为涨跌灯（📈🔴 / 📉🟢）
 22:00 ─── 所有灯熄灭
```

---

## 🚀 部署到 OneCloud

```bash
# 1. 修改 deploy_onecloud.py 中的 IP 和密码
# 2. 运行自动部署
python deploy_onecloud.py
```

部署脚本会自动完成：
- ✅ 上传所有文件到 `/opt/fund007751/`
- ✅ 离线安装 Python 依赖（解压 `pip_packages/*.whl`）
- ✅ 添加 crontab 定时任务
- ✅ 首次运行爬虫验证

### crontab 最终配置

```
30 15 * * 1-5  → fund_crawler.py      (交易日：涨跌灯)
0  22 * * *    → led_scheduler.py off  (熄灯)
0  7  * * *    → led_scheduler.py on   (恢复：估值灯)
```

---

### 玩客云服务器目录结构

```
/opt/fund007751/
├── fund_crawler.py              # 主程序
├── led_scheduler.py             # LED 定时开关
├── setup.sh                     # 部署脚本
├── requirements.txt             # 依赖清单
├── led控制伪代码.txt             # LED 原始说明
├── pip_packages/                # 离线 wheel 包
│   ├── certifi-*.whl
│   ├── charset_normalizer-*.whl
│   ├── idna-*.whl
│   ├── requests-*.whl
│   └── urllib3-*.whl
├── .led_state                   # 上次 LED 状态快照（JSON）
├── fund_007751_*.json           # 每日净值数据归档
└──                              # ── 以下由 setup.sh 创建 ──
/var/log/fund007751/
    ├── crawler.log              # 爬虫运行日志
    └── led.log                  # LED 定时开关日志
```

---

## 🧰 本地运行

```bash
pip install -r requirements.txt
python fund_crawler.py
```

每次运行自动导出 `fund_007751_YYYYMMDD_HHMMSS.json`。

---

## 📊 数据来源

| 数据 | API |
|------|-----|
| 实时估值 | `fundgz.1234567.com.cn` |
| 历史净值 | `api.fund.eastmoney.com` |
| 基金经理/持仓 | `fund.eastmoney.com/pingzhongdata/` |
| 基金基本信息 | `fund.eastmoney.com` |
| PE 估值参考 | 理杏仁 / 中证指数 `csindex.com.cn` |

---

## 🔧 硬件要求

- **OneCloud（玩客云）** 设备，刷 Armbian 系统
- 板载三色 RGB LED（`/sys/class/leds/onecloud:{red,green,blue}:alive`）
- Python 3.6+

---

## 📄 License

MIT
