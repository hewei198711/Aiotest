# AioTest 示例代码

本目录包含了 AioTest 框架的各种示例代码，按难度和场景分类。

## 📋 目录

- [基础级示例](#基础级示例)
- [进阶级示例](#进阶级示例)
- [高级示例](#高级示例)
- [标准项目示例](#标准项目示例)
- [按场景分类](#按场景分类)

---

## 基础级示例

适合初学者，涵盖基本功能和简单场景。

### 1. 基础 HTTP 测试

**文件**: [basic.py](basic.py)

**功能**:

- 最简单的 HTTP GET 请求
- 基本的用户类定义
- 简单的负载形状

**适用场景**: 第一次使用 AioTest，了解基本概念

**运行方式**:

```bash
aiotest -f examples/basic.py
```

### 2. 简单 HTTP 测试

**文件**: [simple_http_test.py](simple_http_test.py)

**功能**:

- HTTP GET 和 POST 请求
- 基本的断言验证
- 固定等待时间

**适用场景**: 测试简单的 HTTP API

**运行方式**:

```bash
aiotest -f examples/simple_http_test.py
```

### 3. 基础负载形状

**文件**: [basic_load_shape.py](basic_load_shape.py)

**功能**:

- 阶梯式负载增长
- 固定用户数和速率
- 基本的负载形状实现

**适用场景**: 了解负载形状的基本概念

**运行方式**:

```bash
aiotest -f examples/basic_load_shape.py
```

---

## 进阶级示例

适合有一定经验的用户，涵盖中等复杂度的功能。

### 4. API 性能测试

**文件**: [api_performance_test.py](api_performance_test.py)

**功能**:

- 多种 HTTP 方法（GET、POST、PUT、DELETE）
- 请求参数和响应验证
- 自定义负载形状
- 指标收集和监控

**适用场景**: 测试 RESTful API 的性能

**运行方式**:

```bash
aiotest -f examples/api_performance_test.py --prometheus-port 8089
```

### 5. 并发执行模式

**文件**: [concurrent_example.py](concurrent_example.py)

**功能**:

- 并发执行模式
- 任务权重控制
- 最大并发任务数限制
- 高并发场景测试

**适用场景**: 测试高并发 API

**运行方式**:

```bash
aiotest -f examples/concurrent_example.py
```

### 6. 权重和等待时间

**文件**: [weight_and_wait.py](weight_and_wait.py)

**功能**:

- 用户权重设置
- 任务权重设置
- 多种等待时间类型
- 随机等待时间

**适用场景**: 模拟真实的用户行为

**运行方式**:

```bash
aiotest -f examples/weight_and_wait.py
```

### 7. 事件系统示例

**文件**: [events_example.py](events_example.py)

**功能**:

- 自定义事件处理器
- 事件钩子使用
- 事件数据收集
- 自定义指标处理

**适用场景**: 需要自定义事件处理的场景

**运行方式**:

```bash
aiotest -f examples/events_example.py
```

### 8. 请求验证示例

**文件**: [request_verification.py](request_verification.py)

**功能**:

- 响应状态码验证
- 响应内容验证
- 响应头验证
- JSON 响应解析

**适用场景**: 需要严格验证响应的场景

**运行方式**:

```bash
aiotest -f examples/request_verification.py
```

---

## 高级示例

适合有丰富经验的用户，涵盖复杂场景和高级功能。

### 9. 分布式测试

**文件**: [distributed_example.py](distributed_example.py)

**功能**:

- Master-Worker 架构
- Redis 协调
- 分布式负载分配
- 节点状态监控

**适用场景**: 大规模负载测试，需要多台机器

**运行方式**:

```bash
# 启动 Master
aiotest -f examples/distributed_example.py --master --expect-workers 2

# 启动 Worker（在另一台机器上）
aiotest -f examples/distributed_example.py --worker
```

### 10. 数据库性能测试

**文件**: [database_performance_test.py](database_performance_test.py)

**功能**:

- 数据库连接管理
- 数据库查询测试
- 事务处理
- 连接池优化

**适用场景**: 测试数据库性能

**运行方式**:

```bash
aiotest -f examples/database_performance_test.py
```

### 11. 微服务测试

**文件**: [microservices_test.py](microservices_test.py)

**功能**:

- 多个微服务调用
- 服务间依赖测试
- 分布式事务
- 服务发现模拟

**适用场景**: 测试微服务架构

**运行方式**:

```bash
aiotest -f examples/microservices_test.py
```

### 12. 秒杀场景测试

**文件**: [seckill_scenario.py](seckill_scenario.py)

**功能**:

- 高并发秒杀场景
- 库存管理
- 分布式锁
- 限流控制

**适用场景**: 电商秒杀、抢购等高并发场景

**运行方式**:

```bash
aiotest -f examples/seckill_scenario.py
```

### 13. 暂停恢复测试

**文件**: [pause_resume_test.py](pause_resume_test.py)

**功能**:

- 测试暂停功能
- 测试恢复功能
- 状态转换验证
- 控制中心集成

**适用场景**: 需要暂停和恢复测试的场景

**运行方式**:

```bash
aiotest -f examples/pause_resume_test.py
```

---

## 标准项目示例

### [demo/](demo/) - 完整的负载测试项目示例

**功能**:

- 完整的负载测试项目结构
- Docker 容器化部署
- Prometheus 监控集成
- Grafana 可视化面板
- 一键部署脚本

**适用场景**:

- 作为标准的负载测试项目模板
- 快速搭建完整的负载测试环境
- 学习如何集成监控和可视化

**详细文档**: [TEST_DEMO.md](demo/TEST_DEMO.md) - 包含完整的部署和使用说明

**目录结构**:

```text
demo/
├── provisioning/           # 监控配置
│   ├── dashboards/         # Grafana 面板
│   └── datasources/        # Prometheus 数据源
├── aiotestfile.py          # 测试脚本
├── deploy.py               # 部署脚本
├── docker-compose.yml      # Docker 配置
├── Dockerfile              # Docker 镜像构建
├── prometheus.yml          # Prometheus 配置
├── requirements.txt        # 依赖包
└── TEST_DEMO.md            # 测试说明
```

**运行方式**:

```bash
# 进入 demo 目录
cd examples/demo

# 一键部署（启动所有服务）
python deploy.py

# 或手动启动
docker-compose up -d
```

**监控访问**:

- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (默认用户名/密码: admin/admin)

---

## 按场景分类

### API 测试

- [basic.py](basic.py) - 基础 API 测试
- [api_performance_test.py](api_performance_test.py) - API 性能测试
- [request_verification.py](request_verification.py) - 请求验证

### 负载测试

- [basic_load_shape.py](basic_load_shape.py) - 基础负载形状
- [api_performance_test.py](api_performance_test.py) - 负载性能测试
- [pause_resume_test.py](pause_resume_test.py) - 暂停恢复测试

### 分布式测试

- [distributed_example.py](distributed_example.py) - 分布式测试
- [microservices_test.py](microservices_test.py) - 微服务测试

### 高并发测试

- [concurrent_example.py](concurrent_example.py) - 并发执行
- [seckill_scenario.py](seckill_scenario.py) - 秒杀场景

### 功能测试

- [events_example.py](events_example.py) - 事件系统
- [weight_and_wait.py](weight_and_wait.py) - 权重和等待时间

---

## 负载形状示例

`load_shape/` 目录包含各种负载形状的示例：

### [peak_load_shape.py](load_shape/peak_load_shape.py)

**功能**: 模拟峰值负载
**适用场景**: 测试系统在峰值负载下的表现

### [random_load_shape.py](load_shape/random_load_shape.py)

**功能**: 模拟随机负载
**适用场景**: 测试系统在不稳定负载下的表现

### [step_load_shape.py](load_shape/step_load_shape.py)

**功能**: 模拟阶梯式负载
**适用场景**: 测试系统在不同负载级别下的表现

### [wave_load_shape.py](load_shape/wave_load_shape.py)

**功能**: 模拟波浪式负载
**适用场景**: 测试系统在周期性负载下的表现

---

## 运行示例

### 基础运行

```bash
# 运行基础示例
aiotest -f examples/basic.py

# 指定日志级别
aiotest -f examples/basic.py --loglevel DEBUG

# 指定日志文件
aiotest -f examples/basic.py --logfile test.log
```

### 分布式运行

```bash
# 准备用户数据
python examples/prepare_user_data.py

# 启动 Master
aiotest -f examples/distributed_example.py \
    --master --expect-workers 2 \
    --redis-path 127.0.0.1 --redis-port 6379

# 启动 Worker
aiotest -f examples/distributed_example.py \
    --worker \
    --redis-path 127.0.0.1 --redis-port 6379
```

### 监控运行

```bash
# 启动 Prometheus 指标
aiotest -f examples/basic.py --prometheus-port 8089

# 访问 http://localhost:8089/metrics 查看指标
```

---

## 自定义示例

### 创建自己的测试

1. **复制基础示例**:

    ```bash
    cp examples/basic.py my_test.py
    ```

2. **修改用户类**:

    ```python
    from aiotest import HttpUser

    class MyUser(HttpUser):
        host = "https://your-api.com"
        wait_time = 1

        async def test_my_api(self):
            async with self.client.get("/my-endpoint") as resp:
                assert resp.status == 200
    ```

3. **运行自定义测试**:

    ```bash
    aiotest -f my_test.py
    ```

---

## 📞 获取帮助

如果您在运行示例时遇到问题：

1. 查看 [快速入门指南](../docs/QUICKSTART.md)
2. 参考 [API 参考](../docs/API_REFERENCE.md)
3. 查看 [常见问题](../docs/FAQ.md)
4. 提交 [GitHub Issue](https://github.com/hewei198711/Aiotest/issues)

---

**提示**: 建议从基础级示例开始，逐步学习进阶级和高级示例。
