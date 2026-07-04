#!/bin/bash
# =============================================================
# 离线安装 Python 依赖 (被 deploy_onecloud.py 远程调用)
# =============================================================

PROJECT_DIR="/opt/fund007751"
LOG_DIR="/var/log/fund007751"

mkdir -p "$LOG_DIR"

if ! command -v python3 &>/dev/null; then
    echo "  ❌ 未找到 python3"
    exit 1
fi

WHEEL_DIR="${PROJECT_DIR}/pip_packages"
if ! ls "$WHEEL_DIR"/*.whl &>/dev/null 2>&1; then
    echo "  ❌ pip_packages/ 为空，请先获取 wheel 包"
    exit 1
fi

cat > /tmp/install_wheels.py << 'PYEOF'
import zipfile, glob, os, sys

paths = ["/usr/local/lib/python3.11/dist-packages",
         "/usr/lib/python3/dist-packages",
         "/usr/lib/python3.11/dist-packages"]
site_pkg = next((p for p in paths if os.path.isdir(p)), None)
if not site_pkg:
    import site as _site
    site_pkg = _site.getsitepackages()[0]

wheels = sorted(glob.glob("/opt/fund007751/pip_packages/*.whl"))
if not wheels:
    print("  ❌ 未找到 wheel 包")
    sys.exit(1)

for w in wheels:
    name = os.path.basename(w)
    print(f"  解压 {name}...")
    with zipfile.ZipFile(w) as zf:
        zf.extractall(site_pkg)

try:
    import requests
    print(f"  ✅ requests {requests.__version__}")
except Exception as e:
    print(f"  ❌ {e}")
    sys.exit(1)
PYEOF

python3 /tmp/install_wheels.py
rm -f /tmp/install_wheels.py
