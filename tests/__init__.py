# encoding: utf-8
"""
AioTest测试包

这个包包含了AioTest框架的所有测试用例，包括：
- 单元测试：各个模块的独立功能测试
- 集成测试：模块间协作测试
- 性能测试：性能和资源使用测试
- 端到端测试：完整的负载测试场景

测试结构：
- conftest.py: pytest配置和共享fixtures
- test_http_clients.py: HTTP客户端测试
- test_users.py: 用户类测试
- test_runners.py: 运行器测试
- test_config.py: 配置管理测试
- test_events.py: 事件系统测试
- test_metrics.py: 指标系统测试
- test_exception.py: 异常处理测试
- test_integration.py: 集成测试

运行测试：
```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_http_clients.py

# 运行带allure报告的测试
pytest tests/ --alluredir=reports/allure

# 运行性能测试
pytest tests/ -m performance

# 运行集成测试
pytest tests/ -m integration
```
"""

__version__ = "1.0.0"
__author__ = "AioTest Team"
