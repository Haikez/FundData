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
LOCAL_PACKAGE = "fund007751_*.tar.gz"
REMOTE_DIR = "/opt"


def run_ssh(ssh, command, label=""):
    """执行SSH命令并打印输出"""
    if label:
        print(f"\n  → {label}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n'):
            print(f"    {line}")
    if err and exit_code != 0:
        for line in err.split('\n'):
            print(f"    ⚠️ {line}")
    return exit_code


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
    print("\n[2/4] 上传部署包...")
    sftp = ssh.open_sftp()
    try:
        sftp.stat(REMOTE_DIR)
    except FileNotFoundError:
        run_ssh(ssh, f"mkdir -p {REMOTE_DIR}", "创建远程目录")

    remote_path = f"{REMOTE_DIR}/{LOCAL_PACKAGE}"
    sftp.put(LOCAL_PACKAGE, remote_path)
    sftp.close()
    print(f"  ✅ 上传完成: {remote_path}")

    # 解压
    print("\n[3/4] 解压部署包...")
    run_ssh(ssh, f"cd {REMOTE_DIR} && tar xzf {LOCAL_PACKAGE} && chmod +x fund007751/setup.sh",
            "解压并设置权限")
    print("  ✅ 解压完成")

    # 执行 setup.sh
    print("\n[4/4] 执行一键部署脚本...")
    print("  " + "-" * 40)

    # 创建一个交互式shell来执行setup.sh
    channel = ssh.invoke_shell()
    time.sleep(1)

    # 清空buffer
    if channel.recv_ready():
        channel.recv(65535)

    # 执行 setup.sh
    channel.send(f"cd {REMOTE_DIR}/fund007751 && bash setup.sh\n")
    time.sleep(2)

    # 读取输出
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='replace')
        time.sleep(0.3)

    for line in output.split('\n'):
        line = line.strip()
        if line:
            print(f"    {line}")

    channel.close()

    print("  " + "-" * 40)
    print("  ✅ 部署脚本执行完成")

    # 验证
    print("\n[验证] 检查部署结果...")
    run_ssh(ssh, f"ls -la {REMOTE_DIR}/fund007751/", "项目文件列表")
    run_ssh(ssh, f"crontab -l | grep fund_crawler", "定时任务检查")

    # 清理
    run_ssh(ssh, f"rm -f {REMOTE_DIR}/{LOCAL_PACKAGE}", "清理远程安装包")

    ssh.close()

    # LED状态提示
    print()
    print("=" * 56)
    print("  🎉 部署完成！当前估值: 📗 低估 → 绿灯常亮")
    print()
    print("  📗 PE < 7.5  = 🟢 绿灯 (低估)")
    print("  📙 PE 7.5~11.5 = 🔵 蓝灯 (合理)")
    print("  📕 PE > 11.5  = 🔴 红灯 (高估)")
    print()
    print("  手动执行: cd /opt/fund007751 && python3 fund_crawler.py")
    print("  查看日志: tail -f /var/log/fund007751/crawler.log")
    print("=" * 56)


if __name__ == "__main__":
    main()
