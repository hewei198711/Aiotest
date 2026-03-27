# encoding: utf-8

import asyncio
import ssl

from aiohttp import web


async def handle(request):
    """处理 HTTP 请求"""
    return web.Response(
        text='{"message": "Hello, HTTPS!"}',
        content_type='application/json'
    )


async def start_https_server():
    """启动 HTTPS 服务器"""
    # 创建 SSL 上下文
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    # 生成自签名证书（仅用于测试）
    import os
    import tempfile

    from OpenSSL import crypto

    # 创建密钥
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # 创建证书
    cert = crypto.X509()
    cert.get_subject().C = "CN"
    cert.get_subject().ST = "Beijing"
    cert.get_subject().L = "Beijing"
    cert.get_subject().O = "Test"
    cert.get_subject().OU = "Test"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)  # 1 year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha256")

    # 保存证书和密钥到临时文件
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pem', delete=False) as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        cert_file = f.name

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.key', delete=False) as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
        key_file = f.name

    try:
        # 加载证书和密钥
        ssl_context.load_cert_chain(cert_file, key_file)

        # 创建应用
        app = web.Application()
        app.add_routes([web.route('*', '/', handle),
                       web.route('*', '/{tail:.*}', handle)])

        # 启动服务器
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8443, ssl_context=ssl_context)
        await site.start()
        print("HTTPS server started at https://localhost:8443")

        # 保持服务器运行
        while True:
            await asyncio.sleep(3600)
    finally:
        # 清理临时文件
        if os.path.exists(cert_file):
            os.unlink(cert_file)
        if os.path.exists(key_file):
            os.unlink(key_file)


if __name__ == "__main__":
    asyncio.run(start_https_server())
