# AioTest 常见问题解答

本文档收集了 AioTest 使用过程中的常见问题和解决方案。

## 📋 目录

- [安装问题](#安装问题)
- [配置问题](#配置问题)
- [运行问题](#运行问题)
- [性能问题](#性能问题)
- [分布式测试问题](#分布式测试问题)
- [监控和日志问题](#监控和日志问题)

---

## 安装问题

### Q1: 安装失败，提示依赖冲突

**问题**: 执行 `pip install aiotest` 时出现依赖冲突错误。

**解决方案**:
1. 使用虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
pip install aiotest
```

2. 更新 pip 和 setuptools：
```bash
pip install --upgrade pip setuptools
```

3. 使用国内镜像源：
```bash
pip install aiotest -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: Windows 下安装失败

**问题**: Windows 系统下安装 aiotest 时出现编译错误。

**解决方案**:
1. 确保安装了 Microsoft Visual C++ Build Tools
2. 使用预编译的 wheel 包：
```bash
pip install aiotest --only-binary :all:
```

3. 使用 Anaconda 或 Miniconda 环境

### Q3: Python 版本不兼容

**问题**: 提示 Python 版本过低。

**解决方案**:
- AioTest 需要 Python 3.8 或更高版本
- 升级 Python：
```bash
# Windows
# 下载并安装最新版 Python：https://www.python.org/downloads/

# Linux/Mac
brew install python3  # Mac
sudo apt-get install python3.8  # Ubuntu
```

---

## 配置问题

### Q4: 如何配置 Redis 连接

**问题**: 不清楚如何配置 Redis 连接参数。

**解决方案**:
```bash
# 命令行参数
aiotest -f test.py \
    --redis-path 127.0.0.1 \
    --redis-port 6379 \
    --redis-password "your_password"
```

或在代码中配置：
```python
from aiotest import RedisConnection

# 全局 Redis 连接
redis_client = None
redis_connection = None

async def initialize_redis():
    """初始化Redis连接"""
    global redis_client, redis_connection
    if redis_client is None:
        if redis_connection is None:
            redis_connection = RedisConnection()
        redis_client = await redis_connection.get_client(
            path="127.0.0.1",
            port=6379,
            password="your_password"
        )
    return redis_client

# 使用示例
async def test_with_redis():
    redis = await initialize_redis()
    # 使用 redis 客户端
```

### Q5: 如何设置 Prometheus 端口

**问题**: 需要修改 Prometheus 指标服务的默认端口。

**解决方案**:
```bash
# 使用 --prometheus-port 参数
aiotest -f test.py --prometheus-port 9090
```

访问 http://localhost:9090/metrics 查看指标。

### Q6: 如何配置日志级别

**问题**: 需要调整日志输出详细程度。

**解决方案**:
```bash
# 使用 --loglevel 参数
aiotest -f test.py --loglevel DEBUG
```

支持的日志级别：
- `DEBUG`: 详细的调试信息
- `INFO`: 一般信息（默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

---

## 运行问题

### Q7: 测试启动失败，提示端口被占用

**问题**: 启动测试时提示端口已被占用。

**解决方案**:
1. 查找占用端口的进程：
```bash
# Windows
netstat -ano | findstr :8089

# Linux/Mac
lsof -i :8089
```

2. 终止进程或更换端口：
```bash
# 更换 Prometheus 端口
aiotest -f test.py --prometheus-port 9090
```

### Q8: 用户任务不执行

**问题**: 用户启动后，任务函数没有被执行。

**解决方案**:
1. 确保任务函数命名正确：
```python
# 正确：以 test_ 开头或 _test 结尾
async def test_my_task(self):
    pass

async def my_task_test(self):
    pass

# 错误：不符合命名规范
async def my_task(self):
    pass
```

2. 检查执行模式：
```python
class MyUser(HttpUser):
    execution_mode = ExecutionMode.SEQUENTIAL  # 系统默认执行模式为顺序执行
```

### Q9: HTTP 请求超时

**问题**: HTTP 请求经常超时。

**解决方案**:
1. 增加超时时间：
```python
class MyUser(HttpUser):
    timeout = 60  # 增加到60秒
```

2. 检查网络连接和目标服务器状态
3. 使用重试机制：
```python
class MyUser(HttpUser):
    max_retries = 5  # 增加重试次数
```

---

## 性能问题

### Q10: 测试性能不佳，响应时间过长

**问题**: 测试结果显示响应时间比预期长很多。

**解决方案**:
1. 优化用户数量：
```python
class MyLoadShape(LoadUserShape):
    def tick(self):
        # 从小规模开始，逐步增加
        run_time = self.get_run_time()
        if run_time < 30:
            return (10, 2)
        elif run_time < 60:
            return (50, 5)
        else:
            return (100, 10)
```

2. 调整等待时间：
```python
class MyUser(HttpUser):
    wait_time = (0.1, 0.5)  # 减少等待时间
```

3. 使用并发执行模式：
```python
class MyUser(HttpUser):
    execution_mode = ExecutionMode.CONCURRENT
    max_concurrent_tasks = 10
```

### Q11: 内存占用过高

**问题**: 测试运行时内存占用持续增长。

**解决方案**:
1. 定期清理非活跃用户：
```python
# 在运行器中定期调用
await user_manager.cleanup_inactive_users()
```

2. 限制最大用户数：
```python
class MyLoadShape(LoadUserShape):
    def tick(self):
        # 限制最大用户数
        max_users = 1000
        current_users = self.get_run_time() * 10
        return (min(current_users, max_users), 5)
```

3. 检查是否有内存泄漏：
```python
async def on_stop(self):
    # 调用父类的 on_stop 方法
    await super().on_stop()
    
    # 清理数据库连接
    if hasattr(self, 'db'):
        try:
            await self.db.close()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")
    
    # 清理Redis连接
    if hasattr(self, 'redis'):
        try:
            await self.redis.close()
        except Exception as e:
            logger.error(f"关闭Redis连接失败: {e}")
    
    # 清理临时文件
    if hasattr(self, 'temp_files'):
        for file_path in self.temp_files:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"删除临时文件失败 {file_path}: {e}")
```

### Q12: CPU 使用率过高

**问题**: 测试运行时 CPU 使用率达到 100%。

**解决方案**:
1. 增加任务等待时间：
```python
class MyUser(HttpUser):
    wait_time = 1.0  # 增加等待时间
```

2. 减少并发任务数：
```python
class MyUser(HttpUser):
    max_concurrent_tasks = 5  # 减少并发数
```

3. 使用异步 I/O 优化：
```python
# 避免同步阻塞操作
async def test_api(self):
    # 使用异步 HTTP 客户端
    async with self.client.get("/api") as resp:
        data = await resp.json()
```

---

## 分布式测试问题

### Q13: Worker 无法连接到 Master

**问题**: Worker 节点启动后无法连接到 Master。

**解决方案**:
1. 检查 Redis 连接：
```bash
# 测试 Redis 连接
redis-cli -h 127.0.0.1 -p 6379 -a "your_password" ping
```

2. 确保网络连通性：
```bash
# 测试网络连接
telnet master_ip 6379
```

3. 检查防火墙设置：
```bash
# 确保 Redis 端口开放
# Linux
sudo ufw allow 6379/tcp

# Windows
# 在防火墙中添加入站规则
```

### Q14: 分布式测试数据不同步

**问题**: Master 和 Worker 之间的数据不同步。

**解决方案**:
1. 确保使用相同的 Redis 实例：
```bash
# Master 和 Worker 使用相同的 Redis 配置
--redis-path 127.0.0.1 --redis-port 6379 --redis-password "same_password"
```

2. 检查 Redis 持久化配置：
```bash
# redis.conf
appendonly yes
save 900 1
save 300 10
```

3. 使用分布式锁保护关键操作：
```python
from aiotest import redis_client, RedisLock

async def test_with_lock(self):
    async with await RedisLock.with_lock(redis_client, "critical_section", timeout=10) as lock:
        if lock.locked:
            # 执行关键操作
            pass
```

### Q15: Worker 节点频繁掉线

**问题**: Worker 节点经常显示为丢失状态。

**解决方案**:

1. 检查网络稳定性：
```bash
# 使用 ping 测试网络
ping -t master_ip
```


---

## 监控和日志问题

### Q16: Prometheus 指标不显示

**问题**: Prometheus 端口可以访问，但指标数据为空。

**解决方案**:
1. 确保指标收集器已启动：
```python
# 检查 initialize() 是否被调用
await runner.initialize()
```

2. 检查指标配置：
```python
# 确保配置了正确的指标参数
config = {
    'prometheus_port': 8089,
    'metrics_collection_interval': 5.0,
    'metrics_batch_size': 100,
    'metrics_flush_interval': 1.0,
    'metrics_buffer_size': 10000
}
```

3. 访问正确的端点：
```bash
# 访问 /metrics 端点
curl http://localhost:8089/metrics
```

### Q17: 日志文件过大

**问题**: 日志文件增长过快，占用大量磁盘空间。

**解决方案**:

1. 调整日志级别：
```bash
# 使用 WARNING 或 ERROR 级别减少日志量
aiotest -f test.py --loglevel WARNING
```



---

## 其他常见问题

### Q19: 如何暂停和恢复测试

**问题**: 需要在测试运行过程中暂停和恢复。

**解决方案**:



```python
# 使用运行器的 pause 和 resume 方法
await runner.pause()   # 暂停测试
await runner.resume()  # 恢复测试
```

或通过控制中心界面操作：
   
   - 启动测试后，打开浏览器访问 http://localhost:8089 （默认端口）
   - 您将看到 AioTest 的 Web 控制界面

### Q20: 如何自定义负载形状

**问题**: 需要实现特定的负载变化模式。

**解决方案**:
```python
from aiotest import LoadUserShape

class CustomLoadShape(LoadUserShape):
    def tick(self):
        run_time = self.get_run_time()
        
        # 实现自定义的负载逻辑
        if run_time < 60:
            return (10, 2)   # 阶段1
        elif run_time < 120:
            return (30, 5)   # 阶段2
        elif run_time < 180:
            return (50, 10)  # 阶段3
        else:
            return None      # 结束
```

---

## 📞 获取更多帮助

如果您的问题不在此列表中：

1. 查看 [完整文档](README.md)
2. 搜索 [GitHub Issues](https://github.com/hewei198711/Aiotest/issues)
3. 提交新的 [Issue](https://github.com/hewei198711/Aiotest/issues/new)


---

**提示**: 本文档持续更新，欢迎贡献您遇到的问题和解决方案！
