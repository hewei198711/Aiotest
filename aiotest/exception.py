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
