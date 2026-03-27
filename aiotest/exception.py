# encoding: utf-8
"""
AioTest自定义异常模块

定义了框架中使用的所有自定义异常类型，提供清晰的错误分类和详细的错误信息。
"""


class AioTestError(Exception):
    """AioTest框架基础异常类"""

    def __init__(self, message: str, error_code: str = None,
                 context: dict = None):
        """
        初始化异常

        Args:
            message: 错误信息
            error_code: 错误代码，用于程序化处理
            context: 错误上下文信息，包含相关的状态数据
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}

    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class RunnerError(AioTestError):
    """运行器异常，用于测试运行过程中的错误"""
    pass


class InvalidUserCountError(RunnerError):
    """无效用户数量异常"""

    def __init__(self, message: str, user_count: int = None):
        context = {'user_count': user_count} if user_count is not None else {}
        super().__init__(message, "INVALID_USER_COUNT", context)
        self.user_count = user_count


class InvalidRateError(RunnerError):
    """无效速率异常"""

    def __init__(self, message: str, rate: float = None):
        context = {'rate': rate} if rate is not None else {}
        super().__init__(message, "INVALID_RATE", context)
        self.rate = rate


# 异常映射表，用于错误码到异常类的转换
EXCEPTION_MAP = {
    "INVALID_USER_COUNT": InvalidUserCountError,
    "INVALID_RATE": InvalidRateError,
}


def create_exception(error_code: str, message: str,
                     context: dict = None) -> AioTestError:
    """
    根据错误码创建对应的异常实例

    Args:
        error_code: 错误代码
        message: 错误信息
        context: 错误上下文

    Returns:
        对应的异常实例

    Raises:
        ValueError: 如果错误码无效
    """
    exception_class = EXCEPTION_MAP.get(error_code, AioTestError)

    # 对于 AioTestError 或其他没有特殊参数的异常
    if exception_class == AioTestError:
        return exception_class(message, error_code, context)

    # 对于有特殊参数的异常类，从 context 中提取参数
    context = context or {}
    if exception_class == InvalidUserCountError:
        return exception_class(message, user_count=context.get('user_count'))
    elif exception_class == InvalidRateError:
        return exception_class(message, rate=context.get('rate'))
    else:
        return exception_class(message, error_code, context)
