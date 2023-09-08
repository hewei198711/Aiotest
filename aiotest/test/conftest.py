# encoding: utf-8

import asyncio
import base64
import random
import time
from io import BytesIO

import pytest
import allure
from asgiref.wsgi import WsgiToAsgi
from hypercorn.config import Config
from hypercorn.asyncio import serve
from flask import Flask, request, redirect, make_response, send_file, Response, stream_with_context
from aiotest import events
from aiotest.stats_exporter import on_request, on_error, on_worker_report
from aiotest.test.log import logger

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)


@app.route("/")
async def get():
    await asyncio.sleep(0.1)
    return "asyncio sleep"

@app.route("/fast")
async def ultra_fast():
    return "This is an ultra fast response"

@app.route("/slow")
async def slow():
    delay = request.args.get("delay")
    if delay:
        await asyncio.sleep(float(delay))
    else:
        await asyncio.sleep(random.choice([0.5, 1, 1.5]))
    return "This is a slow response"

@app.route("/key")
async def keys():
    dic = {"key01": 1, "key02": 2}
    return dic

@app.route("/consistent")
async def consistent():
    await asyncio.sleep(0.2)
    return "This is a consistent response"

@app.route("/request_method", methods=["POST", "GET", "HEAD", "PUT", "DELETE", "PATCH"])
async def request_method():
    return request.method

@app.route("/request_header_test")
async def request_header_test():
    return request.headers["X-Header-Test"]

@app.route("/post", methods=["POST"])
@app.route("/put", methods=["PUT"])
async def manipulate():
    return str(request.form.get("arg", ""))

@app.route("/fail")
async def failed_request():
    return "This response failed", 500

@app.route("/status/204")
async def status_204():
    return "", 204

@app.route("/redirect", methods=["GET", "POST"])
async def do_redirect():
    delay = request.args.get("delay")
    if delay:
        await asyncio.sleep(float(delay))
    url = request.args.get("url", "/fast")
    return redirect(url)

@app.route("/basic_auth")
async def basic_auth():
    auth = base64.b64decode(request.headers.get("Authorization", "").replace("Basic ", "")).decode('utf-8')
    if auth == "aiotest:menace":
        return "Authorized"
    resp = make_response("401 Authorization Required", 401)
    resp.headers["WWW-Authenticate"] = 'Basic realm="aiotest"'
    return resp

@app.route("/no_content_length")
async def no_content_length():
    r = send_file(BytesIO("This response does not have content-length in the header".encode('utf-8')),
                  etag=False,
                  mimetype='text/plain')
    r.headers.remove("Content-Length")
    return r

@app.errorhandler(404)
async def not_found(error):
    return "Not Found", 404

@app.route("/streaming/<int:iterations>")
def streaming_response(iterations):
    def generate():
        yield "<html><body><h1>streaming response</h1>"
        for i in range(iterations):
            yield f"<span>{i}</span>\n"
            time.sleep(0.01)
        yield "</body></html>"
    return Response(stream_with_context(generate()), mimetype="text/html")

@app.route("/set_cookie", methods=["POST"])
async def set_cookie():
    response = make_response("ok")
    response.set_cookie(request.args.get("name"), request.args.get("value"))
    return response

@app.route("/get_cookie")
async def get_cookie():
    return make_response(request.cookies.get(request.args.get("name"), ""))

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@allure.title("启动/关闭flask服务")
@pytest.fixture(scope="session", autouse=True)
async def web_server_up():
    config = Config()
    config.bind = ["localhost:8080"]
    flask_task = asyncio.create_task(serve(asgi_app, config), name="flask_task")
    events.stats_request -= on_request
    events.user_error -= on_error
    events.worker_report -= on_worker_report
    yield
    flask_task.cancel()
    await asyncio.sleep(0.2)

        




