# 🌊 Xuan-Flow (玄流)

一款轻量级、状态驱动的多智能体（Multi-Agent）框架，灵感源自 Deer-Flow。专为灵活性、长效记忆和无缝工具集成而设计。

## 🚀 项目概览

Xuan-Flow 旨在成为一个具备“思考能力”的助手。它不仅能分解复杂的请求，还能将任务委派给专门的子智能体（Sub-agents），并能在跨会话的交互中记住重要事实。项目核心采用 **LangGraph** 进行有向有环图（DAG）编排，并使用 **FastAPI** 作为高性能网关。

---

## ✨ 核心亮点

- **🧠 原子化事实记忆系统 (Atomic Fact Memory)**：基于 LLM 的记忆提取机制。它能自动从对话中提取关键事实并进行增量更新（Upsert），实现长效上下文保留，同时避免上下文窗口溢出。
- **🤖 状态驱动编排 (State-Driven Orchestration)**：利用 LangGraph 维护 Agent 状态，支持复杂的多步推理、工具调用及任务流与会话流的物理隔离。
- **👥 多智能体架构 (Multi-Agent Architecture)**：由中心 **Lead Agent** 负责调度，支持委派给 **Researcher（搜索者）**、**Coder（代码助手）** 等专门节点。
- **🛠️ MCP 标准集成**：全面支持 **Model Context Protocol (MCP)**。通过配置驱动，Agent 可动态接入成千上万的外部工具与数据源。
- **⚡ 毫秒级流式响应 (SSE)**：前端采用 React 19 + Web Streams API，实现了健壮的 SSE 流式解析。支持逐字蹦出的打字机效果，极大优化了首屏加载体验（TTFB）。
- **🔍 深度搜索能力**：集成 **Tavily** 搜索引擎，提供高质量的实时联网研究能力。
- **🎨 现代全栈技术栈**：采用 Next.js 15 & Tailwind CSS 4 构建的极简玻璃拟态（Glassmorphism）UI。

---

## 🛠️ 技术架构

### 后端 (Python 3.12+)
- **[LangGraph](https://github.com/langchain-ai/langgraph)**：核心工作流编排与状态持久化。
- **[LangChain](https://github.com/langchain-ai/langchain)**：模型抽象与工具集成。
- **[FastAPI](https://fastapi.tiangolo.com/)**：支持异步处理与 SSE 推送的 RESTful 接口。
- **[Pydantic v2](https://docs.pydantic.dev/)**：严格的数据校验与配置管理。

### 前端
- **[Next.js 15](https://nextjs.org/)**：采用 App Router 架构。
- **[React 19](https://react.dev/)**：最新的并发渲染特性。
- **[Tailwind CSS 4](https://tailwindcss.com/)**：高性能原子化 CSS 框架。
- **[Framer Motion](https://www.framer.com/motion/)**：丝滑的 UI 动效处理。

---

## 🚦 快速开始

### 1. 环境准备
- Python 3.12+
- Node.js 18+ (用于 Web UI)
- API 密钥：OpenAI/DeepSeek (大模型) 以及 Tavily (搜索)

### 2. 安装依赖
```bash
# 后端安装
pip install -e .

# 前端安装
cd frontend
npm install
```

### 3. 配置
将 `.env.example` 复制为 `.env` 并填写密钥：
```env
DEEPSEEK_API_KEY=your_key
TAVILY_API_KEY=your_key
```
在 `config.yaml` 中自定义模型选择和记忆系统参数。

### 4. 运行项目

#### 命令行模式 (CLI)
```bash
python main.py
```

#### API 服务
```bash
python run_api.py
```

#### 网页前端
```bash
cd frontend
npm run dev
```
访问 [http://localhost:3000](http://localhost:3000) 即可开始对话。

---

## 📄 开源协议
本项目基于 MIT 协议开源。详见 [LICENSE](LICENSE) 文件。
