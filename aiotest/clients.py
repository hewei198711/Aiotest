# encoding: utf-8
"""
HTTP客户端模块，提供异步HTTP请求功能

封装了基于aiohttp的异步HTTP请求功能，支持连接池管理、自动重试、请求/响应拦截器等特性。
"""

import asyncio
import json
import re
import time
import traceback
import uuid
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
import backoff

from aiotest.events import request_metrics
from aiotest.logger import logger
from aiotest.metrics import RequestMetrics

# 连接池配置
CONNECTOR_SETTINGS = {
    'limit': 1000,  # 默认最大连接数（支持高并发场景）
    'limit_per_host': 100,  # 默认每个主机最大连接数（适合单主机压测）
    'force_close': False,  # 默认是否强制关闭空闲连接
    'enable_cleanup_closed': True,  # 默认是否清理已关闭的连接
}


def configure_connector(limit=None, limit_per_host=None,
                        force_close=None, enable_cleanup_closed=None):
    """动态配置连接池参数"""
    for key, value in {
        'limit': limit,
        'limit_per_host': limit_per_host,
        'force_close': force_close,
        'enable_cleanup_closed': enable_cleanup_closed
    }.items():
        if value is not None:
            CONNECTOR_SETTINGS[key] = value

    logger.info("当前连接池配置: %s", CONNECTOR_SETTINGS)


