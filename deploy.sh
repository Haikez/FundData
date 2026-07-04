#!/bin/bash
# =============================================================
# 基金007751 部署打包脚本
# 在 Windows/Linux 上运行，生成部署包
# 用法: bash deploy.sh
# =============================================================

set -e

PROJECT="fund007751"
VERSION=$(date +%Y%m%d)
OUTPUT="${PROJECT}_${VERSION}.tar.gz"

echo "============================================"
echo "  打包基金 007751 LED 看板项目"
echo "============================================"

# 拷贝到临时目录，排除不需要的文件
TMP_DIR=$(mktemp -d)
mkdir -p "${TMP_DIR}/${PROJECT}"

cp fund_crawler.py   "${TMP_DIR}/${PROJECT}/"
cp led_scheduler.py  "${TMP_DIR}/${PROJECT}/"
cp setup.sh          "${TMP_DIR}/${PROJECT}/"
cp led控制伪代码.txt  "${TMP_DIR}/${PROJECT}/"
cp -r pip_packages   "${TMP_DIR}/${PROJECT}/"

# 设置权限
chmod +x "${TMP_DIR}/${PROJECT}/setup.sh"

# 打包
cd "$TMP_DIR"
tar czf "$OUTPUT" "$PROJECT"
mv "$OUTPUT" "$OLDPWD/"
cd - > /dev/null

# 清理
rm -rf "$TMP_DIR"

echo "  ✅ 打包完成: ${OUTPUT}"
echo "  📦 包含文件:"
echo "    - fund_crawler.py   (主程序)"
echo "    - requirements.txt  (Python依赖)"
echo "    - setup.sh          (OneCloud一键部署)"
echo "    - led控制伪代码.txt  (LED说明)"
echo ""
echo "  🚀 部署到 OneCloud:"
echo "    scp ${OUTPUT} root@<OneCloud_IP>:/tmp/"
echo "    ssh root@<OneCloud_IP> \"cd /opt && tar xzf /tmp/${OUTPUT} && bash /opt/${PROJECT}/setup.sh\""
echo "============================================"
