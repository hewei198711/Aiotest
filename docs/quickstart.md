# AioTest 快速入门指南

欢迎来到 AioTest 快速入门指南！本指南将帮助您在5分钟内快速上手 AioTest 负载测试框架。

## 📋 前置要求

- Python 3.8 或更高版本
- pip 包管理器
- 基本的 Python 编程知识

## 🚀 第一步：安装 AioTest

### 从 PyPI 安装（推荐）

```bash
pip install aiotest
```

### 从源代码安装

```bash
git clone https://github.com/hewei198711/Aiotest.git
cd aiotest
pip install -r requirements.txt
```

## 🎯 第二步：创建第一个测试

### 最简单的 HTTP 测试

您可以直接使用我们提供的完整示例文件：

**使用示例文件**：

```bash
python -m aiotest -f examples/basic.py
```

**示例文件内容**：

`examples/basic.py` 包含了完整的测试示例，包括：
- 多个测试方法（GET、POST、错误处理等）
- 认证请求示例
- 负载形状定义
- 详细的文档和注释

这是一个更加完整和实用的示例，适合作为入门参考。

## 📊 第三步：添加负载控制

### 自定义负载形状

```python
from aiotest import HttpUser, LoadUserShape

class MyUser(HttpUser):
    host = "https://httpbin.org"
    wait_time = 1
    
    async def test_get(self):
        async with self.client.get("/get") as resp:
            assert resp.status == 200

class MyLoadShape(LoadUserShape):
    def tick(self):
        """逐步增加用户数"""
        run_time = self.get_run_time()
        
        if run_time < 30:
            return (10, 2)   # 前30秒：10用户，每秒2个
        elif run_time < 60:
            return (20, 5)   # 30-60秒：20用户，每秒5个
        else:
            return None      # 60秒后停止
```

## 🌐 第四步：分布式测试

### 启动 Master 节点

```bash
python -m aiotest -f my_first_test.py \
    --master --expect-workers 2 \
    --redis-path 127.0.0.1 --redis-port 6379
```

### 启动 Worker 节点

```bash
python -m aiotest -f my_first_test.py \
    --worker \
    --redis-path 127.0.0.1 --redis-port 6379
```

## 📈 第五步：监控测试

### 启动 Prometheus 指标

```bash
python -m aiotest -f my_first_test.py --prometheus-port 8089
```

访问 http://localhost:8089 查看实时指标。

### 使用 Grafana 可视化

1. 安装 Grafana 和 Prometheus
2. 配置 Prometheus 数据源
3. 导入 AioTest 仪表板模板

## 🎮 第六步：使用控制中心

AioTest 提供了 Web 控制中心，方便管理测试：

1. 启动测试后，访问控制中心界面
2. 使用控制中心进行：
   - 暂停/恢复测试/提前结束测试

## 💡 常见使用场景

### 场景1：API 性能测试

```python
from aiotest import HttpUser

class ApiUser(HttpUser):
    host = "https://api.example.com"
    wait_time = (0.5, 2)  # 随机等待0.5-2秒
    
    async def test_list_users(self):
        async with self.client.get("/users") as resp:
            assert resp.status == 200
    
    async def test_create_user(self):
        data = {"name": "Test User", "email": "test@example.com"}
        async with self.client.post("/users", json=data) as resp:
            assert resp.status == 201
```

### 场景2：高并发测试

```python
from aiotest import HttpUser, ExecutionMode, weight

class HighConcurrencyUser(HttpUser):
    host = "https://api.example.com"
    execution_mode = ExecutionMode.CONCURRENT  # 并发执行
    max_concurrent_tasks = 10  # 最大并发任务数
    wait_time = 0.1  # 短等待时间
    
    @weight(5)  # 高权重任务
    async def test_read_api(self):
        async with self.client.get("/data") as resp:
            assert resp.status == 200
    
    @weight(1)  # 低权重任务
    async def test_write_api(self):
        data = {"value": "test"}
        async with self.client.post("/data", json=data) as resp:
            assert resp.status == 200
```

### 场景3：数据库压力测试

```python
from aiotest import User
import asyncio

class DatabaseUser(User):
    wait_time = 0.5
    
    async def on_start(self):
        """初始化数据库连接"""
        import asyncpg
        self.db = await asyncpg.connect("postgresql://user:pass@localhost/db")
    
    async def test_query(self):
        """执行数据库查询"""
        result = await self.db.fetch("SELECT * FROM users LIMIT 10")
        assert len(result) > 0
    
    async def on_stop(self):
        """关闭数据库连接"""
        await self.db.close()
```

## 🔧 进阶功能

### 暂停和恢复测试

```python
# 在运行器中调用暂停/恢复
await runner.pause()   # 暂停测试
await runner.resume()  # 恢复测试
```

### 自定义事件处理

```python
from aiotest import request_metrics

@request_metrics.handler(priority=0)
async def custom_handler(**kwargs):
    metrics = kwargs.get('metrics')
    if metrics:
        print(f"请求: {metrics.method} {metrics.endpoint} - {metrics.duration:.0f}ms")
```

### 分布式锁

```python
from aiotest import redis_client, RedisLock

async def test_with_lock(self):
    async with await RedisLock.with_lock(redis_client, "my_lock", timeout=10) as lock:
        if lock.locked:
            # 执行需要互斥的操作
            pass
```

## 📚 下一步

恭喜您完成了快速入门！接下来您可以：

1. 📖 阅读 [完整文档](README.md)
2. 💡 查看 [最佳实践](BEST_PRACTICES.md)
3. 🎯 探索 [示例代码](../examples/)
4. ❓ 查看 [常见问题](FAQ.md)
5. 🏗️ 了解 [架构设计](ARCHITECTURE.md)

## 🆘 遇到问题？

- 查看 [常见问题](FAQ.md)
- 提交 [GitHub Issue](https://github.com/hewei198711/Aiotest/issues)
- 加入社区讨论

---

**提示**: 本指南涵盖了 AioTest 的核心功能，更多高级功能请参考完整文档。
