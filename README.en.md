<div align="right">
  <b>English</b> · <a href="./README.md">中文</a>
</div>

<div align="center">

# 📊 Company News Graph

**Track recent company events through an interactive knowledge graph**

Enter a company name and time range — the tool automatically aggregates SEC filings and Google News,
extracts structured investment events, and presents them as an interactive graph where every conclusion is traceable to its original source.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🏛️ **SEC EDGAR First** | Automatically fetches 8-K, 10-K, 10-Q and other official filings, prioritized over media reports |
| 📰 **Google News Supplement** | Intelligently resolves real company names so even obscure tickers match relevant news |
| 🧠 **Optional AI Summaries** | Supports Claude CLI, Anthropic API, and any OpenAI-compatible endpoint |
| 🕸️ **Interactive Graph** | Powered by Cytoscape.js — click any node to inspect event details and source evidence |
| 📅 **Event Timeline** | Chronological view of all events, color-coded by impact direction (positive / negative / neutral) |
| 🏆 **Key Events Panel** | Automatically scores and surfaces the top 3 most investment-relevant events |
| 🔍 **Ticker Autocomplete** | 37 popular stocks built in, with keyboard navigation support |
| 💾 **Persistent History** | Results are saved to disk and restored on restart — revisit any past research session |

---

## 🖥️ Screenshots

![img.png](img.png)
![img_1.png](img_1.png)

---

## 🏗️ Architecture

```
User Input
  │  Company name / ticker + date range
  ▼
Backend Research Pipeline
  ├─ SEC EDGAR  ──→ Official filings (8-K / 10-K / 10-Q / DEF 14A …)
  │                  ↳ Auto CIK lookup, works with any ticker
  │
  ├─ Google News ──→ Supplementary media coverage
  │                  ↳ Uses SEC registered name to improve query accuracy
  │                    (e.g. NVDA → "NVIDIA")
  │
  ├─ Event Extraction ──→ Keyword-based classification
  │                        (earnings / M&A / layoffs / regulation …)
  │
  ├─ News Clustering ───→ Groups similar headlines into a single event cluster
  │
  └─ AI Summary (optional) → Generates title, summary, key points, confidence
       ├─ claude-cli          Reuses your local Claude Code CLI — zero config
       ├─ anthropic           Calls the /messages API directly
       └─ openai-compatible   Calls any /chat/completions endpoint

Frontend Display
  ├─ Key Events cards (scored by importance, top 3 shown)
  ├─ Event timeline (reverse chronological, color-coded by impact)
  ├─ Cytoscape.js graph (Company → Event → Source)
  └─ Node detail panel (source links / AI summary / original article titles)
```

---

## ⚡ Quick Start

### Backend (FastAPI + Python 3.13)

**First-time setup:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

**Daily startup:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

> The backend listens on `http://127.0.0.1:8000` by default. Visit `/health` to confirm it's running.

### Frontend (React + Vite)

**First-time setup:**

```bash
cd frontend
npm install
npm run dev
```

**Daily startup:**

```bash
cd frontend
npm run dev
```

> The frontend points to `http://127.0.0.1:8000` by default. Override with an environment variable if needed:
> ```bash
> VITE_API_BASE_URL=http://localhost:9000 npm run dev
> ```

### One-command startup (recommended)

After completing the first-time setup, run from the project root:

```bash
./start_dev.sh
```

The script automatically detects available ports, starts both backend and frontend, and wires the frontend API URL to the actual backend port — no port conflicts.

---

## 🤖 AI Event Summaries (optional)

By default the app uses rule-based summaries and **requires no API key**. To enable AI summaries, create a `.env` file:

```bash
cd backend
cp .env.example .env
```

Then pick one of the options below:

---

### Option 1: Reuse your local Claude Code CLI (easiest — zero config)

```env
COMPANY_NEWS_USE_AI=1
LLM_PROVIDER=claude-cli
```

**Requirement:** [Claude Code CLI](https://claude.ai/download) must be installed and authenticated on your machine (i.e. the `claude` command works). No API key needed — the backend calls `claude -p` directly.

---

### Option 2: Anthropic API

```env
COMPANY_NEWS_USE_AI=1
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-6
```

Get a key at [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

To use a custom proxy, add:

```env
ANTHROPIC_BASE_URL=https://your-proxy-endpoint
```

---

### Option 3: OpenAI-compatible endpoint

```env
COMPANY_NEWS_USE_AI=1
LLM_PROVIDER=openai-compatible
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=claude-sonnet-4-6
OPENAI_BASE_URL=https://your-endpoint/v1
```

Works with any service that exposes a `/chat/completions` endpoint — OpenAI, local LLMs, third-party proxies, etc.

---

When AI is enabled, each event cluster receives a generated title, summary, key points, and confidence rating. Check the `AI Status` field in the summary card, or look for `generated_by=` in the backend logs to confirm it's working.

---

## 📁 Repository Structure

```
agents/
├── backend/
│   ├── app/
│   │   ├── api/          Routes and endpoint definitions
│   │   ├── schemas/      Pydantic data models
│   │   └── services/     Core research pipeline
│   ├── data/tasks/       Persisted task results (local JSON)
│   └── .env.example      Environment variable template
│
├── frontend/
│   └── src/
│       ├── components/   GraphView / InvestmentPanels / SummaryPanel
│       ├── lib/          API client / i18n / type definitions
│       └── pages/        Main App page
│
├── docs/                 Product docs and roadmap
└── start_dev.sh          One-command dev startup script
```

---

## 🗺️ Roadmap

- [x] SEC EDGAR official filings
- [x] Google News RSS supplement
- [x] Optional AI summaries (Claude / OpenAI-compatible)
- [x] Cytoscape.js interactive graph
- [x] Key Events panel + event timeline
- [x] Ticker autocomplete
- [x] Persistent task history and replay
- [x] Investment event entity & relation schema design
- [ ] More data sources (Bloomberg, Reuters, earnings call transcripts)
- [ ] Full entity extraction (people, locations, products, competitive relationships)
- [ ] Neo4j graph database integration
- [ ] Multi-company comparison and competitor tracking

---

## 📚 Design Docs

- [Investment Intelligence Roadmap](./docs/investment-intelligence-roadmap.md)

---

## 🌐 Project Focus

This project solves one specific problem:

> **"Research what happened to a company over a given period, and organize the results as a graph."**

It is not a general-purpose knowledge graph platform. It is a focused **company event graph** tool suited for:

- 📈 Rapid investment research summarization
- 🔭 Ongoing competitor monitoring
- ⚠️ Early detection of risk events
- 📖 Reviewing a company's recent history

Issues, PRs, and feedback are welcome.
