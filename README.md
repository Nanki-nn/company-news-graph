# Company News Graph

一个面向“公司动态研究”的开源项目。

输入公司名称和时间范围，抓取相关新闻与公告，抽取结构化事件与关系，最终以图谱形式展示结果，并保留可追溯的来源证据。

## 项目目标

这个项目要解决的问题是：

- 输入：`公司名称` + `时间范围`
- 处理：检索新闻、公告、披露信息，抽取实体、事件和关系
- 输出：一份摘要结果 + 一张可交互的关系图

它不是通用知识图谱平台，而是更聚焦的“公司事件图谱”工具，适合做：

- 公司近期动态研究
- 竞品跟踪
- 投研信息整理
- 风险事件追踪
- 关系和时间演化分析

## 当前状态

当前仓库是第一版项目骨架，已经包含：

- 后端 `FastAPI` 接口骨架
- 前端 `React + Vite` 页面骨架
- 图谱节点和边的数据结构
- 一个可创建任务并返回图数据的研究接口
- `Google News RSS` 单一数据源接入
- 基于标题和摘要关键词的基础事件抽取
- 基于 `LangChain` 或 `requests` 的可选 AI 事件总结
- `Cytoscape.js` 图谱可视化
- 初版设计文档

当前已经可以本地跑通“前端提交 -> 后端返回图数据 -> 前端展示结果”这一条最小流程。

还没有接入更丰富的数据源、完整实体抽取和图数据库。

## 仓库结构

```text
backend/   后端接口与数据处理骨架
frontend/  前端页面与图谱展示骨架
docs/      产品和技术文档
```

## 快速启动

### 启动后端

首次安装：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m uvicorn app.main:app --reload
```

后续日常启动：

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload
```

如果你的机器没有 `python` 命令，而只有 `python3`，请务必先完成虚拟环境激活。
激活后再执行 `python -m pip` 和 `python -m uvicorn`。

### 可选：启用 AI 事件总结

默认后端会使用规则摘要。

如果你想启用 AI 事件总结，推荐直接使用 `backend/.env`：

```bash
cd backend
cp .env.example .env
```

然后修改 `.env`：

```env
COMPANY_NEWS_USE_AI=1
LLM_PROVIDER=anthropic
```

如果你走 `Claude / Anthropic` 或中转站的 Anthropic 协议：

```env
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
# ANTHROPIC_BASE_URL=https://your-anthropic-compatible-endpoint
```

如果你的中转站提供的是 `OpenAI-compatible` 协议，但模型是 Claude，则这样配：

```env
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=claude-3-5-sonnet-latest
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
```

启用后，后端会在“新闻聚类之后、建图之前”为每个事件簇生成：

- 事件标题
- 事件摘要
- 关键要点
- 置信度

支持两种 provider：

- `anthropic` / `claude`
  目前通过 `LangChain` 调用
- `openai-compatible`
  目前通过 `requests` 直接请求 `/chat/completions`

是否实际用了 AI，可以从两个地方确认：

- 前端摘要卡片里的 `AI 状态` 和 `AI 提供方`
- 后端控制台日志里的 `generated_by=` 和 `confidence=`

默认启动后可以访问：

- `GET /`
- `GET /health`
- `POST /research/tasks`
- `GET /research/tasks/{task_id}`
- `GET /research/tasks/{task_id}/graph`

### 启动前端

首次安装：

```bash
cd frontend
npm install
npm run dev
```

后续日常启动：

```bash
cd frontend
npm run dev
```

默认前端会请求 `http://127.0.0.1:8000`。

如果你的后端地址不同，可以在前端目录下通过环境变量覆盖：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## 当前可用流程

1. 启动后端服务
2. 启动前端页面
3. 输入公司名称、开始日期、结束日期
4. 点击“开始研究”
5. 后端从 `Google News RSS` 拉取新闻
6. 后端基于标题和摘要做基础事件分类
7. 后端将相近新闻聚成关键事件
8. 如果启用了 AI，则生成事件摘要
9. 前端拉取图谱结果并用 `Cytoscape.js` 展示

当前已经接入真实单一数据源，并支持可选 AI 事件总结。

## 一键启动

如果你已经完成过首次安装，后续开发可以直接在项目根目录运行：

```bash
./start_dev.sh
```

这个脚本会自动：

- 查找可用的后端端口，避免 `8000` 被占用时报错
- 查找可用的前端端口
- 启动后端 `uvicorn`
- 启动前端 `vite`
- 自动把前端 API 地址指向实际后端端口

如果脚本提示缺少 `.venv` 或 `node_modules`，先按上面的“首次安装”步骤补齐一次。

## MVP 计划

第一阶段目标：

- 输入公司名和时间范围
- 拉取新闻和公告
- 抽取结构化事件
- 生成图谱节点和边
- 在前端展示可交互结果
- 所有结果都能回溯到原始来源

## 下一步开发计划

1. 接入新闻和公告数据源
2. 将规则抽取升级为 LLM 或混合抽取
3. 增加实体归一化和事件去重
4. 接入 Neo4j 图数据库
5. 增加节点点击详情与来源证据面板

## 设计文档

当前设计文档位于：

- [docs/design.md](docs/design.md)

## 开源定位

这个项目优先解决一个具体问题：

“研究某家公司在一段时间内发生了什么，并把结果用图谱方式组织起来。”

所以它的重点不是大而全，而是：

- 聚焦公司动态
- 聚焦事件结构化
- 聚焦证据可追溯
- 聚焦图谱展示和研究效率
