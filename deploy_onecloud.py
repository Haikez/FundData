"""
OneCloud 自动部署脚本
上传部署包并执行 setup.sh
"""
import paramiko
import sys
import io
import os
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "192.168.1.104"
PORT = 22
USER = "root"
PASSWORD = "xxxx"
LOCAL_PACKAGE = "fund007751_20260704.tar.gz"
REMOTE_DIR = "/opt"
LOG_DIR = "/var/log/fund007751"


def run_ssh(ssh, command, label="", timeout=60):
    """执行SSH命令并打印输出，返回 (exit_code, stdout, stderr)"""
    if label:
        print(f"\n  → {label}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n'):
            print(f"    {line}")
    if err and exit_code != 0:
        for line in err.split('\n'):
            print(f"    ⚠️ {line}")
    return exit_code, out, err


def upload_pip_wheels(sftp):
    """上传 pip_packages/ 离线 wheel 包"""
    local_dir = os.path.join(os.path.dirname(__file__), "pip_packages")
    remote_dir = os.path.join(REMOTE_DIR, "fund007751", "pip_packages")
    if not os.path.isdir(local_dir):
        print("  ⚠️  本地 pip_packages/ 不存在，跳过离线包上传")
        return

    # 确保远程目录存在
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    for whl in sorted(os.listdir(local_dir)):
        if whl.endswith(".whl"):
            local = os.path.join(local_dir, whl)
            remote = os.path.join(remote_dir, whl)
            sftp.put(local, remote)
            print(f"  ✓ pip_packages/{whl}")


def offline_install(ssh):
    """离线安装依赖"""
    installer = """#!/usr/bin/env python3
import zipfile, glob, os, sys
paths = ["/usr/local/lib/python3.11/dist-packages", "/usr/lib/python3/dist-packages"]
site_pkg = next((p for p in paths if os.path.isdir(p)), None)
if not site_pkg:
    import site as _site
    site_pkg = _site.getsitepackages()[0]
print(f"  目标路径: {site_pkg}")
wheels = sorted(glob.glob("/opt/fund007751/pip_packages/*.whl"))
if not wheels:
    print("  ❌ 无离线包")
    sys.exit(1)
for w in wheels:
    name = os.path.basename(w)
    print(f"  解压 {name}...")
    with zipfile.ZipFile(w) as zf:
        zf.extractall(site_pkg)
try:
    import requests
    print(f"  ✅ requests OK: {requests.__version__}")
except Exception as e:
    print(f"  ❌ {e}")
    sys.exit(1)
"""
    # 写入安装脚本到远程
    sftp = ssh.open_sftp()
    with sftp.open("/opt/fund007751/install_deps.py", "w") as f:
        f.write(installer)
    sftp.close()

    # 执行
    run_ssh(ssh, "python3 /opt/fund007751/install_deps.py", "离线安装依赖")
    run_ssh(ssh, "rm -f /opt/fund007751/install_deps.py", "清理临时脚本")


def main():
    print("=" * 56)
    print("  🚀 OneCloud 自动部署 - 基金007751 LED看板")
    print(f"  目标: {USER}@{HOST}:{PORT}")
    print("=" * 56)

    # 连接 SSH
    print("\n[1/4] 连接 SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=10)
        print("  ✅ SSH 连接成功")
    except Exception as e:
        print(f"  ❌ SSH 连接失败: {e}")
        sys.exit(1)

    # 上传文件
    print("\n[2/4] 上传文件...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(REMOTE_DIR)
    except FileNotFoundError:
        run_ssh(ssh, f"mkdir -p {REMOTE_DIR}", "创建远程目录")

    # 上传核心文件
    core_files = ["fund_crawler.py", "led_scheduler.py", "requirements.txt",
                  "setup.sh", "led控制伪代码.txt"]
    try:
        sftp.stat(f"{REMOTE_DIR}/fund007751")
    except FileNotFoundError:
        sftp.mkdir(f"{REMOTE_DIR}/fund007751")

    for f in core_files:
        local = os.path.join(os.path.dirname(__file__), f)
        if os.path.exists(local):
            sftp.put(local, f"{REMOTE_DIR}/fund007751/{f}")
            print(f"  ✓ {f}")

    # 上传离线包
    upload_pip_wheels(sftp)
    sftp.close()

    # 设置权限
    run_ssh(ssh, f"chmod +x {REMOTE_DIR}/fund007751/setup.sh", "设置执行权限")

    # 安装依赖
    print("\n[3/4] 安装依赖...")
    code, out, err = run_ssh(ssh, f"cd {REMOTE_DIR}/fund007751 && bash setup.sh", "执行 setup.sh")

    # 无论 setup.sh 是否成功，确保日志目录存在
    run_ssh(ssh, f"mkdir -p {LOG_DIR}", "创建日志目录")

    # 验证依赖
    code, out, err = run_ssh(ssh, 'python3 -c "import requests; print(requests.__version__)"', "验证依赖")
    if code != 0:
        print("  pip 安装失败，切换到离线安装...")
        offline_install(ssh)

    # 设置 crontab
    print("\n[4/4] 设置定时任务...")
    cron_jobs = [
        f"30 15 * * 1-5 cd {REMOTE_DIR}/fund007751 && python3 fund_crawler.py >> {LOG_DIR}/crawler.log 2>&1",
        f"0 22 * * * cd {REMOTE_DIR}/fund007751 && python3 led_scheduler.py off >> {LOG_DIR}/led.log 2>&1",
        f"0 7 * * * cd {REMOTE_DIR}/fund007751 && python3 led_scheduler.py on >> {LOG_DIR}/led.log 2>&1",
    ]
    existing = ""
    stdin, stdout, stderr = ssh.exec_command("crontab -l 2>/dev/null", timeout=10)
    existing = stdout.read().decode()

    for job in cron_jobs:
        if job not in existing:
            stdin, stdout, stderr = ssh.exec_command(
                f'(crontab -l 2>/dev/null; echo "{job}") | crontab -', timeout=10)
            stdout.channel.recv_exit_status()
            print(f"  ✅ 添加: {job.split('cd ')[0].strip()} {job.split('>>')[0].split()[-1]}")
        else:
            print(f"  → 已存在: {job[:40]}...")

    # 首次运行
    print("\n🚀 首次运行爬虫...")
    run_ssh(ssh, f"cd {REMOTE_DIR}/fund007751 && python3 fund_crawler.py", "fund_crawler.py", timeout=60)

    # 验证
    print("\n[验证] 检查部署结果...")
    run_ssh(ssh, f"ls -la {REMOTE_DIR}/fund007751/", "项目文件")
    run_ssh(ssh, f"ls -la {LOG_DIR}/", "日志目录")
    run_ssh(ssh, "crontab -l", "定时任务")

    ssh.close()

    print()
    print("=" * 56)
    print("  🎉 部署完成！")
    print(f"  查看日志: tail -f {LOG_DIR}/crawler.log")
    print("=" * 56)


if __name__ == "__main__":
    main()
