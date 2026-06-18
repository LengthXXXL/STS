<div align="center">

# STS 模拟交易系统

Simulated Trading System，一个面向量化策略初学者的可视化积木式模拟交易平台。

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-42b883?style=flat-square&logo=vuedotjs&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-300_passing-6d3df2?style=flat-square)

</div>

## 项目简介

STS 的目标是让不懂代码的用户也能搭建自己的盘中量化策略。用户可以在黑曜石风格的策略工作台中拖拽积木，通过连接线表达输入和输出，例如把“条件”“收益率”“卖出”“冷却”等积木组合起来，形成一套可回测、可保存、可分享的交易逻辑。

系统当前围绕单股票策略测试展开，支持 A 股和美股的基础交易规则、1 分钟和 5 分钟 K 线回测、模拟账户、个人空间、积木分享、论坛审核、文件管理等模块。

## 目录

- [功能概览](#功能概览)
- [核心流程](#核心流程)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [VSCode 启动](#vscode-启动)
- [测试与构建](#测试与构建)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [数据库概览](#数据库概览)
- [开发路线](#开发路线)

## 功能概览

### 策略工作台

| 模块 | 当前能力 |
| --- | --- |
| 大画布 | 类似无边记的点阵画布，支持平移、缩放、清屏和磁吸对齐 |
| 积木库 | 右侧浮窗，支持折叠、拖拽、搜索和功能分类 |
| 积木拖拽 | 从积木库拖到画布，画布内可继续移动 |
| 连线系统 | 积木左右两侧输入/输出端点，可拉线连接，也可删除连接 |
| 参数面板 | 右键积木打开参数配置，可在面板中删除积木 |
| 策略校验 | 发布或回测前检查积木、连接、股票、时间区间等必要条件 |

### 积木能力

| 分类 | 积木 |
| --- | --- |
| 交易动作 | 买入、卖出、清仓、调仓 |
| 风险控制 | 止盈、止损、移动止损、异常冷却 |
| 条件逻辑 | 如果、与、或、非 |
| 技术指标 | RSI、MACD、布林带、VWAP |
| 自定义积木 | 用户可把当前画布保存为私有积木，可选择暴露参数，并在搭建页和个人空间复用 |

### 业务模块

| 模块 | 说明 |
| --- | --- |
| 登录注册 | JWT 鉴权，普通用户和管理员角色分离 |
| 个人空间 | 管理策略、我的积木、模拟账户、回测记录、论坛内容和个人文件 |
| 模拟账户 | 创建单股票策略测试账户，绑定市场和初始资金 |
| 回测系统 | 支持 A 股和美股、1 分钟和 5 分钟 K 线、收益率、回撤、交易时间线、资金曲线和报告导出 |
| 行情缓存 | 用户点击运行回测后按需检查并下载缺失行情，避免提前浪费时间和本地空间 |
| 积木分享 | 公开积木搜索、收藏、导入和热度统计，推荐能力集中在分享页内 |
| 论坛 | 发帖、评论、关联公开积木或回测内容，帖子和评论提交后进入审核 |
| 管理后台 | 管理员审核公开积木、论坛帖子和评论 |
| 文件管理 | 上传、搜索、下载、删除个人文件，文件元数据入库，文件本体本地保存 |

## 核心流程

```mermaid
flowchart LR
  A["打开策略工作台"] --> B["拖拽积木到画布"]
  B --> C["连接输入/输出端点"]
  C --> D["配置积木参数"]
  D --> E["选择市场、股票、周期和时间段"]
  E --> F["检查并下载缺失行情"]
  F --> G["运行回测"]
  G --> H["查看收益、回撤、交易明细和资金曲线"]
  H --> I["保存到个人空间"]
  I --> J["发布积木或在论坛分享经验"]
  J --> K["管理员审核"]
  K --> L["公开展示、搜索、收藏、导入"]
```

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router、Pinia、Axios、ECharts、Vite、Vitest |
| 后端 | Python 3.10+、FastAPI、SQLAlchemy、Pydantic、PyJWT、Passlib |
| 数据库 | MySQL 8.0+，测试环境使用 SQLite in-memory |
| 鉴权 | JWT Bearer Token |
| 文件 | FastAPI UploadFile，本地文件目录 + MySQL 元数据 |
| 行情 | A 股东方财富分钟 K 线，美股 Yahoo Chart 可选配置，本地缓存优先 |
| 工程 | 前后端分离、VSCode tasks、pytest、ruff、vue-tsc |

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Git

### 1. 克隆项目

```bash
git clone https://github.com/LengthXXXL/STS.git
cd STS
```

### 2. 创建数据库

在 MySQL 中创建数据库：

```sql
CREATE DATABASE sts_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

后端在开发模式下会自动创建当前模型对应的数据表。

### 3. 配置后端环境变量

```bash
cd backend
cp .env.example .env
```

修改 `backend/.env` 中的数据库连接和 JWT 密钥：

```env
APP_NAME=STS API
ENVIRONMENT=development
DATABASE_URL=mysql+pymysql://你的用户名:你的密码@127.0.0.1:3306/sts_db?charset=utf8mb4
JWT_SECRET_KEY=请换成更长的随机字符串
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
US_MARKET_DATA_PROVIDER=disabled
```

如果需要尝试美股 Yahoo 分钟行情，可把 `US_MARKET_DATA_PROVIDER` 改为 `yahoo`。A 股分钟行情目前通过东方财富接口下载并写入本地缓存。

### 4. 启动后端

```bash
cd backend
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

### 5. 启动前端

打开另一个终端：

```bash
cd frontend
npm install
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

## VSCode 启动

项目已经内置 VSCode tasks 和 debug 配置。用 VSCode 打开克隆后的 `STS` 根目录后，可以使用：

| 操作 | VSCode 入口 |
| --- | --- |
| 安装后端依赖 | `Terminal > Run Task... > Setup: backend venv` |
| 安装前端依赖 | `Terminal > Run Task... > Setup: frontend deps` |
| 启动全栈 | `Run and Debug > Run: STS full stack` |
| 单独启动后端 | `Terminal > Run Task... > Run: backend API` |
| 单独启动前端 | `Terminal > Run Task... > Run: frontend Vite` |

如果出现 `ModuleNotFoundError: No module named 'fastapi'`，通常是 VSCode 没有选中 `backend/.venv`。在命令面板中执行 `Python: Select Interpreter`，选择：

```text
backend/.venv/bin/python
```

更多说明见 [docs/vscode-run.md](docs/vscode-run.md)。

## 测试与构建

在项目根目录执行：

```bash
backend/.venv/bin/python -m ruff check backend/app backend/tests
backend/.venv/bin/python -m pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

最近一次验证结果：

| 项目 | 结果 |
| --- | --- |
| 后端 lint | 通过 |
| 后端测试 | 185 passed |
| 前端测试 | 115 passed |
| 前端构建 | 通过 |

## 项目结构

```text
STS
├── backend
│   ├── app
│   │   ├── api              # FastAPI 路由
│   │   ├── core             # 配置、数据库、安全、轻量 schema migration
│   │   ├── models           # SQLAlchemy 数据模型
│   │   ├── schemas          # Pydantic 请求与响应模型
│   │   ├── services         # 业务逻辑、回测、行情、推荐、文件等服务
│   │   └── main.py          # FastAPI 应用入口
│   ├── tests                # pytest 后端测试
│   └── pyproject.toml
├── frontend
│   ├── src
│   │   ├── api              # Axios 客户端
│   │   ├── components       # 通用组件
│   │   ├── router           # 前端路由
│   │   ├── stores           # Pinia 状态
│   │   ├── styles           # 黑曜石主题样式
│   │   └── views            # 工作台、个人空间、论坛、分享页、后台审核
│   ├── tests                # Vitest 前端测试
│   └── package.json
├── docs                     # 开发说明和阶段设计文档
├── .vscode                  # VSCode tasks/debug 配置
└── README.md
```

## API 概览

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 健康检查 | `GET /api/health` | 后端服务状态 |
| 鉴权 | `/api/auth/*` | 注册、登录、当前用户 |
| 策略 | `/api/strategies` | 保存、查询、重命名、删除策略 |
| 自定义积木 | `/api/custom-blocks` | 私有积木 CRUD、发布审核 |
| 公开积木 | `/api/shared-blocks` | 公开列表、详情、收藏、导入、行为记录 |
| 积木审核 | `/api/admin/custom-block-reviews` | 管理员审核公开积木 |
| 模拟账户 | `/api/simulation-accounts` | 创建和管理模拟账户 |
| 回测 | `/api/backtests` | 运行回测、查看历史、详情复盘、导出报告 |
| 行情 | `/api/market-data` | 行情覆盖检查、按需下载和缓存 |
| 市场规则 | `/api/market-rules` | A 股和美股规则说明 |
| 论坛 | `/api/forum` | 发帖、评论、我的论坛内容 |
| 论坛审核 | `/api/admin/forum` | 管理员审核帖子和评论 |
| 文件 | `/api/files` | 上传、列表、下载、删除个人文件 |

## 数据库概览

| 表 | 用途 |
| --- | --- |
| `users`, `roles`, `user_roles` | 用户、角色和权限 |
| `strategies` | 用户保存的策略草稿和回测配置 |
| `custom_blocks` | 用户自定义积木和公开审核状态 |
| `shared_block_stats`, `shared_block_favorites`, `shared_block_imports` | 公开积木热度、收藏、导入和推荐数据 |
| `simulation_accounts` | 模拟账户 |
| `backtest_tasks` 及明细表 | 回测任务、交易记录、事件、资金曲线和时间线 |
| `market_kline_cache`, `market_data_download_ranges` | 本地行情缓存和下载区间记录 |
| `forum_posts`, `forum_comments` | 论坛帖子、评论和审核状态 |
| `uploaded_files` | 用户上传文件元数据 |

## 开发路线

| 阶段 | 目标 |
| --- | --- |
| 已完成 | 可视化积木搭建、自定义积木参数化、策略保存、模拟账户、回测记录、回测报告导出、A 股/美股规则、行情缓存、个人空间、论坛、积木分享、文件管理 |
| 下一步 | 完善论坛多类型关联卡片、点赞收藏和标签/作者等社区查询能力 |
| 后续 | 更稳定的行情数据源、公开积木推荐排序升级、策略版本管理、回测参数批量对比 |
| 长期 | 更细的交易成本模型、策略模板市场、多人协作和更完善的管理员后台 |

## 注意事项

- STS 是模拟交易和学习项目，不构成任何投资建议。
- 当前回测以单股票策略为主，暂不处理多股票组合、真实下单和实盘风控。
- A 股和美股规则会随市场变化调整，项目中的规则用于模拟测试，需要持续校准。
- `backend/.env`、`backend/uploads/`、`backend/.venv/`、`frontend/node_modules/` 不应提交到仓库。
