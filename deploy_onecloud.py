"""
OneCloud 自动部署脚本
上传文件 + 离线安装依赖 + 设置定时任务
"""
import paramiko
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "192.168.1.104"
PORT = 22
USER = "root"
PASSWORD = "xxxx"
REMOTE_DIR = "/opt"
LOG_DIR = "/var/log/fund007751"

# 依赖安装 Python 脚本 (在远程执行)
INSTALLER_SCRIPT = r"""import zipfile, glob, os, sys
paths = ["/usr/local/lib/python3.11/dist-packages", "/usr/lib/python3/dist-packages"]
site_pkg = next((p for p in paths if os.path.isdir(p)), None)
if not site_pkg:
    import site as _site
    site_pkg = _site.getsitepackages()[0]
wheels = sorted(glob.glob("/opt/fund007751/pip_packages/*.whl"))
if not wheels:
    print("  ❌ 无离线包可用")
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
"""


def run_ssh(ssh, command, label="", timeout=60):
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
    local_dir = os.path.join(os.path.dirname(__file__), "pip_packages")
    remote_dir = os.path.join(REMOTE_DIR, "fund007751", "pip_packages")
    if not os.path.isdir(local_dir):
        print("  ⚠️  本地 pip_packages/ 不存在")
        return

    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    for whl in sorted(os.listdir(local_dir)):
        if whl.endswith(".whl"):
            sftp.put(os.path.join(local_dir, whl), os.path.join(remote_dir, whl))
            print(f"  ✓ {whl}")


def offline_install(ssh):
    """远程离线安装"""
    sftp = ssh.open_sftp()
    with sftp.open("/opt/fund007751/install_deps.py", "w") as f:
        f.write(INSTALLER_SCRIPT)
    sftp.close()
    run_ssh(ssh, "python3 /opt/fund007751/install_deps.py", "离线安装依赖")
    run_ssh(ssh, "rm -f /opt/fund007751/install_deps.py", "清理")


def main():
    print("=" * 56)
    print("  🚀 OneCloud 自动部署 - 基金007751 LED看板")
    print(f"  目标: {USER}@{HOST}:{PORT}")
    print("=" * 56)

    print("\n[1/4] 连接 SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=10)
        print("  ✅ SSH 连接成功")
    except Exception as e:
        print(f"  ❌ SSH 连接失败: {e}")
        sys.exit(1)

    print("\n[2/4] 上传文件...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(f"{REMOTE_DIR}/fund007751")
    except FileNotFoundError:
        sftp.mkdir(f"{REMOTE_DIR}/fund007751")

    for f in ["fund_crawler.py", "led_scheduler.py", "setup.sh", "led控制伪代码.txt"]:
        local = os.path.join(os.path.dirname(__file__), f)
        if os.path.exists(local):
            sftp.put(local, f"{REMOTE_DIR}/fund007751/{f}")
            print(f"  ✓ {f}")

    upload_pip_wheels(sftp)
    sftp.close()

    print("\n[3/4] 离线安装依赖...")
    offline_install(ssh)
    run_ssh(ssh, f"mkdir -p {LOG_DIR}", "创建日志目录")

    print("\n[4/4] 设置定时任务 + 首次运行...")
    cron_jobs = [
        f"30 15 * * 1-5 cd {REMOTE_DIR}/fund007751 && python3 fund_crawler.py >> {LOG_DIR}/crawler.log 2>&1",
        f"0 22 * * * cd {REMOTE_DIR}/fund007751 && python3 led_scheduler.py off >> {LOG_DIR}/led.log 2>&1",
        f"0 7 * * * cd {REMOTE_DIR}/fund007751 && python3 led_scheduler.py on >> {LOG_DIR}/led.log 2>&1",
    ]
    stdin, stdout, stderr = ssh.exec_command("crontab -l 2>/dev/null", timeout=10)
    existing = stdout.read().decode()
    for job in cron_jobs:
        if job not in existing:
            stdin, stdout, stderr = ssh.exec_command(
                f'(crontab -l 2>/dev/null; echo "{job}") | crontab -', timeout=10)
            stdout.channel.recv_exit_status()
        print(f"  ✅ {job.split(chr(62)+chr(62))[0].strip()}")

    run_ssh(ssh, f"cd {REMOTE_DIR}/fund007751 && python3 fund_crawler.py", "首次运行", timeout=60)
    run_ssh(ssh, f"ls -la {LOG_DIR}/", "日志文件")

    ssh.close()
    print()
    print("=" * 56)
    print("  🎉 部署完成！")
    print(f"  查看日志: tail -f {LOG_DIR}/crawler.log")
    print("=" * 56)


if __name__ == "__main__":
    main()
