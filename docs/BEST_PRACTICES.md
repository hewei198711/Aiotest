# AioTest 最佳实践指南

本指南提供了 AioTest 负载测试的最佳实践，帮助您设计高效、可靠的负载测试。

## 📋 目录

- [负载测试设计](#%E8%B4%9F%E8%BD%BD%E6%B5%8B%E8%AF%95%E8%AE%BE%E8%AE%A1)
- [参数调优](#%E5%8F%82%E6%95%B0%E8%B0%83%E4%BC%98)
- [性能优化](#%E6%80%A7%E8%83%BD%E4%BC%98%E5%8C%96)
- [分布式测试最佳实践](#%E5%88%86%E5%B8%83%E5%BC%8F%E6%B5%8B%E8%AF%95%E6%9C%80%E4%BD%B3%E5%AE%9E%E8%B7%B5)
- [监控和调优](#%E7%9B%91%E6%8E%A7%E5%92%8C%E8%B0%83%E4%BC%98)

______________________________________________________________________

## 负载测试设计

### 1.1 确定测试目标

在设计负载测试之前，明确测试目标至关重要：

**性能基准测试**：

- 目标：建立系统性能基准
- 策略：逐步增加负载，记录性能指标
- 示例：从10用户开始，每30秒增加10用户，直到500用户

**容量规划测试**：

- 目标：确定系统最大承载能力
- 策略：持续增加负载直到系统饱和
- 示例：从100用户开始，每分钟增加50用户，直到响应时间超过阈值

**稳定性测试**：

- 目标：验证系统长时间运行的稳定性
- 策略：保持中等负载运行较长时间
- 示例：保持200用户负载运行24小时

**压力测试**：

- 目标：发现系统极限和故障点
- 策略：快速增加负载到极限
- 示例：从500用户开始，每10秒增加100用户

### 1.2 设计真实的负载模式

避免使用不切实际的负载模式：

**好的实践**：

```python

class RealisticLoadShape(LoadUserShape):
    def tick(self):
        run_time = self.get_run_time()

        # 模拟真实用户行为：缓慢增长，波动
        if run_time < 300:  # 前5分钟
            return (50, 2)   # 缓慢启动
        elif run_time < 1800:  # 5-30分钟
            # 模拟业务高峰期
            import math
            base = 100
            wave = 50 * math.sin(2 * math.pi * (run_time - 300) / 300)
            return (int(base + wave), 5)
        else:
            return None

```

**避免的实践**：

```python
# 避免：瞬间达到最大负载

class BadLoadShape(LoadUserShape):
    def tick(self):
        return (10000, 1000)  # 不切实际的瞬间高负载

```

### 1.3 设计多样化的用户行为

创建不同类型的用户，模拟真实场景：

```python

class BrowsingUser(HttpUser):
    """浏览型用户：主要进行读取操作"""
    weight = 3
    host = "https://api.example.com"
            wait_time = (2, 5)
            execution_mode = ExecutionMode.CONCURRENT

    @weight(5)
    async def test_view_products(self):
        async with self.client.get("/products") as resp:
            assert resp.status == 200

    @weight(3)
    async def test_view_product_detail(self):
        async with self.client.get("/products/123") as resp:
            assert resp.status == 200

class ShoppingUser(HttpUser):
    """购物型用户：包含写入操作"""
    weight = 1
    host = "https://api.example.com"
            wait_time = (1, 3)
            execution_mode = ExecutionMode.CONCURRENT

    @weight(2)
    async def test_add_to_cart(self):
        data = {"product_id": 123, "quantity": 1}
        async with self.client.post("/cart", json=data) as resp:
            assert resp.status == 201

    @weight(1)
    async def test_checkout(self):
        async with self.client.post("/checkout") as resp:
            assert resp.status == 200

class AdminUser(HttpUser):
    """管理型用户：执行管理操作"""
    weight = 1
    host = "https://api.example.com"
    wait_time = (5, 10)

    async def test_view_analytics(self):
        async with self.client.get("/admin/analytics") as resp:
            assert resp.status == 200

```

______________________________________________________________________

## 参数调优

### 2.1 用户数量调优

**原则**：从少量用户开始，逐步增加

```python

class OptimizedLoadShape(LoadUserShape):
    def __init__(self):
        super().__init__()
        self.stages = [
            (60, 10, 2),    # 1分钟：10用户，每秒2个
            (120, 50, 5),   # 2分钟：50用户，每秒5个
            (180, 100, 10),  # 3分钟：100用户，每秒10个
            (240, 200, 20),  # 4分钟：200用户，每秒20个
            (300, 500, 50),  # 5分钟：500用户，每秒50个
        ]

    def tick(self):
        run_time = self.get_run_time()
        for duration, user_count, rate in self.stages:
            if run_time < duration:
                return (user_count, rate)
        return None

```

**调优建议**：

- 初始阶段：10-50用户，验证系统稳定性
- 中等阶段：50-200用户，观察性能变化
- 高负载阶段：200-500用户，测试系统极限
- 极限阶段：500+用户，发现系统瓶颈

### 2.2 等待时间调优

**原则**：根据实际业务场景设置合理的等待时间

```python

class RealisticWaitTimeUser(HttpUser):
    """根据业务场景设置等待时间"""

    # 固定等待时间：适合稳定的测试场景
    wait_time = 2.0

    # 随机等待时间：模拟真实用户行为
    wait_time = (1.0, 3.0)

    # 动态等待时间：根据系统负载调整
    def get_wait_time(self):
        import random
        # 根据时间调整：白天等待时间短，夜间等待时间长
        import datetime
        hour = datetime.datetime.now().hour
        if 9 <= hour <= 18:  # 工作时间
            return random.uniform(0.5, 2.0)
        else:  # 非工作时间
            return random.uniform(2.0, 5.0)

    wait_time = get_wait_time

```

**调优建议**：

- 保守估计：设置较长的等待时间，避免系统过载
- 激进测试：设置较短的等待时间，测试系统极限
- 真实模拟：根据实际用户行为设置等待时间分布

### 2.3 并发控制调优

**原则**：根据系统资源和业务需求调整并发度

```python

class ConcurrentOptimizedUser(HttpUser):
    execution_mode = ExecutionMode.CONCURRENT

    # 保守设置：适合资源有限的系统
    max_concurrent_tasks = 5
    wait_time = 1.0

    # 激进设置：适合高性能系统
    max_concurrent_tasks = 50
    wait_time = 0.1

    # 自适应设置：根据系统负载动态调整
    def get_max_concurrent_tasks(self):
        # 根据时间调整并发度
        import datetime
        hour = datetime.datetime.now().hour
        if 9 <= hour <= 18:  # 高峰期
            return 50
        else:  # 低峰期
            return 20

    max_concurrent_tasks = get_max_concurrent_tasks

```

**调优建议**：

- 从低并发开始：5-10个并发任务
- 逐步增加：每次增加5-10个并发任务
- 监控系统资源：CPU、内存、网络使用率
- 观察响应时间：确保响应时间在可接受范围内

______________________________________________________________________

## 性能优化

### 3.1 异步 I/O 优化

**原则**：充分利用异步 I/O，避免阻塞操作

```python

class AsyncOptimizedUser(HttpUser):
    async def test_multiple_apis(self):
        """使用异步并发调用多个 API"""
        import asyncio

        # 好的实践：使用 asyncio.gather 并发调用
        tasks = [
            self.client.get("/api1"),
            self.client.get("/api2"),
            self.client.get("/api3")
        ]
        responses = await asyncio.gather(*tasks)

        for resp in responses:
            assert resp.status == 200

    # 避免的实践：顺序调用导致性能损失
    async def test_sequential_apis(self):
        # 不推荐：顺序调用
        await self.client.get("/api1")
        await self.client.get("/api2")
        await self.client.get("/api3")

```

### 3.2 连接池优化

**原则**：合理配置连接池，避免连接开销

```python

class ConnectionPoolOptimizedUser(HttpUser):
    async def on_start(self):
        """配置连接池参数"""
        await super().on_start()

        # 配置连接池
        self.client.connector = aiohttp.TCPConnector(
            limit=100,              # 最大连接数
            limit_per_host=50,      # 每个主机的最大连接数
            force_close=False,        # 不强制关闭连接
            enable_cleanup_closed=True  # 清理已关闭的连接
        )

```

**调优建议**：

- 连接池大小：设置为最大并发任务数的1.5-2倍
- 每主机连接数：根据目标服务器性能调整
- 连接复用：启用连接复用，减少连接建立开销

### 3.3 内存管理优化

**原则**：及时清理资源，避免内存泄漏

```python

class MemoryOptimizedUser(HttpUser):
    async def on_start(self):
        """初始化资源"""
        self.cache = {}
        self.db_connection = await self.create_db_connection()

    async def test_api(self):
        """使用缓存减少重复计算"""
        cache_key = "api_data"

        # 检查缓存
        if cache_key in self.cache:
            data = self.cache[cache_key]
        else:
            async with self.client.get("/api") as resp:
                data = await resp.json()

            # 更新缓存
            self.cache[cache_key] = data

            # 限制缓存大小
            if len(self.cache) > 100:
                # 清理最旧的缓存项
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]

    async def on_stop(self):
        """清理资源"""
        # 清理缓存
        if hasattr(self, 'cache'):
            self.cache.clear()

        # 关闭数据库连接
        if hasattr(self, 'db_connection'):
            await self.db_connection.close()

```

**调优建议**：

- 定期清理：在 on_stop 中清理所有资源
- 限制缓存大小：避免缓存占用过多内存
- 使用弱引用：对于大型缓存，考虑使用弱引用

______________________________________________________________________

## 分布式测试最佳实践

### 4.1 Master-Worker 架构设计

**原则**：合理规划 Master 和 Worker 的数量和分布

```python
# Master 节点配置

master_config = {
    'prometheus_port': 8089,
    'expect_workers': 3,  # 期望的 Worker 数量
}

# Worker 节点配置

worker_config = {
    'prometheus_port': 8090,  # 使用不同的端口
    'heartbeat_interval': 5.0,  # 心跳间隔
    'metrics_batch_size': 100,  # 指标批量大小
}

```

**最佳实践**：

- Master 节点：1个，负责协调和监控
- Worker 节点：3-5个，根据测试规模调整
- 网络配置：确保 Master 和 Worker 之间的网络稳定
- 资源分配：每个 Worker 分配足够的资源

______________________________________________________________________

## 监控和调优

### 5.1 关键指标监控

**原则**：监控关键指标，及时发现性能问题

**重要指标**：

1. **响应时间**：

   - 平均响应时间
   - P95、P99 响应时间
   - 响应时间分布

1. **吞吐量**：

   - 每秒请求数（RPS）
   - 峰值吞吐量

1. **错误率**：

   - HTTP 错误率
   - 业务错误率
   - 超时率

1. **资源使用**：

   - CPU 使用率
   - 内存使用量
   - 网络带宽

### 5.2 性能瓶颈分析

**原则**：系统化分析性能瓶颈

**分析步骤**：

1. **识别瓶颈**：

   - 检查响应时间增长趋势
   - 分析错误率变化
   - 观察资源使用情况

1. **定位瓶颈**：

   - CPU 瓶颈：CPU 使用率持续接近100%
   - 内存瓶颈：内存使用量持续增长
   - I/O 瓶颈：磁盘 I/O 或网络 I/O 饱和
   - 数据库瓶颈：数据库查询响应时间长

**提示**: 负载测试是一个持续优化的过程，根据实际业务需求和系统特点不断调整测试策略。
