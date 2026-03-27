# AioTest API 参考手册

本手册提供了 AioTest 框架的完整 API 参考，按模块分类列出所有公开 API。

## 📚 目录

- [用户模块](#用户模块)
- [运行器模块](#运行器模块)
- [负载形状模块](#负载形状模块)
- [状态管理模块](#状态管理模块)
- [用户管理模块](#用户管理模块)
- [指标模块](#指标模块)
- [事件模块](#事件模块)
- [分布式协调模块](#分布式协调模块)

---

## 用户模块

### User 类

基础用户类，定义测试用户行为。

#### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `host` | `Optional[str]` | `None` | 目标主机地址 |
| `wait_time` | `WaitTimeType` | `1.0` | 任务执行间隔时间 |
| `weight` | `int` | `1` | 用户权重 |
| `max_concurrent_tasks` | `Optional[int]` | `None` | 最大并发任务数 |
| `execution_mode` | `ExecutionMode` | `SEQUENTIAL` | 任务执行模式 |

#### 方法

##### `on_start(self)` -> `None`
用户启动时调用，用于初始化资源。

##### `on_stop(self)` -> `None`
用户停止时调用，用于清理资源。

##### `start_tasks(self)` -> `None`
启动用户任务。

##### `stop_tasks(self)` -> `None`
停止用户任务。

##### `pause_tasks(self)` -> `None`
暂停用户任务。

##### `resume_tasks(self)` -> `None`
恢复用户任务。

### HttpUser 类

HTTP 用户类，继承自 User，提供 HTTP 客户端功能。

#### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `host` | `str` | `None` | HTTP 服务地址 |
| `timeout` | `int` | `30` | HTTP 请求超时时间（秒）|
| `max_retries` | `int` | `3` | HTTP 请求最大重试次数 |
| `verify_ssl` | `bool` | `True` | 是否验证 SSL 证书 |

#### 方法

##### `client` (property) -> `HTTPClient`
获取 HTTP 客户端实例。

---

## 运行器模块

### LocalRunner 类

本地运行器，用于单机负载测试。

#### 方法

##### `__init__(self, user_types, load_shape, config)`
初始化本地运行器。

**参数**:
- `user_types`: 用户类型列表
- `load_shape`: 负载形状类
- `config`: 配置字典

##### `initialize(self)` -> `None`
初始化本地运行器。

##### `start(self)` -> `None`
启动测试。

##### `stop(self)` -> `None`
停止测试。

##### `pause(self)` -> `None`
暂停测试。

##### `resume(self)` -> `None`
恢复测试。

##### `quit(self)` -> `None`
退出测试。

### MasterRunner 类

主节点运行器，用于分布式测试协调。

#### 方法

##### `__init__(self, user_types, load_shape, config, redis_client)`
初始化主节点运行器。

**参数**:
- `user_types`: 用户类型列表
- `load_shape`: 负载形状类
- `config`: 配置字典
- `redis_client`: Redis 客户端

##### `initialize(self)` -> `None`
初始化主节点。

##### `start(self)` -> `None`
启动测试。

##### `stop(self)` -> `None`
停止测试。

##### `pause(self)` -> `None`
暂停测试。

##### `resume(self)` -> `None`
恢复测试。

##### `quit(self)` -> `None`
退出测试。

### WorkerRunner 类

工作节点运行器，用于分布式测试执行。

#### 方法

##### `__init__(self, user_types, load_shape, config, redis_client)`
初始化工作节点运行器。

**参数**:
- `user_types`: 用户类型列表
- `load_shape`: 负载形状类
- `config`: 配置字典
- `redis_client`: Redis 客户端

##### `initialize(self)` -> `None`
初始化工作节点。

##### `start(self)` -> `None`
启动测试。

##### `stop(self)` -> `None`
停止测试。

##### `pause(self)` -> `None`
暂停测试。

##### `resume(self)` -> `None`
恢复测试。

##### `quit(self)` -> `None`
退出测试。

---

## 负载形状模块

### LoadUserShape 类

负载形状基类，用于定义负载变化策略。

#### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `start_time` | `float` | 当前时间 | 测试开始时间 |
| `paused_time` | `float` | `0.0` | 暂停开始的时间 |

#### 方法

##### `__init__(self)`
初始化负载形状控制器。

##### `reset_time(self)` -> `None`
重置开始时间。

##### `get_run_time(self)` -> `float`
获取运行时长（秒）。

##### `tick(self)` -> `Optional[Tuple[int, float]]`
获取当前时刻的负载控制参数。

**返回值**: `(user_count, rate)` 元组或 `None`

---

## 状态管理模块

### RunnerState 枚举

运行器状态枚举。

#### 枚举值

| 值 | 说明 |
|------|------|
| `READY` | 就绪/已停止状态 |
| `STARTING` | 启动中 |
| `RUNNING` | 运行中 |
| `PAUSED` | 暂停中 |
| `MISSING` | 丢失（仅用于工作节点）|
| `STOPPING` | 停止中 |
| `QUITTING` | 退出中 |

### StateManager 类

状态管理器，管理运行器状态转换。

#### 方法

##### `__init__(self)`
初始化状态管理器。

##### `transition_state(self, new_state)` -> `None`
转换到新状态。

**参数**:
- `new_state`: 目标状态

##### `set_quit_state(self)` -> `None`
设置退出状态。

##### `is_in_quit_state(self)` -> `bool`
检查是否处于退出状态。

##### `get_current_state(self)` -> `RunnerState`
获取当前状态。

##### `can_start(self)` -> `bool`
检查是否可以启动。

##### `is_running(self)` -> `bool`
检查是否正在运行。

##### `can_stop(self)` -> `bool`
检查是否可以停止。

##### `can_pause(self)` -> `bool`
检查是否可以暂停。

##### `can_resume(self)` -> `bool`
检查是否可以恢复。

---

## 用户管理模块

### UserManager 类

用户管理器，管理用户的创建、启动、停止。

#### 方法

##### `__init__(self, user_types, config)`
初始化用户管理器。

**参数**:
- `user_types`: 用户类型列表
- `config`: 配置字典

##### `manage_users(self, user_count, rate, action)` -> `None`
管理用户（启动/停止）。

**参数**:
- `user_count`: 目标用户数
- `rate`: 操作速率（个/秒）
- `action`: 操作类型（'start' 或 'stop'）

##### `stop_all_users(self)` -> `None`
停止所有用户。

##### `pause_all_users(self)` -> `None`
暂停所有用户。

##### `resume_all_users(self)` -> `None`
恢复所有用户。

##### `active_user_count` (property) -> `int`
获取活跃用户数量。

##### `cleanup_inactive_users(self)` -> `None`
清理非活跃用户。

---

## 指标模块

### MetricsCollector 类

指标收集器，收集和上报测试指标。

#### 方法

##### `__init__(self, node, redis_client, node_id, coordinator, batch_size, flush_interval, buffer_size)`
初始化指标收集器。

**参数**:
- `node`: 节点类型
- `redis_client`: Redis 客户端
- `node_id`: 节点 ID
- `coordinator`: 分布式协调器
- `batch_size`: 批量大小
- `flush_interval`: 刷新间隔（秒）
- `buffer_size`: 缓冲区大小

##### `start(self)` -> `None`
启动指标收集器。

##### `stop(self)` -> `None`
停止指标收集器。

---

## 事件模块

### request_metrics 事件

请求指标事件。

#### 方法

##### `handler(priority)` -> `Callable`
注册事件处理器的装饰器。

**参数**:
- `priority`: 处理器优先级

##### `add_handler(handler, priority)` -> `None`
添加事件处理器。

**参数**:
- `handler`: 处理器函数
- `priority`: 处理器优先级

##### `fire(**kwargs)` -> `None`
触发事件。

**参数**:
- `**kwargs`: 事件数据

---

## 分布式协调模块

### DistributedCoordinator 类

分布式协调器，管理分布式节点间的通信。

#### 方法

##### `__init__(self, redis_client, node_id, node_type)`
初始化分布式协调器。

**参数**:
- `redis_client`: Redis 客户端
- `node_id`: 节点 ID
- `node_type`: 节点类型

##### `publish(self, channel_type, data, worker_id, **kwargs)` -> `None`
发布消息到指定频道。

**参数**:
- `channel_type`: 频道类型（'command', 'request_metrics', 'heartbeat'）
- `data`: 消息数据
- `worker_id`: 目标 Worker ID
- `**kwargs`: 额外参数

##### `subscribe(self, channel_type, handler)` -> `None`
订阅指定频道。

**参数**:
- `channel_type`: 频道类型
- `handler`: 消息处理器

### RedisLock 类

分布式锁，用于分布式环境下的互斥操作。

#### 方法

##### `with_lock(redis_client, lock_name, timeout)` -> `AsyncContextManager`
获取分布式锁的上下文管理器。

**参数**:
- `redis_client`: Redis 客户端
- `lock_name`: 锁名称
- `timeout`: 超时时间（秒）

---

## 辅助函数

### create_prometheus_app(runner=None) -> `web.Application`

创建 Prometheus 指标 HTTP 应用。

**参数**:
- `runner`: 运行器实例（可选）

**返回值**: aiohttp 应用实例

---

## 枚举类型

### ExecutionMode 枚举

任务执行模式枚举。

#### 枚举值

| 值 | 说明 |
|------|------|
| `SEQUENTIAL` | 顺序执行，任务按顺序逐个执行 |
| `CONCURRENT` | 并发执行，任务并行执行 |

### WaitTimeType 类型定义

等待时间类型定义。

```python
WaitTimeType = Union[
    float,  # 固定等待时间
    Tuple[float, float],  # 随机范围 (min, max)
    Callable[[], float],  # 同步函数，返回等待时间
    Callable[[], Awaitable[float]],  # 异步函数，返回等待时间
]
```

---

## 装饰器

### weight(weight_value)

为任务函数设置权重的装饰器。

**参数**:
- `weight_value`: 权重值（正整数）

**示例**:
```python
from aiotest import weight

class MyUser(HttpUser):
    @weight(5)  # 高权重
    async def test_important_api(self):
        pass
    
    @weight(1)  # 低权重
    async def test_normal_api(self):
        pass
```

---

## 📞 获取帮助

如果您在 API 使用中遇到问题：

1. 查看 [常见问题](FAQ.md)
2. 参考 [模块文档](README.md#模块文档)
3. 提交 [GitHub Issue](https://github.com/hewei198711/Aiotest/issues)

---

**提示**: 本 API 参考手册涵盖了 AioTest 的主要公开 API，更多详细信息请参考各模块文档。
