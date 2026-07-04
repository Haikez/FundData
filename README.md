# Fund007751 LED 看板

> 支付宝基金 **007751（景顺长城沪港深红利成长低波指数A）** 数据爬虫 + PE 估值分析 + OneCloud LED 硬件指示灯

基于 Python 的基金数据爬虫，定时抓取天天基金/蚂蚁财富数据，分析 PE 估值，并通过 **OneCloud（玩客云）的 RGB LED** 直观显示基金状态。

---

## 🚀 功能

| 功能 | 说明 |
|------|------|
| 📊 **基金数据爬取** | 实时估值、历史净值、阶段收益率、前十大持仓 |
| ⭐ **PE 估值分析** | 获取跟踪指数（931157）市盈率，判断低估/合理/高估 |
| 💡 **LED 硬件指示** | OneCloud 三色 LED 灯直观显示状态 |
| 📅 **双模式切换** | 工作日→涨跌灯 / 周末→估值灯 |
| 🌙 **自动熄灯** | 22:00-07:00 LED 自动熄灭 |
| ⏰ **定时运行** | crontab 每个交易日 15:30 自动执行 |

---

## 📋 LED 指示说明

### 交易日模式（周一至周五 15:30-22:00）

| 基金涨跌 | LED 颜色 | 含义 |
|---------|----------|------|
| 📈 涨 | 🔴 **红灯** | 今日净值上涨 |
| 📉 跌 | 🟢 **绿灯** | 今日净值下跌 |
| ➖ 平 | 🔵 **蓝灯** | 今日净值持平 |

### 周末 / 非交易时段模式

| PE 估值 | LED 颜色 | 含义 |
|---------|----------|------|
| 📗 PE < 7.5 | 🟢 **绿灯** | 低估，可分批买入 |
| 📙 PE 7.5 ~ 11.5 | 🔵 **蓝灯** | 合理，继续持有 |
| 📕 PE > 11.5 | 🔴 **红灯** | 高估，注意风险 |
| ⚠️ 异常 | 🔴 **红灯闪烁** | 数据获取失败 |

---

## 🏗 项目结构

```
FundData/
├── fund_crawler.py          # 主程序：数据爬取 + PE 分析 + LED 控制
├── led_scheduler.py         # LED 定时开关脚本（07:00恢复/22:00熄灯）
├── requirements.txt         # Python 依赖
├── setup.sh                 # OneCloud 一键部署脚本
├── deploy.sh                # 本地打包脚本
├── deploy_onecloud.py       # SSH 自动部署脚本
├── led控制伪代码.txt         # LED 原始控制指令
└── .gitignore               # Git 忽略规则
```

---

## 🛠 部署到 OneCloud

### 方式一：SSH 一键部署

```bash
# 从本机推送到 OneCloud
scp fund007751_*.tar.gz root@<OneCloud_IP>:/tmp/
ssh root@<OneCloud_IP>
cd /opt && tar xzf /tmp/fund007751_*.tar.gz
bash /opt/fund007751/setup.sh
```

### 方式二：Python 自动部署

```bash
python deploy_onecloud.py
```

### setup.sh 会自动完成

- ✅ 安装 Python3 + requests
- ✅ 校验 OneCloud LED 设备
- ✅ 添加 crontab 定时任务

---

## ⏰ 每日时间线

```
 07:00 ─── 恢复估值灯（🟢低估/🔵合理/🔴高估）
 09:30 ─── A 股开盘
 15:00 ─── A 股收盘
 15:30 ─── 爬虫运行 → 切换为涨跌灯（📈🔴/📉🟢）
 22:00 ─── 所有灯熄灭
```

### crontab 配置

```
30 15 * * 1-5  → fund_crawler.py      (交易日: 涨跌灯)
0  22 * * *    → led_scheduler.py off  (熄灯)
0  7  * * *    → led_scheduler.py on   (恢复: 估值灯)
```

---

## 📊 数据来源

| 数据 | API |
|------|-----|
| 实时估值 | `fundgz.1234567.com.cn` |
| 历史净值 | `api.fund.eastmoney.com` |
| 基金经理/持仓 | `fund.eastmoney.com/pingzhongdata/` |
| 基金基本信息 | `fund.eastmoney.com` |
| PE 估值参考 | 理杏仁 Lixinger / 中证指数 csindex.com.cn |

---

## 🧰 本地开发

```bash
# 安装依赖
pip install requests

# 运行爬虫
python fund_crawler.py

# 数据导出
# 每次运行自动生成 fund_007751_YYYYMMDD_HHMMSS.json
```

---

## 📝 依赖

- Python 3.6+
- requests
- OneCloud（玩客云）设备（用于 LED 指示）

---

## 📄 License

MIT
