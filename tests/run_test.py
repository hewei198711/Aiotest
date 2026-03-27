# coding:utf-8

import os
import subprocess
import sys
import time
import urllib.request

import pytest


def wait_for_server(url, timeout=30, interval=0.5):
    """等待服务器启动并可用"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(interval)
    return False


def start_http_server():
    """启动 HTTP 服务器"""
    http_process = subprocess.Popen(
        [sys.executable, "tests/http_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    # 等待服务器启动
    if not wait_for_server("http://localhost:8080/"):
        raise RuntimeError("HTTP 服务器启动失败")
    return http_process


def start_https_server():
    """启动 HTTPS 服务器"""
    https_process = subprocess.Popen(
        [sys.executable, "tests/https_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    # 等待服务器启动（HTTPS 需要忽略 SSL 验证）
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    start_time = time.time()
    while time.time() - start_time < 30:
        try:
            urllib.request.urlopen(
                "https://localhost:8443/", timeout=1, context=ctx)
            return https_process
        except Exception:
            time.sleep(0.5)

    raise RuntimeError("HTTPS 服务器启动失败")


def stop_server(process, server_name):
    """停止服务器"""
    if process:
        print(f"正在关闭 {server_name}...")
        process.terminate()
        try:
            process.wait(timeout=5)
            print(f"{server_name} 已关闭")
        except subprocess.TimeoutExpired:
            print(f"{server_name} 强制关闭")
            process.kill()


if __name__ == "__main__":
    http_process = None
    https_process = None

    try:
        # 启动 HTTP 服务器
        print("正在启动 HTTP 服务器...")
        http_process = start_http_server()
        print("HTTP 服务器已启动")

        # 启动 HTTPS 服务器
        print("正在启动 HTTPS 服务器...")
        https_process = start_https_server()
        print("HTTPS 服务器已启动")

        # 执行测试用例
        print("\n开始执行测试用例...\n")
        exit_code = pytest.main([
            "--clean-alluredir",
            "tests",  # 指定测试目录
        ])

        print(f"\n测试执行完成，退出码: {exit_code}")
        print("\n测试覆盖率报告：")
        print("- 终端输出：已在上面显示")
        print("- HTML 报告：coverage_report/index.html")

    except Exception as e:
        print(f"发生错误: {e}")
        exit_code = 1
    finally:
        # 关闭服务器
        stop_server(http_process, "HTTP 服务器")
        stop_server(https_process, "HTTPS 服务器")

    sys.exit(exit_code)
