# AioTest 事件系统文档

## 目录

- [概述](#概述)
- [核心概念](#核心概念)
- [快速开始](#快速开始)
- [API 参考](#api-参考)
- [使用示例](#使用示例)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

---

## 概述

AioTest 事件系统是一个强大的异步事件处理框架，支持基于优先级的事件处理器执行、线程安全操作、装饰器式注册等特性。

### 主要特性

- ✅ **优先级执行** - 支持按优先级顺序执行事件处理器
- ✅ **并发安全** - 使用 `asyncio.Lock` 确保在异步上下文中的并发安全
- ✅ **装饰器注册** - 支持声明式的事件处理器注册
- ✅ **同步/异步混合** - 同时支持同步和异步事件处理器
- ✅ **批量触发** - 支持批量触发事件以提高性能
- ✅ **异常隔离** - 单个处理器的异常不会影响其他处理器
- ✅ **超时保护** - 内置处理器超时保护机制（默认 5 秒）

---

## 核心概念

### EventHook

`EventHook` 是单个事件钩子，负责管理特定类型的事件处理器。

**特点：**
- 维护一个处理器列表，每个处理器包含优先级和可调用对象
- 使用 `asyncio.Lock` 确保异步上下文中的并发安全
- 支持装饰器和手动两种注册方式
- 注意：仅在单线程 asyncio 事件循环中安全，不支持多线程环境

### Events

`Events` 是集中式事件系统管理器，负责创建和管理多个 `EventHook` 实例。

**特点：**
- 自动创建事件钩子（通过 `__getattr__`）
- 统一管理所有事件的生命周期
- 支持注册装饰器定义的处理器

### 预定义事件

系统预定义了以下核心测试生命周期事件：

| 事件名称 | 说明 | 触发时机 |
|---------|------|---------|
| `init_events` | 初始化事件 | 系统初始化时 |
| `test_start` | 测试开始事件 | 测试开始时 |
| `test_stop` | 测试停止事件 | 测试停止时 |
| `test_quit` | 测试退出事件 | 测试退出时 |
| `startup_completed` | 启动完成事件 | 所有用户启动完成后 |
| `request_metrics` | 请求指标事件 | 每次请求完成后 |
| `worker_request_metrics` | Worker 请求指标事件 | Master 接收 Worker 指标时 |

---

## 快速开始

### 方式一：使用装饰器注册（推荐）

```python
from aiotest import test_start

@test_start.handler(priority=0)
async def my_test_start_handler(**kwargs):
    print("测试开始！")
```

### 方式二：手动注册

```python
from aiotest import test_start

async def my_handler(**kwargs):
    print("测试开始！")

await test_start.add_handler(my_handler, priority=0)
```

### 运行示例

```bash
py -m aiotest -f examples/events_example.py
```

---

## API 参考

### EventHook

#### `handler(priority: int = 0)`

装饰器方法，用于声明式注册事件处理器。

**参数：**
- `priority` (int): 优先级，数值越大优先级越高，默认为 0

**返回：** 装饰器函数

**示例：**

```python
@event_hook.handler(priority=10)
async def high_priority_handler(**kwargs):
    print("高优先级处理器")
```

---

#### `async add_handler(handler: Callable, priority: int = 0) -> None`

添加事件处理器。

**参数：**
- `handler` (Callable): 事件处理器函数
- `priority` (int): 处理器的优先级，数值越高越先执行，默认为 0

**异常：**
- `TypeError`: 如果 handler 不是可调用对象

**示例：**

```python
async def my_handler(**kwargs):
    print("处理事件")

await event_hook.add_handler(my_handler, priority=5)
```

---

#### `async remove_handler(handler: Callable) -> None`

移除事件处理器。

**参数：**
- `handler` (Callable): 要移除的事件处理器函数

**示例：**

```python
await event_hook.remove_handler(my_handler)
```

---

#### `async fire(**kwargs: Any) -> None`

触发事件，执行所有注册的处理器。

**参数：**
- `**kwargs` (Any): 传递给事件处理器的参数

**示例：**

```python
await event_hook.fire(user_id=123, action="login")
```

---

#### `async fire_batch(events: List[Dict[str, Any]]) -> None`

批量触发事件，提高性能。

**参数：**
- `events` (List[Dict[str, Any]]): 事件字典列表

**异常：**
- `RuntimeError`: 如果任务数量超过限制（1000）

**示例：**

```python
events = [
    {"user_id": 1, "action": "login"},
    {"user_id": 2, "action": "logout"}
]
await event_hook.fire_batch(events)
```

---

#### `async register_pending_handlers() -> int`

注册所有通过装饰器定义的待注册处理器。

**返回：** 注册的处理器数量

**示例：**

```python
count = await event_hook.register_pending_handlers()
print(f"注册了 {count} 个处理器")
```

---

### Events

#### `register(name: str) -> EventHook`

注册新事件类型。

**参数：**
- `name` (str): 事件类型名称

**返回：** EventHook 实例

**示例：**

```python
custom_event = events.register("custom_event")
```

---

#### `async register_all_pending_handlers() -> int`

注册所有事件钩子的待注册处理器。

**返回：** 注册的处理器总数

**示例：**

```python
total = await events.register_all_pending_handlers()
print(f"总共注册了 {total} 个处理器")
```

---

#### `__getattr__(name: str) -> EventHook`

获取事件钩子，如果不存在则自动注册。

**参数：**
- `name` (str): 事件钩子名称

**返回：** EventHook 实例

**示例：**

```python
# 自动注册并获取事件钩子
my_event = events.my_event
```

---

## 使用示例

### 示例 1：基础装饰器注册

```python
from aiotest import test_start, test_stop

@test_start.handler(priority=0)
async def on_test_start(**kwargs):
    print("测试开始执行")

@test_stop.handler(priority=0)
async def on_test_stop(**kwargs):
    print("测试执行结束")
```

---

### 示例 2：优先级执行

```python
from aiotest import request_metrics

@request_metrics.handler(priority=10)  # 最高优先级
async def log_slow_requests(**kwargs):
    duration = kwargs.get('duration', 0)
    if duration > 1000:
        print(f"慢请求: {duration}ms")

@request_metrics.handler(priority=5)  # 中等优先级
async def log_errors(**kwargs):
    status = kwargs.get('status_code', 0)
    if status >= 400:
        print(f"错误请求: {status}")

@request_metrics.handler(priority=0)  # 默认优先级
async def log_all_requests(**kwargs):
    print(f"请求: {kwargs.get('request_id')}")
```

---

### 示例 3：手动注册处理器

```python
from aiotest import test_start

async def setup_test(**kwargs):
    print("设置测试环境")

async def initialize_data(**kwargs):
    print("初始化测试数据")

# 在初始化阶段注册
await test_start.add_handler(setup_test, priority=10)
await test_start.add_handler(initialize_data, priority=5)
```

---

### 示例 4：动态创建自定义事件

```python
from aiotest import events

# 创建自定义事件
user_event = events.register("user_login")

@user_event.handler(priority=0)
async def on_user_login(**kwargs):
    user_id = kwargs.get('user_id')
    print(f"用户 {user_id} 登录")

# 触发自定义事件
await user_event.fire(user_id=123, timestamp="2024-01-01")
```

---

### 示例 5：同步和异步处理器混合

```python
from aiotest import test_start

# 异步处理器
@test_start.handler(priority=10)
async def async_setup(**kwargs):
    await asyncio.sleep(0.1)
    print("异步设置完成")

# 同步处理器
@test_start.handler(priority=5)
def sync_setup(**kwargs):
    print("同步设置完成")
```

---

### 示例 6：批量触发事件

```python
from aiotest import events

# 创建批量处理事件
batch_event = events.register("batch_process")

@batch_event.handler(priority=0)
async def process_item(**kwargs):
    item_id = kwargs.get('item_id')
    # 处理单个项目
    print(f"处理项目 {item_id}")

# 批量触发
items = [{"item_id": i} for i in range(100)]
await batch_event.fire_batch(items)
```

---

### 示例 7：移除处理器

```python
from aiotest import test_start

async def temp_handler(**kwargs):
    print("临时处理器")

# 注册处理器
await test_start.add_handler(temp_handler, priority=0)

# 触发事件（会调用 temp_handler）
await test_start.fire()

# 移除处理器
await test_start.remove_handler(temp_handler)

# 触发事件（不会调用 temp_handler）
await test_start.fire()
```

---

## 最佳实践

### 1. 使用装饰器优先

推荐使用装饰器方式注册事件处理器，代码更清晰易读：

```python
# ✅ 推荐
@test_start.handler(priority=0)
async def on_test_start(**kwargs):
    print("测试开始")

# ❌ 不推荐（除非需要动态注册）
async def on_test_start(**kwargs):
    print("测试开始")
await test_start.add_handler(on_test_start)
```

---

### 2. 合理设置优先级

根据业务逻辑设置合理的优先级：

```python
# 验证逻辑应该先执行
@test_start.handler(priority=20)
async def validate(**kwargs):
    if not validate_test(**kwargs):
        raise ValueError("测试配置无效")

# 初始化操作中等优先级
@test_start.handler(priority=10)
async def setup(**kwargs):
    setup_test_env(**kwargs)

# 日志记录最后执行
@test_start.handler(priority=0)
async def log(**kwargs):
    logger.info("测试开始")
```

---

### 3. 处理器应该幂等

确保事件处理器可以安全地被多次调用：

```python
# ✅ 好的实践 - 幂等
@request_metrics.handler(priority=0)
async def log_request(**kwargs):
    request_id = kwargs.get('request_id')
    logger.info(f"请求完成: {request_id}")

# ❌ 坏的实践 - 有副作用
@request_metrics.handler(priority=0)
async def log_request(**kwargs):
    global counter
    counter += 1  # 可能导致计数不准确
```

---

### 4. 使用参数传递上下文信息

通过 `**kwargs` 传递事件相关的上下文信息：

```python
@request_metrics.handler(priority=10)
async def monitor_performance(**kwargs):
    duration = kwargs.get('duration')
    endpoint = kwargs.get('endpoint')
    if duration > 1000:
        logger.warning(f"慢请求: {endpoint}, 耗时: {duration}ms")
```

---

### 5. 处理器应该捕获自己的异常

虽然系统会捕获处理器异常，但建议在处理器内部处理预期内的异常：

```python
@test_start.handler(priority=0)
async def setup_database(**kwargs):
    try:
        await connect_database()
    except DatabaseError as e:
        logger.error(f"数据库连接失败: {e}")
        # 不要抛出异常，避免影响其他处理器
```

---

### 6. 避免长时间运行的处理器

系统默认超时时间为 5 秒，避免处理器执行时间过长：

```python
# ❌ 坏的实践 - 可能超时
@test_start.handler(priority=0)
async def load_large_data(**kwargs):
    data = await download_large_file()  # 可能超过 5 秒

# ✅ 好的实践 - 使用后台任务
@test_start.handler(priority=0)
async def start_background_task(**kwargs):
    asyncio.create_task(download_large_data())
```

---

### 7. 使用去重机制

系统会自动去重相同的处理器对象（使用 `is` 比较）：

```python
# 安全地多次注册同一个处理器
await test_start.add_handler(my_handler)
await test_start.add_handler(my_handler)  # 不会重复注册
```

**注意：** 去重对 `lambda` 函数无效，每次调用 `lambda` 都会创建新对象：

```python
# ❌ 会被重复注册 3 次
await test_start.add_handler(lambda **kwargs: print("1"))
await test_start.add_handler(lambda **kwargs: print("1"))
await test_start.add_handler(lambda **kwargs: print("1"))

# ✅ 使用命名函数可以正确去重
async def my_handler(**kwargs):
    print("1")
await test_start.add_handler(my_handler)
await test_start.add_handler(my_handler)  # 不会重复注册
```

---

## 常见问题

### Q1: 装饰器和手动注册可以混合使用吗？

**A:** 可以。两种注册方式完全兼容，处理器会按优先级统一执行。

```python
# 装饰器注册
@test_start.handler(priority=10)
async def handler1(**kwargs):
    pass

# 手动注册
await test_start.add_handler(handler2, priority=5)
```

---

### Q2: 处理器抛出异常会影响其他处理器吗？

**A:** 不会。系统会捕获每个处理器的异常，继续执行其他处理器。

```python
@test_start.handler(priority=10)
async def handler_with_error(**kwargs):
    raise ValueError("This won't affect others")

@test_start.handler(priority=5)
async def handler_normal(**kwargs):
    print("This will still execute")  # 仍然会执行
```

---

### Q3: 如何确保处理器按特定顺序执行？

**A:** 使用优先级参数，数值越大越先执行。

```python
@test_start.handler(priority=20)
async def first(**kwargs):
    print("First")

@test_start.handler(priority=10)
async def second(**kwargs):
    print("Second")

@test_start.handler(priority=0)
async def third(**kwargs):
    print("Third")
```

---

### Q4: 同步和异步处理器可以混用吗？

**A:** 可以。系统会自动识别处理器类型并正确执行。

```python
@test_start.handler(priority=10)
async def async_handler(**kwargs):
    await asyncio.sleep(0.1)

@test_start.handler(priority=5)
def sync_handler(**kwargs):
    print("Sync handler")
```

---

### Q5: 如何移除已注册的处理器？

**A:** 使用 `remove_handler` 方法，传入同一个处理器对象。

```python
async def my_handler(**kwargs):
    pass

await test_start.add_handler(my_handler)
await test_start.remove_handler(my_handler)
```

---

### Q6: 批量触发事件有什么限制？

**A:** 单次批量触发的任务总数不能超过 1000，防止系统过载。

```python
# ✅ 正常
events = [{"id": i} for i in range(500)]
await event_hook.fire_batch(events)

# ❌ 会抛出 RuntimeError
events = [{"id": i} for i in range(1010)]
await event_hook.fire_batch(events)
```

---

### Q7: 如何获取当前已注册的处理器数量？

**A:** 可以直接访问 `_handlers` 属性（不推荐用于生产代码）。

```python
event_hook = EventHook()
await event_hook.add_handler(handler1)
await event_hook.add_handler(handler2)

print(len(event_hook._handlers))  # 输出: 2
```

---

### Q8: 处理器的超时时间可以修改吗？

**A:** 当前版本超时时间固定为 5 秒，如需修改需要修改源码中的 `_safe_execute` 方法。

```python
async def _safe_execute(self, handler, **kwargs):
    try:
        # 可以修改这里的超时时间
        await asyncio.wait_for(handler(**kwargs), timeout=5.0)
    except asyncio.TimeoutError:
        # ...
```

---

### Q9: 可以在处理器中修改处理器列表吗？

**A:** 不推荐在处理器执行期间添加或移除处理器，可能导致不可预测的行为。建议在事件触发前完成所有处理器注册。

---

### Q10: 事件系统是线程安全的吗？

**A:** 不是。事件系统使用 `asyncio.Lock` 只保证在**单线程 asyncio 事件循环**中的并发安全，**不支持多线程环境**。

如果需要在多线程环境中使用，请确保：
- 所有事件操作都在同一个线程中执行
- 或者使用 `threading.Lock` 等多线程同步机制（需要自行实现）

---

## 技术说明

### 并发模型

AioTest 事件系统基于 **asyncio 协程**，设计用于单线程异步编程模型：

- **适用场景**: 单线程、高并发的异步应用
- **不适用场景**: 多线程环境或需要跨线程同步的场景

### 安全保证

在 asyncio 单线程事件循环中：
- ✅ 多个协程并发添加/移除处理器 - 安全
- ✅ 多个协程同时触发事件 - 安全
- ❌ 多线程同时操作事件系统 - **不安全**

如果确实需要在多线程中使用，需要额外实现多线程同步机制。

---

## 性能考虑

### 处理器数量建议

- **推荐**: 每个事件的处理器数量 < 20
- **警告**: 每个事件的处理器数量 > 50 可能影响性能
- **限制**: 单次批量触发任务数 ≤ 1000

### 性能优化建议

1. **减少同步处理器** - 同步处理器会被放到执行器中运行，性能较低
2. **合理使用批量触发** - 对于大量事件，使用 `fire_batch` 提高性能
3. **避免复杂计算** - 将复杂计算放到后台任务中
4. **控制处理器数量** - 避免在一个事件上注册过多处理器

---

## 相关资源

- [完整示例代码](../examples/events_example.py)
- [测试用例](../tests/test_events.py)
- [项目主文档](../README.md)
