# FreeLLMAPI × Debate × Agentic AI

A unified platform integrating **FreeLLMAPI** (free LLM routing) with an **AI Debate Simulator** featuring immersive character interactions, scene settings, and multi-agent capabilities.

## 🎯 What Is This?

This project combines three powerful components:

1. **FreeLLMAPI** - A free LLM router that aggregates 16+ providers (Google, Groq, OpenRouter, etc.) behind one API key
2. **Debate Simulator** - Multi-character AI debates with immersive roleplay
3. **Agentic AI Tools** - Knowledge hub, news aggregation, and personal chat features

## 🚀 Quick Start

```bash
# Navigate to the project
cd ~/freellmapi

# Start all services
./run.sh start

# Check status
./run.sh status
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | http://localhost:3001/ | Main FreeLLMAPI interface |
| **Debate** | http://localhost:3001/debate | Group AI debates (18 characters) |
| **Personal** | http://localhost:3001/personal | 1-on-1 immersive roleplay |
| **Knowledge** | http://localhost:3001/knowledge | RAG knowledge hub |
| **Playground** | http://localhost:3001/playground | Test models, view history |

## ✨ Features

### 🎭 Debate Simulator
- **18 Character Cards** with unique personalities and images
- **Scene/Setting Selector** - Choose where the conversation happens:
  - Café, Car, Home, Office, Park
  - Restaurant, Bar, Bedroom, Kitchen, Living Room
- **Search Box** - Filter characters by name
- **History Management** - Save, load, and delete conversations
- **Auto-Play Mode** - Watch debates run autonomously
- **Export** - Download transcripts as markdown
- **Token Usage Tracking** - See input/output tokens per message
- **Rate Limit Info** - View remaining RPM per model

### 💬 Personal Chat
- **1-on-1 Roleplay** with immersive setting
- **Character Selection** - Choose your conversation partner
- **Scene Context** - AI describes surroundings and actions
- **Session Persistence** - Conversations survive refresh

### 🧠 Knowledge Hub
- **RAG Integration** - Upload documents for contextual responses
- **Search** - Query your knowledge base
- **File Support** - PDF, DOCX, TXT, Source Code

### 📊 Playground
- **Model Testing** - Try different models on your prompts
- **History** - View past conversations with search
- **Rate Limits** - Monitor API usage across providers
- **Token Stats** - Track costs and usage

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   React UI      │────▶│  Express Server  │────▶│ FreeLLMAPI  │
│  (:5174/:3001)  │     │    (:3001)       │     │   Proxy     │
└─────────────────┘     └────────┬─────────┘     └──────┬──────┘
                                 │                       │
                                 ▼                       ▼
                        ┌──────────────────┐     ┌─────────────┐
                        │  Debate Module   │     │  16+ LLM    │
                        │  (/debate)       │     │  Providers  │
                        └────────┬─────────┘     └─────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Python Server    │
                        │  (:5050)         │
                        │ (Optional API)   │
                        └──────────────────┘
```

## 📂 Project Structure

```
freellmapi/
├── server/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── debate.ts      # Debate API endpoints
│   │   │   ├── playground.ts  # History management
│   │   │   └── rateLimits.ts  # Rate limit tracking
│   │   └── app.ts             # Main Express app
│   └── data/
│       ├── characters.json    # 18 character definitions
│       ├── images/            # Character portrait images
│       ├── debate_sessions/   # Saved conversations
│       └── exports/           # Downloaded transcripts
├── client/
│   └── src/
│       ├── pages/
│       │   ├── PlaygroundPage.tsx
│       │   └── ...
│       └── App.tsx            # Navigation with Debate link
├── docs/
│   ├── debate.html            # Debate UI template
│   ├── personal.html          # Personal chat UI
│   └── knowledge.html         # Knowledge hub UI
├── run.sh                     # Startup script
└── README.md                  # This file
```

## 🔧 Commands

```bash
# Start all services
./run.sh start

# Stop all services
./run.sh stop

# Restart all services
./run.sh restart

# Check status
./run.sh status
```

## 🔑 API Endpoints

### Debate API
```bash
# Get characters
GET /api/characters

# Send chat message
POST /api/chat
{
  "topic": "AI ethics",
  "characters": ["Maya", "Shimelia"],
  "history": [],
  "user_name": "Sword",
  "mode": "random",
  "forced_speaker": "",
  "scene": "cafe"  # Optional: cafe, car, home, office, etc.
}

# Save session
POST /api/sync_session
{
  "session_id": "unique-id",
  "topic": "...",
  "characters": [...],
  "history": [...]
}

# List sessions
GET /api/sessions

# Export transcript
POST /api/export
{
  "topic": "...",
  "characters": [...],
  "history": [...]
}

# Upload character card
POST /api/upload_character
# Multipart form with PNG file
```

### FreeLLMAPI Proxy
```bash
# Chat completions (OpenAI-compatible)
POST /v1/chat/completions
Authorization: Bearer <unified-api-key>

# Models list
GET /v1/models
```

## 🎨 Characters

The platform includes 18 pre-loaded characters:

| Character | Persona |
|-----------|---------|
| Admiral Statura | Military strategist, values discipline |
| Elena Vasquez | Tech ethicist, progressive views |
| Makima | Analytical, manipulative thinker |
| Maya | Creative, emotional, Quotidian Bipolarity |
| Shimelia | Intense, passionate debater |
| ... | *(12 more available)* |

## 🌟 Key Innovations

1. **Unified Free LLM Access** - 100+ free models across 16 providers
2. **Scene-Aware Roleplay** - AI adapts dialogue to physical setting
3. **Multi-Agent Debates** - Watch characters debate autonomously
4. **Immersive Personal Chat** - 1-on-1 with descriptive narration
5. **Persistent Sessions** - Save and resume conversations
6. **Zero Login Required** - Open access on localhost

## 📝 License

MIT License - Feel free to use, modify, and distribute.

## 🤝 Contributing

This is a merged project combining:
- [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) - LLM routing
- [AI_Debate](https://github.com/BayazidHabibSiddikee/AI_Debate) - Debate simulator
- Custom integrations and enhancements

---

**Built with ❤️ for AI enthusiasts**

Open http://localhost:3001/debate to start debating!
