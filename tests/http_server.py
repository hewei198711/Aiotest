# encoding: utf-8

import asyncio
import json

from aiohttp import web


async def handle_json(request):
    """处理 JSON 请求"""
    return web.Response(
        text=json.dumps({"message": "Hello, HTTP!"}),
        content_type="application/json"
    )


async def handle_text(request):
    """处理纯文本请求（非 JSON）"""
    return web.Response(
        text="This is plain text response",
        content_type="text/plain"
    )


async def handle_invalid_json(request):
    """处理无效 JSON 请求"""
    return web.Response(
        text="This is { invalid json",
        content_type="application/json"
    )


async def handle_custom_headers(request):
    """处理自定义请求头"""
    response = web.Response(
        text=json.dumps({"message": "Hello with custom headers!"}),
        content_type="application/json"
    )
    response.headers["X-Custom-Header"] = "custom-value"
    response.headers["X-Another-Header"] = "another-value"
    return response


async def handle_with_cookies(request):
    """处理带 cookies 的请求"""
    response = web.Response(
        text=json.dumps({"message": "Hello with cookies!"}),
        content_type="application/json"
    )
    response.set_cookie("session_id", "abc123", httponly=True)
    response.set_cookie("user_id", "456", httponly=True)
    return response


async def handle_error(request):
    """处理错误请求，模拟响应读取异常"""
    # 返回 500 错误，模拟服务器内部错误
    return web.Response(
        status=500,
        text="Internal Server Error",
        content_type="text/plain"
    )


async def handle_not_found(request):
    """处理 404 错误"""
    return web.Response(
        status=404,
        text="Not Found",
        content_type="text/plain"
    )


retry_counter = {}


async def handle_retry(request):
    """处理重试请求，模拟请求失败后成功"""
    client_addr = request.remote
    if client_addr not in retry_counter:
        retry_counter[client_addr] = 0

    retry_count = retry_counter[client_addr]
    retry_counter[client_addr] += 1

    if retry_count < 2:
        # 第一次和第二次请求返回 500 错误，并关闭连接触发异常
        request.transport.close()
        return None
    else:
        # 第三次及以后请求成功
        retry_counter[client_addr] = 0  # 重置计数器
        return web.Response(
            text='{"message": "Success after retry"}', content_type='application/json')


async def handle_reset_connection(request):
    """处理连接重置请求，模拟连接被重置的情况"""
    # 直接关闭连接，模拟连接被重置
    request.transport.close()
    return None


async def start_http_server():
    """启动 HTTP 服务器"""
    app = web.Application()

    # 添加路由
    app.router.add_route('*', '/', handle_json)
    app.router.add_get('/text', handle_text)
    app.router.add_get('/invalid-json', handle_invalid_json)
    app.router.add_get('/custom-headers', handle_custom_headers)
    app.router.add_get('/cookies', handle_with_cookies)
    app.router.add_get('/error', handle_error)
    app.router.add_get('/retry', handle_retry)
    app.router.add_get('/reset-connection', handle_reset_connection)
    app.router.add_route('*', '/{tail:.*}', handle_not_found)

    # 启动服务器
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("HTTP server started at http://localhost:8080")

    # 保持服务器运行
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(start_http_server())
