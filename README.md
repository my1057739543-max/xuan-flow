# 🌊 Xuan-Flow (玄流)

[English](README.md) | [简体中文](README_CN.md)

A lightweight, state-driven Multi-Agent framework inspired by Deer-Flow. Built for flexibility, long-term memory, and seamless tool integration.

## 🚀 Overview

Xuan-Flow is designed to be a "thinking" assistant that can decompose complex requests, delegate tasks to specialized sub-agents, and remember important facts across sessions. It leverages **LangGraph** for structured agent workflows and **FastAPI** for a high-performance gateway.

## ✨ Key Features

- **🧠 Atomic Fact Memory**: An LLM-powered memory system that extracts and stores key facts from conversations, enabling long-term context retention without overwhelming the context window.
- **🤖 State-Driven Orchestration**: Uses LangGraph to manage agent states, enabling reliable multi-step reasoning and tool calling.
- **👥 Multi-Agent Architecture**: A central **Lead Agent** orchestrates specialized sub-agents (e.g., Researcher, Coder).
- **🛠️ MCP Integration**: Full support for the **Model Context Protocol (MCP)**, allowing the agent to connect to a vast ecosystem of external tools and data sources.
- **🔍 Intelligent Search**: Integrated with **Tavily** for high-quality web research.
- **🎨 Modern Web UI**: A sleek, responsive interface built with the latest web technologies.

## 🛠️ Tech Stack

### Backend (Python 3.12+)
- **[LangGraph](https://github.com/langchain-ai/langgraph)**: Orchestration and state management.
- **[LangChain](https://github.com/langchain-ai/langchain)**: LLM framework and tool integration.
- **[FastAPI](https://fastapi.tiangolo.com/)**: RESTful API gateway.
- **[Pydantic v2](https://docs.pydantic.dev/)**: Data validation and settings.
- **[Uvicorn](https://www.uvicorn.org/)**: ASGI server.

### Frontend
- **[Next.js 15](https://nextjs.org/)**: React framework with App Router.
- **[React 19](https://react.dev/)**: Reactive UI components.
- **[Tailwind CSS 4](https://tailwindcss.com/)**: Atomic CSS for rapid styling.
- **[Framer Motion](https://www.framer.com/motion/)**: Fluid UI animations.

## 🚦 Getting Started

### 1. Prerequisites
- Python 3.12 or higher.
- Node.js 18 or higher (for the Web UI).
- API Keys for: OpenAI (or compatible provider), Tavily (for search).

### 2. Installation
Clone the repository and install dependencies:
```bash
# Backend
pip install -e .

# Frontend
cd frontend
npm install
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your API keys:
```env
DEEPSEEK_API_KEY=your_key
OPENROUTER_API_KEY=your_key
DASHSCOPE_API_KEY=your_key
TAVILY_API_KEY=your_key
MYSQL_PASSWORD=root
MYSQL_DATABASE=xuan_flow
```
Review `config.yaml` to customize model selection and memory settings.

To enable the 3-layer memory pipeline (L1 JSON + L2 memory.md + L3 MySQL), set:
```yaml
memory:
	mysql_enabled: true
```

### 4. Running the Project

#### CLI Mode (Development)
Run the interactive CLI to test the Lead Agent:
```bash
python main.py
```

#### API Mode
Start the FastAPI gateway:
```bash
python run_api.py
```

#### Web UI
Start the Next.js development server:
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

#### One-command Full Stack (Frontend + Backend + MySQL)
```bash
docker compose up --build
```
This starts:
- MySQL on `3306`
- Backend API on `8000`
- Frontend on `3000`

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
