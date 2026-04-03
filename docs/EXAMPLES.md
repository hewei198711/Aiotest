# AioTest 示例项目

<!-- markdownlint-disable MD024 -->

本页面介绍了 AioTest 框架提供的各种示例项目，帮助您快速了解和使用 AioTest 进行负载测试。

## 📋 目录

- [基础级示例](#%E5%9F%BA%E7%A1%80%E7%BA%A7%E7%A4%BA%E4%BE%8B)
- [进阶级示例](#%E8%BF%9B%E9%98%B6%E7%BA%A7%E7%A4%BA%E4%BE%8B)
- [高级示例](#%E9%AB%98%E7%BA%A7%E7%A4%BA%E4%BE%8B)
- [标准项目示例](#%E6%A0%87%E5%87%86%E9%A1%B9%E7%9B%AE%E7%A4%BA%E4%BE%8B)
- [负载形状示例](#%E8%B4%9F%E8%BD%BD%E5%BD%A2%E7%8A%B6%E7%A4%BA%E4%BE%8B)

______________________________________________________________________

## 基础级示例

适合初学者，涵盖基本功能和简单场景。

### 1. 基础 HTTP 测试

**文件**: examples/basic.py

**功能**：

- 最简单的 HTTP GET 请求
- 基本的用户类定义
- 简单的负载形状

**适用场景**: 第一次使用 AioTest，了解基本概念

**运行方式**：

```bash

aiotest -f examples/basic.py
```

### 2. 并发执行示例

**文件**: examples/concurrent_example.py

**功能**:

- 并发执行模式
- 任务权重控制
- 最大并发任务数限制
- 高并发场景测试

**适用场景**: 测试高并发 API

**运行方式**：

```bash

aiotest -f examples/concurrent_example.py
```

### 3. 请求验证示例

**文件**: examples/request_verification.py

**功能**:

- 响应状态码验证
- 响应内容验证
- 响应头验证
- JSON 响应解析

**适用场景**: 需要严格验证响应的场景

**运行方式**：

```bash

aiotest -f examples/request_verification.py
```

______________________________________________________________________

## 进阶级示例

适合有一定经验的用户，涵盖中等复杂度的功能。

### 4. 分布式测试

**文件**: examples/distributed_example.py

**功能**:

- Master-Worker 架构
- Redis 协调
- 分布式负载分配
- 节点状态监控

**适用场景**: 大规模负载测试，需要多台机器

**运行方式**：

```bash
# 启动 Master

aiotest -f examples/distributed_example.py --master --expect-workers 2

# 启动 Worker（在另一台机器上）

aiotest -f examples/distributed_example.py --worker
```

### 5. 权重和等待时间

**文件**: examples/weight_and_wait.py

**功能**:

- 用户权重设置
- 任务权重设置
- 多种等待时间类型
- 随机等待时间

**适用场景**: 模拟真实的用户行为

**运行方式**：

```bash

aiotest -f examples/weight_and_wait.py
```

### 6. 事件系统示例

**文件**: examples/events_example.py

**功能**:

- 自定义事件处理器
- 事件钩子使用
- 事件数据收集
- 自定义指标处理

**适用场景**: 需要自定义事件处理的场景

**运行方式**：

```bash

aiotest -f examples/events_example.py
```

______________________________________________________________________

## 高级示例

适合有丰富经验的用户，涵盖复杂场景和高级功能。

### 7. 秒杀场景测试

**文件**: examples/seckill_scenario.py

**功能**:

- 高并发秒杀场景
- 库存管理
- 分布式锁
- 限流控制

**适用场景**: 电商秒杀、抢购等高并发场景

**运行方式**：

```bash

aiotest -f examples/seckill_scenario.py
```

______________________________________________________________________

## 标准项目示例

### demo/ - 完整的负载测试项目示例

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

**详细文档**: 包含完整的部署和使用说明

### 项目结构

AioTest 负载测试项目的文件结构如下：

```text

aiotest_demo/
├── .venv/             # Python虚拟环境
├── logs/              # 测试日志目录
├── provisioning/      # 配置文件目录
│   ├── dashboards/    # Grafana仪表板配置
│   │   ├── Aiotest.json       # AioTest测试仪表板
│   │   ├── dashboards.yml     # 仪表板配置文件
│   │   └── NodeExporter.json  # 节点导出器仪表板
│   └── datasources/   # 数据源配置
│       └── prometheus.yml     # Prometheus数据源配置
├── .gitignore         # Git忽略文件配置
├── aiotestfile.py     # AioTest测试脚本
├── deploy.py          # 代码部署工具
├── docker-compose.yml # Docker Compose配置文件
├── Dockerfile         # Docker镜像构建文件
├── dockerignore       # Docker忽略文件配置
├── prepare_user_data.py # 用户数据准备工具
├── prometheus.yml     # Prometheus监控配置
├── requirements.txt   # Python依赖包配置
├── userinfo.csv    # 测试用户数据

```

**文件说明**：

- **aiotestfile.py**：核心测试脚本，定义测试场景和流程

- **deploy.py**：自动将代码部署到远程服务器

- **prepare_user_data.py**：从CSV文件导入用户数据，执行真实登录并存储到Redis

- **docker-compose.yml**：定义容器服务配置，包括master、worker和监控服务

- **Dockerfile**：构建AioTest容器镜像

- **prometheus.yml**：Prometheus监控配置

- **userinfo.csv**：测试用户数据

- **provisioning/**：监控配置目录

  - **dashboards/**：Grafana仪表板配置

  - **Aiotest.json**：AioTest测试专用仪表板，展示测试性能指标

  - **NodeExporter.json**：服务器节点监控仪表板，展示系统资源使用情况

  - **datasources/**：数据源配置

  - **prometheus.yml**：Prometheus数据源配置，连接到Prometheus服务器

### 环境准备

#### 硬件环境

- 5台Linux主机，每台配置：4核心8G内存
- IP地址：122.16.40.21, 122.16.40.22, 122.16.40.23, 122.16.40.24, 122.16.40.25

#### 软件环境

- Docker 和 Docker Compose
- Python 3.12+
- Git

### 操作步骤

#### 1. 代码准备

在本地开发环境中，确保代码仓库已更新到最新版本：

```bash

git pull
```

#### 2. 代码分发

使用 `deploy.py` 脚本将最新测试代码分发到各台主机：

```bash
# 在本地项目目录执行

python deploy.py
```

#### 3. 部署监控服务（仅122.16.40.25）

在122.16.40.25主机上启动监控服务：

```bash
# 登录到122.16.40.25

ssh root@122.16.40.25

# 进入项目目录

cd aiotest_demo

# 启动监控服务

docker compose up -d prometheus grafana redis cadvisor
```

#### 4. 部署节点导出器（所有主机）

在所有5台主机上启动 node-exporter 服务：

```bash
# 登录到每台主机

ssh root@<主机IP>

# 进入项目目录

cd aiotest_demo

# 启动 node-exporter

docker compose up -d node-exporter
```

#### 5. 准备测试数据

在工作电脑（Windows 10系统）上执行 `prepare_user_data.py` 脚本，将用户登录数据放入Redis：

```bash
# 在工作电脑的项目目录执行

python prepare_user_data.py
```

**注意**：

- 确保工作电脑已安装Python 3环境
- 确保工作电脑能够连接到122.16.40.25的Redis服务
- 脚本会自动将生成的用户数据写入到122.16.40.25:6379的Redis服务中

#### 6. 启动测试服务

##### 6.1 在122.16.40.24启动 master 和 worker 服务

```bash
# 登录到122.16.40.24

ssh root@122.16.40.24

# 进入项目目录

cd aiotest_demo

# 启动 master 服务

docker compose up -d master

# 启动 3 个 worker 服务

docker compose up -d --scale worker=3
```

##### 6.2 在其他主机启动 worker 服务

在122.16.40.21、122.16.40.22、122.16.40.23主机上分别启动4个 worker 服务：

```bash
# 登录到目标主机

ssh root@<主机IP>

# 进入项目目录

cd aiotest_demo

# 启动 4 个 worker 服务

docker compose up -d --scale worker=4
```

#### 7. 访问控制界面

通过浏览器访问122.16.40.24:8089，打开AioTest控制Web页面：

- 可以查看测试状态
- 可以暂停测试
- 可以提前结束测试

#### 8. 监控测试性能

- **Prometheus**：访问 122.16.40.25:9090，查看原始监控数据
- **Grafana**：访问 122.16.40.25:3000，查看可视化监控面板

### 停止测试

#### 停止所有服务

在每台主机上执行：

```bash
# 进入项目目录

cd aiotest_demo

# 停止所有服务

docker compose down
```

#### 仅停止测试服务（保留监控服务）

```bash
# 停止并删除 master 和 worker 服务

docker compose down master worker
```

### 常见问题处理

1. **Redis 连接失败**：检查 redis 服务是否正常运行，密码是否正确
1. **Worker 无法连接到 Master**：检查网络连接，确保 Master 服务已启动
1. **监控数据不显示**：检查 node-exporter 是否正常运行，Prometheus 配置是否正确
1. **测试执行缓慢**：检查系统资源使用情况，可能需要调整并发数

### 测试结果分析

1. 通过 Grafana 面板查看性能指标
1. 检查 AioTest 控制界面的测试报告
1. 分析 Prometheus 中的详细监控数据

### 关键代码和重要提示

#### 1. deploy.py - 代码部署工具

**功能**：自动将本地代码部署到远程服务器

**关键配置**：

```python
# Linux主机列表

HOSTS = [
    "122.16.40.21",
    "122.16.40.22",
    "122.16.40.23",
    "122.16.40.24",
    "122.16.40.25"
]

# 要排除的文件/目录

EXCLUDE_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    ".venv",
    "tools",
    "logs"
]

# linux主机用户名和密码

USERNAME = "root"
PASSWORD = "ligeit"

```

**重要提示**：

- 脚本会自动修改远程目录的文件权限为 UID 1000:1000（aiotest 用户），确保容器能够正常启动
- 支持多台服务器批量部署
- 自动排除不必要的文件和目录

#### 2. prepare_user_data.py - 用户数据准备工具

**功能**：从CSV文件导入用户数据，执行真实登录过程，获取token并存储到Redis

**关键配置**：

```python
# Redis 连接配置

REDIS_PATH = "122.16.40.25"
REDIS_PORT = 6379
REDIS_PASSWORD = "test123456"

# CSV 文件路径

CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "userinfo_85.csv")

# 批量处理配置

BATCH_SIZE = 100  # 每批处理的用户数量
WORKER_COUNT = 50  # 并发协程数

```

**重要提示**：

- 需要在工作电脑（Windows 10）上执行，依赖Python 3环境
- 支持批量处理大批量用户（10万+绰绰有余）
- 与 aiotest/distributed_example.py 使用相同的 Redis 键结构

#### 3. Dockerfile - 容器镜像构建

**功能**：构建AioTest容器镜像

**关键配置**：

```dockerfile
# 第一阶段：构建环境

FROM python:3.12-slim AS builder

# 第二阶段：运行环境

FROM python:3.12-slim

# 创建非root用户

RUN useradd -m -u 1000 aiotest  # 创建用户aiotest，UID为1000

# 设置工作目录

WORKDIR /app

# 切换到非root用户

USER aiotest
```

**重要提示**：

- 使用多阶段构建，减少镜像大小
- 创建非root用户aiotest（UID:1000），提高容器安全性
- 暴露8089端口用于Prometheus指标和Web控制界面

#### 4. docker-compose.yml - 服务配置

**功能**：定义master、worker和监控服务的配置

**关键配置**：

```yaml
# master服务

master:
    build: .
    image: aiotest:latest
    ports:
  -- "8089:8089"
    volumes:
  -- .:/app
    pid: host  # 允许访问宿主机的进程信息
    user: "1000:1000"  # 使用aiotest用户(UID:1000)
    environment:
  -- TZ=Asia/Shanghai
    command: aiotest -f aiotestfile.py --master --expect-workers 1 --redis-path 122.16.40.25 --redis-port 6379 --redis-password test123456


# worker服务

worker:
    build: .
    image: aiotest:latest
    volumes:
  -- .:/app
    pid: host  # 允许访问宿主机的进程信息
    user: "1000:1000"  # 使用aiotest用户(UID:1000)
    environment:
  -- TZ=Asia/Shanghai
    command: aiotest -f aiotestfile.py --worker --redis-path 122.16.40.25 --redis-port 6379 --redis-password test123456 --loglevel WARNING
    deploy:
        replicas: 4

```

**重要提示**：

- 使用build指令自动构建镜像
- 支持使用 `--scale` 参数扩展worker数量
- 监控服务（prometheus、grafana、redis、cadvisor）只在122.16.40.25上运行
- node-exporter在所有主机上运行，用于收集系统指标

### 注意事项

1. 测试前确保所有服务正常启动
1. 测试过程中避免在主机上执行其他高负载操作
1. 测试完成后及时清理资源，避免占用系统资源
1. 定期备份测试数据和监控结果
1. 确保工作电脑能够连接到122.16.40.25的Redis服务
1. 首次运行deploy.py时，需要确认主机密钥
1. 修改权限需要sudo权限，确保root用户能够执行sudo命令

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

______________________________________________________________________

## 负载形状示例

`load_shape/` 目录包含各种负载形状的示例：

### peak_load_shape.py

**功能**: 模拟峰值负载
**适用场景**: 测试系统在峰值负载下的表现

### random_load_shape.py

**功能**: 模拟随机负载
**适用场景**: 测试系统在不稳定负载下的表现

### step_load_shape.py

**功能**: 模拟阶梯式负载
**适用场景**: 测试系统在不同负载级别下的表现

### wave_load_shape.py

**功能**: 模拟波浪式负载
**适用场景**: 测试系统在周期性负载下的表现

______________________________________________________________________

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

______________________________________________________________________

## 自定义示例

### 创建自己的测试

1. **复制基础示例**:

   ```bash

   cp examples/basic.py my_test.py
   ```

1. **修改用户类**:

   ```python

   from aiotest import HttpUser

   class MyUser(HttpUser):
       host = "https://your-api.com"
       wait_time = 1

       async def test_my_api(self):
           async with self.client.get("/my-endpoint") as resp:
               assert resp.status == 200

   ```

1. **运行自定义测试**:

   ```bash

   aiotest -f my_test.py
   ```

______________________________________________________________________

## 📞 获取帮助

如果您在运行示例时遇到问题：

1. 查看 [快速入门指南](quickstart.md)
1. 参考 [API 参考](API_REFERENCE.md)
1. 查看 [常见问题](FAQ.md)
1. 提交 [GitHub Issue](https://github.com/hewei198711/Aiotest/issues)

______________________________________________________________________

**提示**: 建议从基础级示例开始，逐步学习进阶级和高级示例。对于生产环境部署，建议参考 demo 项目作为标准模板。
