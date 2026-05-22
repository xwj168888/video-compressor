# 视频压缩工具

跨平台视频压缩 Web 应用，支持硬件加速（Intel QSV / NVIDIA NVENC / AMD AMF / Apple VideoToolbox），针对 500MB-1GB 短视频上传、压缩、下载全流程优化。

## 功能特性

- **Web 界面** — 中文 UI，三阶段进度展示（上传 → 探测 → 压缩）
- **硬件加速** — 自动检测最优编码器，不支持时自动回退软件编码
- **实时进度** — SSE 推送压缩进度，XHR 上传进度条
- **多种配置** — AI 分析优化 / 极限压缩 / 均衡压缩 / 接近无损
- **目标体积** — 支持指定目标文件大小
- **Docker 部署** — 一键部署，已适配国内网络环境

## 快速开始

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（默认 http://localhost:5050）
python run.py web
```

### Docker 部署

```bash
docker compose up -d
```

浏览器访问 `http://localhost:5050`。

详细部署说明见 [DEPLOY.md](DEPLOY.md)。

## 压缩配置

| 配置 | 分辨率 | 帧率 | 编码 | 适用场景 |
|------|--------|------|------|----------|
| AI 分析优化 | ≤1080p | ≤30 | HEVC | 发给 AI 分析，平衡体积与细节 |
| 极限压缩 | ≤720p | ≤15 | HEVC | 最小体积，快速分享 |
| 均衡压缩 | ≤1080p | ≤30 | H.264 | 兼顾画质和兼容性 |
| 接近无损 | 原始 | 原始 | HEVC | 保留最佳画质 |

## 硬件加速

系统启动时自动检测可用硬件编码器：

| 平台 | 编码器 | 要求 |
|------|--------|------|
| Windows | QSV / NVENC / AMF | Intel / NVIDIA / AMD GPU |
| Linux (NAS) | VA-API / QSV / NVENC | 需透传 `/dev/dri` |
| macOS | VideoToolbox | 内置支持 |

Docker 部署时，如需启用 Intel QSV 硬件加速，取消 `docker-compose.yml` 中 `devices` 部分的注释。

## 项目结构

```
video-compressor/
├── compressor/        # 压缩引擎
│   ├── engine.py      # FFmpeg 调用与编码器检测
│   ├── profiles.py    # 压缩配置
│   └── utils.py       # 视频信息探测
├── web/               # Web 应用
│   ├── app.py         # Flask API（SSE 进度推送）
│   └── templates/     # 前端页面
├── Dockerfile
├── docker-compose.yml
└── DEPLOY.md          # 部署指南
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/profiles` | GET | 获取压缩配置列表 |
| `/api/compress` | POST | 上传并压缩（`file` + `profile` + `target_size`） |
| `/api/progress/<id>` | GET | SSE 压缩进度 |
| `/api/download/<id>` | GET | 下载压缩结果 |
| `/api/cleanup/<id>` | DELETE | 清理临时文件 |

## NAS 部署

针对绿联 NAS 4800 等设备编写了详细部署指南，包括 Docker 图形界面和命令行两种方式，以及 QSV 硬件加速配置。见 [DEPLOY.md](DEPLOY.md)。
