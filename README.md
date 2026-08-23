# 🌐 Sword Debate Simulator (AI_Debate)

A unified platform for simulating synthetic character conversations, multi-agent debates, and generating deep research data via RAG (Retrieval-Augmented Generation).

---

## ✨ Features (Premium Edition)

1. **Auto-Pilot Debates**: Watch characters debate autonomously in real-time with continuous generation.
2. **Knowledge Hub UI**: Upload PDFs, DOCX, TXT, and source code directly via the UI to inject facts into the RAG brain.
3. **Markdown Rendering**: Full markdown parsing for beautiful, structured chat messages (code blocks, quotes, lists).
4. **Rich Export**: Download the raw `.jsonl` dataset or click **Export Transcript** for a formatted `.md` file of the debate.
5. **FastAPI Powered**: Async, high-performance backend serving the debate LLM logic.
6. **FreeLLM API Support**: Out-of-the-box configuration for `api.freellmapi.com`.

---

## 📦 Installation

### Prerequisites
* Python 3.10+
* `faiss-cpu` compatible system

### Setup
1. Clone the repository.
2. Use the provided environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements-debate.txt
   pip install -r requirements-rag.txt
   ```
3. Initialize the `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```

---

## 🚀 Launching the Platform

### Option 1: One-Click Script
If you have the `marin_venv` configured, simply run:
```bash
./run.sh
```

### Option 2: Docker Compose (Recommended)
If you have Docker installed, simply run:
```bash
docker-compose up --build -d
```
The services will be available at:
* **Debate Hub**: [http://localhost:5050](http://localhost:5050)
* **RAG Server**: [http://localhost:5080](http://localhost:5080)

### Option 3: Manual Start
1. **Start the RAG Server** (Optional, provides factual context):
   ```bash
   python rag_server.py --port 5080
   ```
2. **Start the Debate Simulator**:
   ```bash
   python app.py
   ```
3. **Access the UI**: Go to [http://localhost:5050](http://localhost:5050).

---

## 🎭 Adding Characters

Drop your SillyTavern/TavernAI `.png` character cards into the `images/` directory and run:
```bash
python extract_chunks.py
```
This automatically parses their embedded persona metadata (base64/JSON) and appends it to `characters.json`. No manual typing needed!

**Where to find character cards:**
You can download `.png` character cards from various community hubs, such as:
* [Chub.ai](https://chub.ai)
* [CharacterHub](https://characterhub.org)
* [JanitorAI](https://janitorai.com) (if they provide exportable Tavern cards)

### Adding Characters Manually
If you do not have a `.png` card and want to create a character manually, simply open `characters.json` and append a new JSON object to the array:
```json
{
  "name": "My Custom Character",
  "system_prompt": "You are a custom AI character. You speak politely and know a lot about science.",
  "image": "images/custom_avatar.png"
}
```

---

## ⚙️ Configuration (API Keys & Models)

You can configure your models, API keys, and endpoint links inside `settings.json`:
* **Models**: Change the default LLM (e.g., `gemma4:31b-cloud`, `llama3`).
* **API Keys**: Add your keys for OpenAI, Anthropic, Google, etc.
* **Server**: Update the `ollama_base_url` or `openai_base_url` if you are using an external provider or a different local port.

---

## 💾 Datasets

Every single debate turn is securely and automatically exported to `storage/debates_dataset.jsonl`.
This file is formatted optimally for fine-tuning future LLMs on synthetic multi-agent conversation data.

---

## 🛠 Tech Stack

* **Backend**: FastAPI, Uvicorn, LangChain Core.
* **Frontend**: Vanilla CSS (Premium Glassmorphism), HTML5, JavaScript, Marked.js.
* **RAG**: FAISS, HuggingFace Embeddings, PyPDF.