class HTTPClient:
    """
    异步HTTP客户端类，封装了基于aiohttp的异步HTTP请求功能。

    功能：
    - 提供异步HTTP请求功能（GET/POST/PUT/DELETE等）。
    - 支持连接池管理，优化高并发场景下的性能。
    - 自动重试机制，处理网络波动或临时故障。
    - 请求/响应拦截器，支持自定义逻辑扩展。
    - 敏感信息过滤，避免日志泄露敏感数据。
    - 统一的错误处理，简化异常管理。

    示例：
        >>> async with HTTPClient(base_url="https://api.example.com") as client:
        ...     response = await client.get("/users")
        ...     print(await response.json())

    参数：
        base_url (str): 基础URL，所有请求将基于此URL构建。默认为空字符串。
        default_headers (Optional[Dict[str, str]]): 默认请求头。如果未提供，将使用内置默认值。
        timeout (int): 请求超时时间（秒）。默认为30秒。
        max_retries (int): 最大重试次数。默认为3次。
        verify_ssl (bool): 是否验证SSL证书。默认为True。

    异常：
        ValueError: 如果参数值无效（如超时时间为负数）。
    """

    def __init__(
        self,
        base_url: str = "",
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ):
        """
        初始化HTTP客户端。

        参数：
            base_url (str): 基础URL，所有请求将基于此URL构建。默认为空字符串。
            default_headers (Optional[Dict[str, str]]): 默认请求头。如果未提供，将使用内置默认值。
            timeout (int): 请求超时时间（秒）。默认为30秒。
            max_retries (int): 最大重试次数。默认为3次。
            verify_ssl (bool): 是否验证SSL证书。默认为True。

        异常：
            ValueError: 如果参数值无效（如超时时间为负数）。
        """

        self.base_url = base_url
        self.default_headers = default_headers or {}
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self._session = None
        self._connector = None
        # 预编译敏感字段正则
        self._sensitive_field_pattern = re.compile(
            r'(password|secret|token|credit_card|cvv|api[_-]key|auth)', re.IGNORECASE
        )
        self._sensitive_str_pattern = re.compile(
            r'(password|token|api[_-]key|auth)=[^&]+', re.IGNORECASE
        )

        # 设置默认请求头
        self.default_headers.update({
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    async def __aenter__(self):
        """
        异步上下文管理器入口，用于初始化HTTP会话和连接池。

        功能：
        - 初始化TCP连接池。
        - 创建ClientSession实例。

        返回：
            HTTPClient: 当前实例，支持链式调用。

        异常：
            ClientError: 如果会话初始化失败。
        """
        self._connector = aiohttp.TCPConnector(
            limit=CONNECTOR_SETTINGS['limit'],
            limit_per_host=CONNECTOR_SETTINGS['limit_per_host'],
            force_close=CONNECTOR_SETTINGS['force_close'],
            enable_cleanup_closed=CONNECTOR_SETTINGS['enable_cleanup_closed'],
            verify_ssl=self.verify_ssl
        )
        self._session = aiohttp.ClientSession(
            base_url=self.base_url,
            headers=self.default_headers,
            timeout=self.timeout,
            connector=self._connector,
            json_serialize=json.dumps  # 使用标准json序列化
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """关闭HTTP会话和连接池，清理资源"""
        close_timeout = 5.0  # 秒

        if self._session:
            try:
                await asyncio.wait_for(self._session.close(), timeout=close_timeout)
            except asyncio.TimeoutError:
                logger.warning("会话关闭超时")

    async def close(self):
        """手动关闭HTTP客户端并清理资源"""
        await self.__aexit__(None, None, None)

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        带重试的实际请求执行方法。

        参数：
            method (str): HTTP方法（如GET、POST等）。
            endpoint (str): API端点路径。
            **kwargs (Any): 其他请求参数（如headers、json等）。

        返回：
            aiohttp.ClientResponse: 响应对象。
        """

        # 当max_retries=0时完全跳过重试逻辑
        if self.max_retries == 0:
            return await self._session.request(method, endpoint, **kwargs)

        @backoff.on_exception(
            backoff.expo,
            (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError),
            max_tries=self.max_retries,
            logger=logger,
            giveup=lambda e: isinstance(
                e, aiohttp.ClientResponseError) and e.status in [
                400, 401, 403, 404]
        )
        async def _do_request():
            """执行实际请求"""
            return await self._session.request(method, endpoint, **kwargs)

        return await _do_request()

    def request(
        self,
        method: str,
        endpoint: str,
        name: Optional[str] = None,
        **kwargs
    ) -> "ResponseContextManager":
        """
        发送HTTP请求

        参数：
            method: HTTP方法 (GET, POST, PUT, DELETE等)
            endpoint: API端点 (不包含基础URL)
            name: 请求名称
            **kwargs: 其他aiohttp请求参数

        返回：
            ResponseContextManager: 响应上下文管理器对象
        """

        # 使用高精度时间戳 + 随机数确保唯一性
        request_id = f"req-{int(time.monotonic() * 1000000)}-{uuid.uuid4().hex[:8]}"
        # 保留原始 endpoint 用于实际请求
        request_endpoint = endpoint
        # 处理日志和标准化
        log_endpoint = endpoint.lstrip('/')
        if not log_endpoint:
            log_endpoint = "unknown"
        normalized_endpoint = self._normalize_endpoint(log_endpoint)

        # 准备请求参数
        kwargs.setdefault('headers', {}).update(self.default_headers)
        kwargs['ssl'] = self.verify_ssl

        # 结构化日志
        log = RequestMetrics(
            request_id=request_id,
            method=method,
            endpoint=name if name else normalized_endpoint,
            extra={
                "headers": self._sanitize_headers(kwargs.get('headers', {})),
                "params": kwargs.get('params', {}),
                "body": self._sanitize_body(kwargs.get('data', kwargs.get('json', None)))
            }
        )

        self._log_request(log, "start")

        start_time = time.monotonic()

        # 返回上下文管理器
        return ResponseContextManager(
            request_coroutine=self._request_with_retry(
                method, request_endpoint, **kwargs),
            log=log,
            start_time=start_time,
            metrics_callback=self._record_request_metrics,
            log_request=self._log_request
        )

    def get(self, endpoint: str,
            params: Optional[Dict[str, Any]] = None, **kwargs) -> "ResponseContextManager":
        """GET请求方法"""
        return self.request('GET', endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Union[Dict[str, Any], str]] = None,
             **kwargs) -> "ResponseContextManager":
        """POST请求方法"""
        return self.request('POST', endpoint, data=data, **kwargs)

    def put(self, endpoint: str, data: Optional[Union[Dict[str, Any], str]] = None,
            **kwargs) -> "ResponseContextManager":
        """PUT请求方法"""
        return self.request('PUT', endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> "ResponseContextManager":
        """DELETE请求方法"""
        return self.request('DELETE', endpoint, **kwargs)

    @lru_cache(maxsize=100)
    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        将动态路径转换为固定模式

        参数：
        - endpoint: 原始API端点

        返回：
        - str: 标准化后的端点（自动转换 /users/123 为 /users/{id}）
        """
        return re.sub(r'\/\d+(/|$)', r'/{id}\1', endpoint)

    async def _record_request_metrics(
        self,
        request_id: str,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        response_size: int,
        error: Optional[Dict[str, Any]] = None,
        assertion_result: str = "unknown"
    ):
        """
        记录接口请求性能数据

        职责：
        - 收集接口请求的原始性能数据
        - 通过 request_events 事件上传数据
        - 不关心数据存储和上报方式
        """
        try:
            # 直接使用 RequestMetrics 类实例，保持数据结构一致性
            request_metrics_data = RequestMetrics(
                request_id=request_id,
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
                response_size=response_size,
                error=error,
                assertion_result=assertion_result
            )

            # 通过事件系统上传请求数据
            await request_metrics.fire(metrics=request_metrics_data)

            logger.debug(
                "记录请求指标: %s %s - %s (%.3fs)",
                method, endpoint, status_code, duration
            )

        except Exception as e:
            logger.warning("记录请求指标失败: %s", e)

    def _log_request(self, log: RequestMetrics, status: str):
        """
        统一记录请求日志

        参数：
        - log: 请求指标对象
        - status: 请求状态（start/complete/failed）
        """
        log_data = {
            "method": log.method,
            "endpoint": log.endpoint,
            "status": status,
        }
        log_prefix = f"request_{status} {log.method} {log.endpoint}"

        if status == "start":
            self._log_request_start(log, log_data, log_prefix)
        elif status == "complete":
            self._log_request_complete(log, log_data, log_prefix)
        elif status == "failed":
            self._log_request_failed(log, log_data, log_prefix)

    def _log_request_start(self, log: RequestMetrics, log_data: Dict[str, Any], log_prefix: str):
        """记录请求开始日志"""
        log_data["request_start"] = log.extra if isinstance(
            log.extra, dict) else {}
        logger.debug(log_prefix, extra=log_data)

    def _log_request_complete(self, log: RequestMetrics, log_data: Dict[str, Any], log_prefix: str):
        """记录请求完成日志"""
        # 过滤掉headers，避免日志过大
        if log.extra and isinstance(log.extra, dict):
            filtered_extra = {k: v for k, v in log.extra.items() if k != 'headers'}
        else:
            filtered_extra = {}
        log_data["response_data"] = filtered_extra
        logger.debug(log_prefix, extra=log_data)

    def _log_request_failed(self, log: RequestMetrics, log_data: Dict[str, Any], log_prefix: str):
        """记录请求失败日志"""
        if hasattr(log, 'error') and log.error is not None:
            log_data["error"] = log.error
            # 如果有响应数据,也记录到日志中
            if log.error.get("response_data") is not None:
                response_data = log.error["response_data"]
                # 限制响应数据长度
                if isinstance(response_data, (dict, str)):
                    response_str = json.dumps(
                        response_data, ensure_ascii=False) if isinstance(
                        response_data, dict) else str(response_data)
                    if len(response_str) > 500:
                        response_str = response_str[:500] + "..."
                    log_data["response_data"] = response_str
                else:
                    log_data["response_data"] = str(response_data)[:500]
        logger.error(log_prefix, extra=log_data)

    @staticmethod
    def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """
        清理敏感信息的请求头

        参数：
        - headers: 原始请求头

        返回：
        - Dict[str, str]: 清理后的请求头
        """
        sensitive_keys = {'authorization', 'api-key', 'token', "cookie"}
        return {
            k: '*****' if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in headers.items()
        }

    def _sanitize_body(self, body: Any) -> Any:
        """
        清理敏感信息的请求体

        参数：
        - body: 原始请求体

        返回：
        - Any: 清理后的请求体
        """
        if isinstance(body, dict):
            return {
                k: '*****' if self._sensitive_field_pattern.search(k) else v
                for k, v in body.items()
            }
        if isinstance(body, str):
            return self._sensitive_str_pattern.sub(r'\1=*****', body)
        return body


class ResponseContextManager:
    """
    响应上下文管理器类

    功能：
    - 封装响应处理逻辑
    - 支持异步上下文管理
    - 提供统一的响应处理方法
    """

    def __init__(
        self,
        request_coroutine,
        log: RequestMetrics,
        start_time: float,
        metrics_callback: Callable,
        log_request: Callable,
    ):
        """
        初始化响应上下文管理器

        参数：
        - request_coroutine: 请求协程
        - log: 请求指标对象
        - start_time: 请求开始时间
        - metrics_callback: 指标回调函数
        - log_request: 请求日志回调函数
        """
        self._request_coroutine = request_coroutine
        self.log = log
        self.start_time = start_time
        self._metrics_callback = metrics_callback
        self._log_request = log_request
        self._response = None
        self._processed_data = None
        self._error_handled = False

    async def __aenter__(self) -> Dict[str, Any]:
        """进入上下文，返回处理后的响应数据"""
        try:
            self._response = await self._request_coroutine
            self._processed_data = await self._process_response(self._response)
            duration = time.monotonic() - self.start_time

            # 更新日志
            self.log.status_code = self._response.status
            self.log.duration = duration
            self.log.response_size = self._estimate_size(
                self._processed_data.get('data'))
            # 确保 extra 不为 None
            if self.log.extra is None:
                self.log.extra = {}
            self.log.extra["response_data"] = self._processed_data.get('data')
        except Exception as e:
            # 处理请求错误（如超时、连接错误等）
            self.log.assertion_result = "fail"
            await self._handle_error(e)
            # 重新抛出异常，让测试用例捕获
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器出口，用于清理资源。

        功能：关闭ClientSession和连接池，确保资源释放，避免内存泄漏。

        异常：asyncio.TimeoutError - 如果关闭操作超时。
        """
        if self._response:
            self._response.close()

        if exc_type:
            # 断言失败时，设置断言结果为fail
            self.log.assertion_result = "fail"
            await self._handle_error(exc_type, exc_val, exc_tb)
            return False  # 返回False，给users 顺序执行任务时，一个任务失败，后续任务不执行

        # 断言成功时，设置断言结果为pass
        self.log.assertion_result = "pass"
        # 记录成功指标
        logger.debug(
            "调用指标回调函数，方法: %s, 端点: %s",
            self.log.method, self.log.endpoint
        )
        await self._metrics_callback(
            request_id=self.log.request_id,
            method=self.log.method,
            endpoint=self.log.endpoint,
            status_code=self.log.status_code,
            duration=self.log.duration,
            response_size=self.log.response_size,
            assertion_result=self.log.assertion_result
        )
        # 记录成功日志
        self._log_request(self.log, "complete")
        return True

    @property
    def status(self) -> int:
        """提供 status 属性，保持和aiohttp一致的操作"""
        return self._processed_data['status']

    @property
    def headers(self) -> Dict[str, str]:
        """提供 headers 属性，保持和aiohttp一致的操作"""
        return self._processed_data['headers']

    async def text(self) -> str:
        """提供 text() 方法,保持和aiohttp一致的操作"""
        return self._processed_data['data']

    async def json(self) -> dict:
        """提供 json() 方法,保持和aiohttp一致的操作"""
        return self._processed_data['data']

    async def _process_response(
            self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """处理响应数据"""
        try:
            raw_bytes = await response.read()
            data = self._parse_response_data(raw_bytes)

            # 统一处理 headers 和 cookies 转换
            headers_dict = self._safe_get_headers(response)
            cookies_dict = self._safe_get_cookies(response)

            return {
                'status': response.status,
                'headers': headers_dict,
                'data': data,
                'cookies': cookies_dict,
            }
        except Exception as e:
            logger.error("处理响应数据失败: %s", e)
            # 简化异常处理，使用空字典作为默认值
            return {
                'status': getattr(response, 'status', 500),
                'headers': self._safe_get_headers(response) if response else {},
                'data': None,
                'cookies': self._safe_get_cookies(response) if response else {},
                'error': str(e)
            }

    def _parse_response_data(self, raw_bytes: bytes) -> Any:
        """解析响应数据"""
        try:
            return json.loads(raw_bytes.decode('utf-8', errors='replace'))
        except Exception:
            # JSON 解析失败，尝试作为文本读取
            return raw_bytes.decode('utf-8', errors='replace')

    @staticmethod
    def _safe_get_headers(response) -> Dict[str, str]:
        """安全获取headers字典"""
        try:
            return dict(response.headers)
        except (TypeError, AttributeError):
            try:
                return dict(response.headers.items())
            except (TypeError, AttributeError):
                return {'Content-Type': 'application/json'}

    @staticmethod
    def _safe_get_cookies(response) -> Dict[str, Any]:
        """安全获取cookies字典"""
        try:
            if hasattr(response, 'cookies') and response.cookies:
                return dict(response.cookies)
        except (TypeError, AttributeError):
            pass
        return {}

    async def _handle_error(self, exc_type, exc_val=None, exc_tb=None):
        """处理请求错误"""
        # 检查是否已经处理过错误，避免重复记录
        if self._error_handled:
            return

        # 标记错误已处理
        self._error_handled = True

        # 简化参数处理逻辑
        if exc_val is None:
            exc_val, exc_type, exc_tb = exc_type, type(
                exc_type), exc_type.__traceback__

        duration = time.monotonic() - self.start_time

        # 断言失败时，设置断言结果为fail
        self.log.assertion_result = "fail"

        # 更新日志
        self.log.duration = duration
        self.log.endpoint = self.log.endpoint or "unknown"

        # 获取简化的堆栈信息
        simplified_stack = self._get_simplified_stack(exc_tb)

        # 获取错误消息，如果为空则提供默认值
        error_message = str(exc_val).strip() or f"{exc_type.__name__} occurred"

        # 获取接口返回信息并附加到错误消息
        error_message = self._enrich_error_message(error_message)

        # 安全获取响应数据
        processed_data = getattr(self, '_processed_data', {})
        response_data = processed_data.get("data") if isinstance(processed_data, dict) else None
        
        self.log.error = {
            "message": error_message,
            "exc_type": exc_type.__name__,
            "stack": simplified_stack,
            "response_data": response_data
        }

        # 记录失败指标
        await self._metrics_callback(
            request_id=self.log.request_id,
            method=self.log.method,
            endpoint=self.log.endpoint,
            status_code=self.log.status_code,
            duration=self.log.duration,
            response_size=0,
            error=self.log.error,
            assertion_result=self.log.assertion_result
        )

        # 记录失败日志
        self._log_request(self.log, "failed")

    def _get_simplified_stack(self, exc_tb) -> List[str]:
        """获取简化的堆栈信息"""
        simplified_stack = []
        if exc_tb:
            stack = traceback.extract_tb(exc_tb)
            simplified_stack = [
                f"{frame.name}() at {frame.filename}:{frame.lineno}"
                for frame in stack if "aiohttp/internal" not in frame.filename
            ][:3]
        return simplified_stack

    def _enrich_error_message(self, error_message: str) -> str:
        """丰富错误消息，添加响应数据"""
        processed_data = getattr(self, '_processed_data', {})
        response_data = processed_data.get("data") if isinstance(processed_data, dict) else None

        if response_data is not None:
            # 将响应数据转换为字符串（限制长度避免过长）
            if isinstance(response_data, dict):
                response_str = json.dumps(response_data, ensure_ascii=False)
            elif isinstance(response_data, bytes):
                response_str = response_data.decode('utf-8', errors='ignore')
            else:
                response_str = str(response_data)

            # 限制响应数据长度，避免错误消息过长
            if len(response_str) > 500:
                response_str = f"{response_str[:500]}..."

            error_message = f"{error_message} | Response: {response_str}"

        return error_message

    @staticmethod
    def _estimate_size(data: Any) -> int:
        """
        估算数据大小

        参数：
        - data: 数据对象

        返回：
        - int: 估算的字节大小
        """
        if data is None:
            return 0
        return len(str(data).encode('utf-8'))
