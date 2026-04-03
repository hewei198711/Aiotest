# AioTest 负载测试操作指导

## 项目结构

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

## 环境准备

### 硬件环境

- 5台Linux主机，每台配置：4核心8G内存
- IP地址：122.16.40.21, 122.16.40.22, 122.16.40.23, 122.16.40.24, 122.16.40.25

### 软件环境

- Docker 和 Docker Compose
- Python 3.12+
- Git

## 操作步骤

### 1. 代码准备

在本地开发环境中，确保代码仓库已更新到最新版本：

```bash
git pull
```

### 2. 代码分发

使用 `deploy.py` 脚本将最新测试代码分发到各台主机：

```bash
# 在本地项目目录执行
python deploy.py
```

### 3. 部署监控服务（仅122.16.40.25）

在122.16.40.25主机上启动监控服务：

```bash
# 登录到122.16.40.25
ssh root@122.16.40.25

# 进入项目目录
cd aiotest_demo

# 启动监控服务
docker compose up -d prometheus grafana redis cadvisor
```

### 4. 部署节点导出器（所有主机）

在所有5台主机上启动 node-exporter 服务：

```bash
# 登录到每台主机
ssh root@<主机IP>

# 进入项目目录
cd aiotest_demo

# 启动 node-exporter
docker compose up -d node-exporter
```

### 5. 准备测试数据

在工作电脑（Windows 10系统）上执行 `prepare_user_data.py` 脚本，将用户登录数据放入Redis：

```bash
# 在工作电脑的项目目录执行
python prepare_user_data.py
```

**注意**：

- 确保工作电脑已安装Python 3环境
- 确保工作电脑能够连接到122.16.40.25的Redis服务
- 脚本会自动将生成的用户数据写入到122.16.40.25:6379的Redis服务中

### 6. 启动测试服务

#### 6.1 在122.16.40.24启动 master 和 worker 服务

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

#### 6.2 在其他主机启动 worker 服务

在122.16.40.21、122.16.40.22、122.16.40.23主机上分别启动4个 worker 服务：

```bash
# 登录到目标主机
ssh root@<主机IP>

# 进入项目目录
cd aiotest_demo

# 启动 4 个 worker 服务
docker compose up -d --scale worker=4
```

### 7. 访问控制界面

通过浏览器访问122.16.40.24:8089，打开AioTest控制Web页面：

- 可以查看测试状态
- 可以暂停测试
- 可以提前结束测试

### 8. 监控测试性能

- **Prometheus**：访问 122.16.40.25:9090，查看原始监控数据
- **Grafana**：访问 122.16.40.25:3000，查看可视化监控面板

## 停止测试

### 停止所有服务

在每台主机上执行：

```bash
# 进入项目目录
cd aiotest_demo

# 停止所有服务
docker compose down
```

### 仅停止测试服务（保留监控服务）

```bash
# 停止并删除 master 和 worker 服务
docker compose down master worker
```

## 常见问题处理

1. **Redis 连接失败**：检查 redis 服务是否正常运行，密码是否正确
1. **Worker 无法连接到 Master**：检查网络连接，确保 Master 服务已启动
1. **监控数据不显示**：检查 node-exporter 是否正常运行，Prometheus 配置是否正确
1. **测试执行缓慢**：检查系统资源使用情况，可能需要调整并发数

## 测试结果分析

1. 通过 Grafana 面板查看性能指标
1. 检查 AioTest 控制界面的测试报告
1. 分析 Prometheus 中的详细监控数据

## 关键代码和重要提示

### 1. deploy.py - 代码部署工具

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

### 2. prepare_user_data.py - 用户数据准备工具

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

### 3. Dockerfile - 容器镜像构建

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

### 4. docker-compose.yml - 服务配置

**功能**：定义master、worker和监控服务的配置

**关键配置**：

```yaml
# master服务
master:
    build: .
    image: aiotest:latest
    ports:
        - "8089:8089"
    volumes:
        - .:/app
    pid: host  # 允许访问宿主机的进程信息
    user: "1000:1000"  # 使用aiotest用户(UID:1000)
    environment:
        - TZ=Asia/Shanghai
    command: aiotest -f aiotestfile.py --master --expect-workers 1 --redis-path 122.16.40.25 --redis-port 6379 --redis-password test123456


# worker服务
worker:
    build: .
    image: aiotest:latest
    volumes:
        - .:/app
    pid: host  # 允许访问宿主机的进程信息
    user: "1000:1000"  # 使用aiotest用户(UID:1000)
    environment:
        - TZ=Asia/Shanghai
    command: aiotest -f aiotestfile.py --worker --redis-path 122.16.40.25 --redis-port 6379 --redis-password test123456 --loglevel WARNING
    deploy:
        replicas: 4
```

**重要提示**：

- 使用build指令自动构建镜像
- 支持使用 `--scale` 参数扩展worker数量
- 监控服务（prometheus、grafana、redis、cadvisor）只在122.16.40.25上运行
- node-exporter在所有主机上运行，用于收集系统指标

## 注意事项

1. 测试前确保所有服务正常启动
1. 测试过程中避免在主机上执行其他高负载操作
1. 测试完成后及时清理资源，避免占用系统资源
1. 定期备份测试数据和监控结果
1. 确保工作电脑能够连接到122.16.40.25的Redis服务
1. 首次运行deploy.py时，需要确认主机密钥
1. 修改权限需要sudo权限，确保root用户能够执行sudo命令
