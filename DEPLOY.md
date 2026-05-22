# 视频压缩工具 — Docker 部署指南

## 适用设备

绿联 NAS 4800（UGOS Pro / Debian），同样适用于其他支持 Docker 的 NAS 或 Linux 服务器。

## 前置条件

- NAS 已开启 SSH（在 UGOS 设置中启用）
- NAS 已安装 Docker / Docker Compose（UGOS 应用中心安装）

## 硬件加速说明

UGREEN NAS 4800 搭载 Intel N100/N150 处理器，集成 Intel UHD Graphics，支持 **Intel QSV（Quick Sync Video）** 硬件加速。启用后压缩速度提升 5-10 倍。

- 软件编码：CPU 密集，速度慢但兼容性最好
- QSV 硬件加速：需要将 `/dev/dri` 设备透传给容器（见下方配置）

---

## 方式一：SSH + Docker Compose（推荐）

### 1. 上传项目到 NAS

```bash
# 在 NAS 上创建目录
mkdir -p /volume1/docker/video-compressor

# 从本机将项目上传到 NAS（在本机执行）
scp -r video-compressor/*你的NAS用户名@你的NAS IP:/volume1/docker/video-compressor/
```

### 2. 启动服务

```bash
# SSH 进入 NAS
ssh 你的NAS用户名@你的NAS_IP

# 进入目录
cd /volume1/docker/video-compressor

# 启动（CPU 软件编码）
docker compose up -d

# 或者启用 Intel QSV 硬件加速：
# 先编辑 docker-compose.yml，取消 devices 部分的注释，然后：
docker compose up -d
```

### 3. 验证

浏览器访问 `http://你的NAS_IP:5050`，上传一个视频测试。

---

## 方式二：UGOS Docker 图形界面

### 1. 上传项目文件

通过 SMB/文件管理将 `video-compressor` 文件夹放到 NAS 上，例如 `/volume1/docker/video-compressor/`。

### 2. 构建镜像

在 UGOS Docker 应用中：
1. 进入「镜像」→「添加」→「从 Dockerfile 构建」
2. 选择项目目录中的 `Dockerfile`
3. 镜像名称填写 `video-compressor`
4. 点击构建

### 3. 创建容器

在 UGOS Docker 应用中：
1. 进入「容器」→「添加」
2. 选择刚构建的 `video-compressor` 镜像
3. 端口映射：`5050:5050`
4. 卷挂载：`/volume1/docker/video-compressor/data` → `/data`
5. 环境变量：
   - `DATA_DIR` = `/data`
   - `HOST` = `0.0.0.0`
   - `PORT` = `5050`
6. 重启策略：`unless-stopped`
7. **（可选）硬件加速**：在「设备」中添加 `/dev/dri` → `/dev/dri`
8. 启动容器

---

## 启用 Intel QSV 硬件加速

编辑 `docker-compose.yml`，取消注释：

```yaml
services:
  video-compressor:
    build: .
    # ...
    devices:
      - /dev/dri:/dev/dri
```

然后重建容器：

```bash
docker compose up -d --build
```

系统会自动检测到 `hevc_qsv` 或 `h264_qsv` 编码器并使用硬件加速。

> **注意**：如果容器内没有 `/dev/dri/renderD128` 设备，系统会自动回退到软件编码，不会报错。

---

## 常用命令

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新代码后重建
docker compose up -d --build

# 查看压缩任务数据
ls -la ./data/jobs/
```

---

## 目录结构

```
video-compressor/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── compressor/        # 压缩引擎
├── web/               # Web 应用
│   ├── app.py         # Flask API
│   └── templates/     # 前端页面
├── run.py             # 本地开发启动
├── data/              # 运行时数据（自动创建）
│   ├── uploads/       # 上传文件（临时）
│   ├── outputs/       # 压缩输出
│   └── jobs/          # 任务状态
└── DEPLOY.md          # 本部署指南
```

`./data` 目录挂载到容器内 `/data`，所有上传、输出、任务数据均持久化在 NAS 上。

---

## 访问地址

- 局域网：`http://NAS_IP:5050`
- 如果 NAS 开启了 DDNS/外网访问：`http://你的域名:5050`（需要在路由器开放 5050 端口）

---

## 修改端口

如需修改默认端口（5050），同步修改以下文件：

1. `docker-compose.yml` — 端口映射（左侧为主机端口）
2. `Dockerfile` — `EXPOSE` 和 `CMD` 中的端口
3. 环境变量 `PORT`

---

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker compose logs video-compressor
```

### 端口被占用

```bash
# 在 NAS 上查看端口占用
ss -tlnp | grep 5050
# 修改 docker-compose.yml 中的端口映射
```

### 压缩失败

1. 检查 NAS 磁盘空间：`df -h`
2. 检查容器日志中的错误信息
3. 确保 `./data` 目录有写入权限

### 硬件加速不生效

```bash
# 检查容器内是否有渲染设备
docker exec video-compressor ls -la /dev/dri/
# 如果没有，说明 NAS 的 GPU 驱动未加载或设备未透传
```

---

## 国内用户注意事项

本项目已配置国内镜像加速：

- **Docker Hub**：如无法拉取 `python:3.12-slim`，建议在 UGOS Docker 设置中配置镜像加速：
  - DaoCloud: `https://docker.m.daocloud.io`
- **APT 源**：Dockerfile 已自动切换至清华大学镜像
- **PyPI 源**：Dockerfile 已自动切换至清华大学镜像
