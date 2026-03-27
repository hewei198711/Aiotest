# AioTest 文档中心

欢迎使用 AioTest 文档中心！这里包含了 AioTest 负载测试框架的完整文档资源。

## 📚 快速导航

### 🚀 快速开始
- [项目介绍](../README.md) - AioTest 项目概述和特性介绍
- [安装指南](../README.md#安装) - 如何安装和配置 AioTest
- [快速开始](../README.md#快速开始) - 5分钟快速上手指南

### 📖 模块文档
详细的模块 API 文档和实现说明：

| 模块 | 文档 | 描述 |
|------|------|------|
| [主模块](MAIN_MODULE_DOC.md) | [查看](MAIN_MODULE_DOC.md) | 命令行解析、测试加载、主入口 |
| [运行器模块](RUNNERS_MODULE_DOC.md) | [查看](RUNNERS_MODULE_DOC.md) | LocalRunner、MasterRunner、WorkerRunner |
| [运行器工厂](RUNNER_FACTORY_MODULE_DOC.md) | [查看](RUNNER_FACTORY_MODULE_DOC.md) | 运行器创建和管理 |
| [用户模块](USERS_MODULE_DOC.md) | [查看](USERS_MODULE_DOC.md) | HttpUser、任务执行、生命周期 |
| [用户管理器](USER_MANAGER_MODULE_DOC.md) | [查看](USER_MANAGER_MODULE_DOC.md) | 用户创建、停止、管理 |
| [客户端模块](CLIENTS_MODULE_DOC.md) | [查看](CLIENTS_MODULE_DOC.md) | HTTPClient、连接管理 |
| [指标模块](METRICS_MODULE_DOC.md) | [查看](METRICS_MODULE_DOC.md) | Prometheus 指标收集 |
| [负载形状管理器](LOAD_SHAPE_MANAGER_MODULE_DOC.md) | [查看](LOAD_SHAPE_MANAGER_MODULE_DOC.md) | 负载形状执行和管理 |
| [分布式协调器](DISTRIBUTED_COORDINATOR_MODULE_DOC.md) | [查看](DISTRIBUTED_COORDINATOR_MODULE_DOC.md) | 分布式锁、心跳、发布订阅 |
| [事件模块](EVENTS_MODULE_DOC.md) | [查看](EVENTS_MODULE_DOC.md) | 事件系统、钩子函数 |
| [日志模块](LOGGER_MODULE_DOC.md) | [查看](LOGGER_MODULE_DOC.md) | 日志配置、格式化、处理器 |
| [状态管理器](STATE_MANAGER_MODULE_DOC.md) | [查看](STATE_MANAGER_MODULE_DOC.md) | 状态机、状态转换 |
| [任务管理器](TASK_MANAGER_MODULE_DOC.md) | [查看](TASK_MANAGER_MODULE_DOC.md) | 任务创建、取消、等待 |
| [形状模块](SHAPE_MODULE_DOC.md) | [查看](SHAPE_MODULE_DOC.md) | LoadUserShape 基类 |
| [异常模块](EXCEPTION_MODULE_DOC.md) | [查看](EXCEPTION_MODULE_DOC.md) | 自定义异常类 |



### 📝 指南文档
面向用户和开发者的实用指南：

| 指南 | 描述 | 适用人群 |
|------|------|---------|
| [快速入门指南](QUICKSTART.md) | 5分钟快速上手指南 | 所有用户 |
| [架构设计](../ARCHITECTURE.md) | 系统架构和设计 | 架构师、开发者 |
| [最佳实践](BEST_PRACTICES.md) | 负载测试最佳实践 | 测试工程师 |

### 💡 示例代码
丰富的示例代码，涵盖各种使用场景：

- [示例目录](../examples/) - 查看所有示例
- [基础示例](../examples/basic.py) - 最简单的测试示例
- [分布式测试](../examples/distributed_test.py) - 分布式测试

**示例分类**：
- **基础级**：basic.py, concurrent_example.py, request_verification.py
- **进阶级**：distributed_example.py, events_example.py, weight_and_wait.py
- **高级**：seckill_scenario.py

### 🔧 参考资料
技术参考和配置说明：

| 参考 | 描述 |
|------|------|
| [API 参考](API_REFERENCE.md) | 完整的 API 参考 |



## 📊 文档统计

- **模块文档**: 16 个
- **指南文档**: 7 个
- **示例代码**: 20+ 个
- **总文档数**: 40+ 个

## 🔍 文档搜索

### 按主题搜索

**性能相关**：
- [最佳实践](BEST_PRACTICES.md)
- [指标模块](METRICS_MODULE_DOC.md)
- [负载形状管理器](LOAD_SHAPE_MANAGER_MODULE_DOC.md)

**分布式相关**：
- [分布式协调器](DISTRIBUTED_COORDINATOR_MODULE_DOC.md)
- [运行器模块](RUNNERS_MODULE_DOC.md)

**测试相关**：
- [用户模块](USERS_MODULE_DOC.md)
- [示例代码](../examples/)
- [快速入门指南](QUICKSTART.md)

**监控相关**：
- [指标模块](METRICS_MODULE_DOC.md)
- [日志模块](LOGGER_MODULE_DOC.md)

## 📝 文档贡献

我们欢迎社区贡献！如果你想改进文档：

1. **发现问题**：在 GitHub 上提交 Issue
2. **改进文档**：Fork 项目，修改文档，提交 PR
3. **添加示例**：添加新的示例代码
4. **翻译文档**：将文档翻译成其他语言


## 🔗 外部资源

- **官方网站**: [https://aiotest.io](https://aiotest.io)
- **GitHub 仓库**: [https://github.com/hewei198711/Aiotest](https://github.com/hewei198711/Aiotest)
- **PyPI 包**: [https://pypi.org/project/aiotest/](https://pypi.org/project/aiotest/)



## 📅 文档更新

- **最后更新**: 2026-03-25
- **文档版本**: 1.0.0
- **维护状态**: ✅ 活跃维护

---

**提示**: 使用 Ctrl+F 或 Cmd+F 在页面中快速搜索关键词。
