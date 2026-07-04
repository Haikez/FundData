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
| `pip_packages/` | **离线 wheel 包** — `requests` 及其依赖的 `.whl` 文件，供无网络的 OneCloud 离线安装 |

### pip_packages/ 来源

`pip_packages/` 目录包含 `requests` 及其依赖（`urllib3`, `certifi`, `idna`, `charset_normalizer`）的纯 Python wheel 包，通过以下命令生成：

```bash
pip download requests -d pip_packages --only-binary=:all: --platform=any
```

**用途**：OneCloud（Armbian）可能无法访问 PyPI 或 Debian 镜像源，`setup.sh` 会自动降级到离线解压这些 `.whl` 文件到 `site-packages`。

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

### 方式一：SSH 一键部署（打包传输）

```bash
# 本地打包
bash deploy.sh

# 上传到 OneCloud
scp fund007751_*.tar.gz root@<OneCloud_IP>:/tmp/
ssh root@<OneCloud_IP>
cd /opt
tar xzf /tmp/fund007751_*.tar.gz
bash /opt/fund007751/setup.sh
```

### 方式二：Python 自动部署

```bash
# 先修改 deploy_onecloud.py 中的 IP 和密码以及压缩包的名称
python deploy_onecloud.py
```

### setup.sh 会自动完成

- ✅ 安装 Python3 依赖（在线 pip → 离线 wheel，自动降级）
- ✅ 校验 OneCloud LED 设备
- ✅ 添加 crontab 定时任务

> **依赖安装优先级**：
> ```
> ① pip3 install requests         (在线，最快)
> ② python3 -m pip install ...    (在线，备选)
> ③ 解压 pip_packages/*.whl      (离线，无网络时)
> ④ apt install python3-pip       (最后手段)
> ```

### crontab 最终配置

```
30 15 * * 1-5  → fund_crawler.py      (交易日：涨跌灯)
0  22 * * *    → led_scheduler.py off  (熄灯)
0  7  * * *    → led_scheduler.py on   (恢复：估值灯)
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
