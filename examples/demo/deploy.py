# encoding: utf-8

"""
代码自动部署工具 - AioTest 负载测试项目

用途：
    将本地代码自动同步到远程 Linux 服务器，并设置正确的文件权限
    
功能：
    1. 通过 SSH/SFTP 将代码上传到远程主机
    2. 自动排除不必要的文件和目录（.git, __pycache__, *.pyc 等）
    3. 自动修改远程目录的文件权限为 UID 1000:1000（aiotest 用户）
    4. 支持多台服务器批量部署
    5. 详细的日志记录

使用场景：
    - 开发完成后快速部署代码到测试服务器
    - 批量更新多台测试节点的代码
    - CI/CD 流程中的自动部署环节

运行方式:
    py -m deploy
    或
    py deploy.py

依赖:
    - paramiko: SSH/SFTP 客户端库
    - aiotest.logger: 日志模块

配置说明:
    - HOSTS: 远程服务器 IP 列表
    - CODE_DIR: 本地代码目录（默认为当前目录）
    - REMOTE_DIR_NAME: 远程目标目录名称
    - EXCLUDE_PATTERNS: 要排除的文件/目录模式
    - USERNAME/PASSWORD: SSH 登录凭证

注意事项:
    - 确保远程服务器已安装 Docker 和 Docker Compose
    - 确保 SSH 服务已开启且密码正确
    - 首次连接需要确认主机密钥
    - 修改权限需要 sudo 权限
"""

import os
import paramiko
import fnmatch
from aiotest import logger


# Linux主机列表
HOSTS = [
    "122.16.40.21",
    "122.16.40.22",
    "122.16.40.23",
    "122.16.40.24",
    "122.16.40.25"
]

# 代码目录（当前目录）
CODE_DIR = "./"
REMOTE_DIR_NAME = "aiotest_demo"

# 要排除的文件/目录
EXCLUDE_PATTERNS = [
    ".git", 
    "__pycache__", 
    "*.pyc", 
    ".venv", 
    "tools", 
    "logs"
]

# 用户名和密码
USERNAME = "root"
PASSWORD = "ligeit"  # 如果使用密钥认证，可以保持为None


def deploy_code():

    code_dir = CODE_DIR
    hosts = HOSTS
    username = USERNAME
    password = PASSWORD
    exclude_patterns = EXCLUDE_PATTERNS
    
    # 遍历主机列表
    for host in hosts:
        logger.info(f"正在分发代码到 {host}...")
        try:
            # 创建SSH客户端,设置主机密钥策略为自动添加
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接主机
            client.connect(host, username=username, password=password)
            
            # 创建SFTP客户端, 用于上传文件
            sftp = client.open_sftp()
            
            # 获取用户主目录
            stdin, stdout, stderr = client.exec_command('echo $HOME')
            home_dir = stdout.read().decode().strip()
            remote_base_dir = f"{home_dir}/{REMOTE_DIR_NAME}"
            logger.info(f"使用远程主目录: {home_dir}")
            
            # 创建目标目录
            try:
                sftp.mkdir(remote_base_dir, mode=0o755)
            except IOError:
                # 目录已存在，忽略错误
                pass
            
            # 遍历本地目录并上传文件
            for root, dirs, files in os.walk(code_dir):
                # 排除指定目录
                dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in exclude_patterns)]
                
                # 创建远程目录
                rel_path = os.path.relpath(root, code_dir)
                # 将Windows风格的反斜杠转换为Linux风格的正斜杠
                rel_path = rel_path.replace('\\', '/')
                if rel_path != ".":
                    remote_dir = f"{remote_base_dir}/{rel_path}"
                    try:
                        sftp.mkdir(remote_dir, mode=0o755)
                    except IOError:
                        # 目录已存在，忽略错误
                        pass
                
                # 上传文件
                for file in files:
                    # 排除指定文件
                    if any(fnmatch.fnmatch(file, pattern) for pattern in exclude_patterns):
                        continue
                    
                    local_path = os.path.join(root, file)
                    if rel_path != ".":
                        remote_path = f"{remote_base_dir}/{rel_path}/{file}"
                    else:
                        remote_path = f"{remote_base_dir}/{file}"
                    sftp.put(local_path, remote_path)
                    logger.debug(f"上传文件: {local_path} -> {remote_path}")
            
            # 关闭连接
            sftp.close()
            
            logger.info(f"代码分发到 {host} 成功，正在修改权限...")
            
            #! 修改权限, 将用户1000:1000 设置为所有者和组所有者,否则无法启动aiotest容器
            execute_remote_command(client, f"sudo chown -R 1000:1000 ~/aiotest_demo")
            
            logger.info(f"✅ {host} 代码分发和权限设置完成")
            
        except Exception as e:
            logger.error(f"代码分发到 {host} 失败：{str(e)}")
        finally:
            if client:
                client.close()


def execute_remote_command(client, command):
    """在远程主机执行命令"""
    try:
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if exit_status == 0:
            logger.info(f"命令执行成功：{command}")
            if output:
                logger.debug(f"输出：{output}")
            return True
        else:
            logger.error(f"命令执行失败：{command}, 错误：{error}")
            return False
    except Exception as e:
        logger.error(f"执行命令异常：{command}, 错误：{str(e)}")
        return False


if __name__ == "__main__":
    deploy_code()