# OpenCode Token Dashboard

[OpenCode](https://github.com/code-yeongyu/oh-my-openagent) 的只读 Token 用量仪表盘。
从 `opencode.db`（SQLite）中读取会话 Token 消耗数据，通过网页图表展示 —— 不写入任何数据。

A read-only token usage dashboard for [OpenCode](https://github.com/code-yeongyu/oh-my-openagent).
Reads session-level token consumption from `opencode.db` (SQLite) and renders time-series
charts in the browser — never writes to the database.

---

## 功能 / Features

- **概览卡片** — 总 Token 数、总费用、会话数、消息数
- **时间序列图** — 按日/周/月聚合的 Input / Output / Reasoning / Cache 堆叠面积图
- **模型分布** — 按模型（model + provider）的 Token 消耗排行榜
- **项目分布** — 按项目（从 worktree 自动推导项目名）的 Token 消耗排行榜
- **费用分布** — 各模型的费用柱状图

| Chart | Description |
|-------|-------------|
| Overview cards | Total tokens, cost, sessions, messages |
| Time-series | Stacked area chart by day/week/month |
| Model breakdown | Horizontal bar by model + provider |
| Project breakdown | Horizontal bar by project (derived from worktree) |
| Cost breakdown | Bar chart by model |

---

## 快速开始 / Quick Start

### 前置要求 / Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — Python 包管理器
- OpenCode 的数据库文件 `opencode.db`（默认路径见下方）

### 安装 / Install

```bash
# 克隆项目
git clone <repo-url>
cd opencode_token_dashboard

# 同步依赖（自动创建虚拟环境）
uv sync --extra dev

# 运行开发服务器
uv run python -m app.main
```

默认监听 `http://127.0.0.1:20230`。可通过以下方式修改端口：

- **CLI 参数**：`uv run python -m app.main --port 9999`
- **环境变量**：`$env:PORT = "9999"; uv run python -m app.main`

优先级：CLI 参数 > 环境变量 > 默认值。

> **Windows 注意**：系统可能自动保留部分端口范围（`netsh int ipv4 show excludedportrange protocol=tcp`），如遇 `WSAEACCES` 错误请更换端口。

```bash
# Windows PowerShell
$env:PORT = "58020"
uv run python -m app.main

# Linux / macOS
PORT=58020 uv run python -m app.main
```

### 运行测试 / Run Tests

```bash
uv run pytest -v
```

共 45 个测试用例（25 个单元测试 + 20 个集成测试），全部验证通过。

---

## 数据库 / Database

从 OpenCode 的本地 SQLite 数据库 `opencode.db` 读取数据。**只读模式**（连接时设置 `PRAGMA query_only = 1`，禁止任何写入操作）。

### 默认路径

| OS | Path |
|----|------|
| **Windows** | `C:\Users\<用户名>\.local\share\opencode\opencode.db` |
| **Linux / macOS** | `~/.local/share/opencode/opencode.db` |

可通过环境变量 `OPCODE_DB_PATH` 自定义路径。

### 项目结构 / Project Structure

```
opencode_token_dashboard/
├── app/                    # Web 应用包
│   ├── __init__.py
│   ├── main.py             # FastAPI 入口（uvicorn）
│   ├── routes.py           # 1 个 HTML + 5 个 JSON API 端点
│   ├── db.py               # 7 个只读 SQLite 查询函数
│   └── templates/
│       └── index.html      # ECharts 仪表盘页面（~1000 行，深色主题，5 张图表）
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # 测试夹具（13 条消息的样本数据库）
│   ├── test_db.py          # 25 个数据库查询测试
│   └── test_routes.py      # 20 个 API 路由测试
├── pyproject.toml          # uv 项目配置
├── AGENTS.md               # 项目知识库（AI 辅助参考）
└── README.md
```

### API 端点 / Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | 仪表盘 HTML 页面 |
| `GET` | `/api/overview` | 总览统计数据（Token 数、费用、会话数、消息数） |
| `GET` | `/api/tokens-by-date?granularity=day` | 按日/周/月聚合的 Token 消耗 |
| `GET` | `/api/tokens-by-model` | 各模型 Token 消耗排行 |
| `GET` | `/api/tokens-by-project` | 各项目 Token 消耗排行 |
| `GET` | `/api/cost-breakdown` | 各模型费用分布 |

---

## 技术栈 / Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) 0.136+ |
| Server | [uvicorn](https://www.uvicorn.org/) 0.46+ |
| Template engine | Raw [Jinja2](https://jinja.palletsprojects.com/) 3.1+ |
| Charting | [ECharts](https://echarts.apache.org/) 5.6 (CDN) |
| Test | [pytest](https://docs.pytest.org/) + [httpx](https://www.python-httpx.org/) |
| Database | SQLite (read-only, `PRAGMA query_only = 1`) |

---

## 约束 / Constraints

- **只读访问**：绝不执行 `INSERT` / `UPDATE` / `DELETE`
- **无 SPA 构建工具**：单页仪表盘，使用 CDN 引入 ECharts
- **长查询控制**：数据库约 385MB，~22k 条消息，所有查询设计了合理的聚合（无全表逐行扫描）

---

## LICENSE

MIT
