# Nile Systems HR Agent — Session 5

Everything from Sessions 2, 3 and 4, wired into one application you can hand to
somebody else.

| Session | What it contributed | Where it lives |
|---|---|---|
| 2 | Retrieval over your own documents | `agent.py` → `search_handbook` |
| 3 | Tools the agent chooses between | `agent.py` → `public_holidays` |
| 3 | A gate in front of an irreversible action | `agent.py` → `book_leave` |
| 4 | Memory, and pause/resume | `agent.py` → checkpointer |
| 5 | A handover note | `app.py` |

## Setup — do this BEFORE the session

1. Install Python 3.10 or newer.
2. Open this folder in VS Code, then open a terminal in it.
3. Create an isolated environment:

   ```
   python -m venv .venv
   ```
   ```
   # macOS / Linux
   source .venv/bin/activate
   # Windows
   .venv\Scripts\activate
   ```

4. Install what it needs:

   ```
   pip install -r requirements.txt
   ```

5. Copy `.env.example` to `.env` and paste your Groq key into it.
6. Check everything worked:

   ```
   python check_setup.py
   ```

## Run it

```
streamlit run app.py
```

Your browser opens on `http://localhost:8501`.

## The two tabs

**Chat** — ask about leave, expenses or public holidays. Ask it to book leave and
the agent pauses for approval. Nothing is written until somebody clicks.

**Handover** — what a sponsor reads before saying yes: what it does, where its
answers come from, what it must never do, and the risk register.

## If something breaks

| Symptom | Fix |
|---|---|
| `No GROQ_API_KEY found` | You have `.env.example`, not `.env`. Copy it and rename |
| Sidebar says keyword fallback | sentence-transformers not installed. The app still works |
| `streamlit: command not found` | The virtual environment is not active. Re-run the activate line |
| Port already in use | `streamlit run app.py --server.port 8502` |
| Agent forgets between messages | You restarted the app. Memory is in RAM by design |
| Approval buttons do nothing | Only one approval can be pending at a time. Refresh the page |
