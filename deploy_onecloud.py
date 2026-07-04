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
PROJECT_DIR = f"{REMOTE_DIR}/fund007751"

INSTALLER_SCRIPT = r"""import zipfile, glob, os, sys
paths = ["/usr/local/lib/python3.11/dist-packages", "/usr/lib/python3/dist-packages"]
site_pkg = next((p for p in paths if os.path.isdir(p)), None)
if not site_pkg:
    import site as _site
    site_pkg = _site.getsitepackages()[0]
wheels = sorted(glob.glob("/opt/fund007751/pip_packages/*.whl"))
if not wheels:
    import subprocess
    result = subprocess.run(["ls", "-la", "/opt/fund007751/pip_packages/"],
                          capture_output=True, text=True)
    print("  pip_packages/ 内容:", result.stdout or result.stderr)
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


def die(msg):
    print(f"  ❌ {msg}")
    sys.exit(1)


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
    """上传离线包，返回上传数量"""
    local_dir = os.path.join(os.path.dirname(__file__), "pip_packages")
    remote_dir = f"{PROJECT_DIR}/pip_packages"

    if not os.path.isdir(local_dir):
        print("  ⚠️  本地 pip_packages/ 不存在")
        return 0

    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    count = 0
    for whl in sorted(os.listdir(local_dir)):
        if whl.endswith(".whl"):
            local = os.path.join(local_dir, whl)
            remote = f"{remote_dir}/{whl}"  # 用 / 拼接，避免 Windows 反斜杠问题
            size = os.path.getsize(local)
            sftp.put(local, remote)
            print(f"  ✓ pip_packages/{whl} ({size // 1024}KB)")
            count += 1
    return count


def verify_remote_whl_count(ssh):
    """验证远程 .whl 文件数量，失败则中止"""
    code, out, err = run_ssh(ssh,
        'ls /opt/fund007751/pip_packages/*.whl 2>&1 | grep -c ".whl"',
        "验证 wheel 包数量")
    try:
        n = int(out.strip())
        if n == 0:
            run_ssh(ssh, "ls -la /opt/fund007751/pip_packages/", "pip_packages 目录内容")
            die("远程 pip_packages/ 中没有 .whl 文件")
        print(f"    → {n} 个 wheel 包")
    except (ValueError, TypeError):
        die(f"无法解析 wheel 数量: {out}")


def offline_install(ssh):
    """远程离线安装，失败则中止"""
    sftp = ssh.open_sftp()
    with sftp.open(f"{PROJECT_DIR}/install_deps.py", "w") as f:
        f.write(INSTALLER_SCRIPT)
    sftp.close()

    code, out, err = run_ssh(ssh, f"python3 {PROJECT_DIR}/install_deps.py", "离线安装依赖")
    run_ssh(ssh, f"rm -f {PROJECT_DIR}/install_deps.py", "清理")
    if code != 0:
        die("依赖安装失败")


def main():
    print("=" * 56)
    print("  🚀 OneCloud 自动部署 - 基金007751 LED看板")
    print(f"  目标: {USER}@{HOST}:{PORT}")
    print("=" * 56)

    # ─── 1. 连接 ───
    print("\n[1/4] 连接 SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=10)
        print("  ✅ SSH 连接成功")
    except Exception as e:
        die(f"SSH 连接失败: {e}")

    # ─── 2. 上传 + 验证 ───
    print("\n[2/4] 上传文件...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(PROJECT_DIR)
    except FileNotFoundError:
        sftp.mkdir(PROJECT_DIR)

    core_files = ["fund_crawler.py", "led_scheduler.py", "setup.sh", "led控制伪代码.txt"]
    for f in core_files:
        local = os.path.join(os.path.dirname(__file__), f)
        if os.path.exists(local):
            remote = f"{PROJECT_DIR}/{f}"  # 用 / 拼接
            sftp.put(local, remote)
            print(f"  ✓ {f}")

    whl_count = upload_pip_wheels(sftp)
    sftp.close()

    if whl_count == 0:
        die("本地 pip_packages/ 为空，请先执行: pip download requests -d pip_packages --only-binary=:all: --platform=any")

    # 远程验证
    print("  → 验证远程文件...")
    verify_remote_whl_count(ssh)
    print("  ✅ 文件完整性验证通过")

    # ─── 3. 离线安装 ───
    print("\n[3/4] 离线安装依赖...")
    offline_install(ssh)
    run_ssh(ssh, f"mkdir -p {LOG_DIR}", "创建日志目录")

    # ─── 4. 定时任务 + 首次运行 ───
    print("\n[4/4] 设置定时任务 + 首次运行...")
    cron_jobs = [
        f"30 15 * * 1-5 cd {PROJECT_DIR} && python3 fund_crawler.py >> {LOG_DIR}/crawler.log 2>&1",
        f"0 22 * * * cd {PROJECT_DIR} && python3 led_scheduler.py off >> {LOG_DIR}/led.log 2>&1",
        f"0 7 * * * cd {PROJECT_DIR} && python3 led_scheduler.py on >> {LOG_DIR}/led.log 2>&1",
    ]
    stdin, stdout, stderr = ssh.exec_command("crontab -l 2>/dev/null", timeout=10)
    existing = stdout.read().decode()
    for job in cron_jobs:
        if job not in existing:
            stdin, stdout, stderr = ssh.exec_command(
                f'(crontab -l 2>/dev/null; echo "{job}") | crontab -', timeout=10)
            stdout.channel.recv_exit_status()

    print("  ✅ 定时任务:")
    for j in cron_jobs:
        parts = j.split()
        print(f"    {parts[0]} {parts[1]} → {parts[-1].split('/')[-1]}")

    run_ssh(ssh, f"cd {PROJECT_DIR} && python3 fund_crawler.py >> {LOG_DIR}/crawler.log 2>&1", "首次运行", timeout=60)

    # 清理安装文件
    print("\n🧹 清理安装文件...")
    cleanup = [
        f"rm -f {PROJECT_DIR}/setup.sh",
        f"rm -f {PROJECT_DIR}/led控制伪代码.txt",
        f"rm -rf {PROJECT_DIR}/pip_packages",
        f"rm -f {PROJECT_DIR}/install_deps.py",
        f"rm -f {PROJECT_DIR}/deploy_onecloud.py",
    ]
    for cmd in cleanup:
        run_ssh(ssh, cmd, timeout=10)
    print("  ✅ 安装文件已清理，仅保留运行必需文件")

    print("\n📂 保留的文件:")
    run_ssh(ssh, f"ls -lh {PROJECT_DIR}/", timeout=10)

    ssh.close()
    print()
    print("=" * 56)
    print("  🎉 部署完成！")
    print(f"  查看日志: tail -f {LOG_DIR}/crawler.log")
    print("=" * 56)


if __name__ == "__main__":
    main()
