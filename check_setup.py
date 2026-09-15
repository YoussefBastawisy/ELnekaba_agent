"""
check_setup.py — run this BEFORE the session, not during it.

    python check_setup.py

It tells you exactly what is missing and what to do about it.
Nothing here needs the internet except the last two checks.
"""
import sys

ok = True

def report(label, passed, fix=""):
    global ok
    print(f"  [{'OK ' if passed else 'XX '}] {label}")
    if not passed:
        ok = False
        if fix:
            print(f"         -> {fix}")

print("\nChecking your setup\n" + "-" * 48)

v = sys.version_info
report(f"Python {v.major}.{v.minor}", v >= (3, 10),
       "Install Python 3.10 or newer from python.org")

for mod, fix in [
    ("streamlit", "pip install -r requirements.txt"),
    ("langchain", "pip install -r requirements.txt"),
    ("langgraph", "pip install -r requirements.txt"),
    ("langchain_groq", "pip install -r requirements.txt"),
    ("pandas", "pip install -r requirements.txt"),
    ("dotenv", "pip install python-dotenv"),
]:
    try:
        __import__(mod); report(mod, True)
    except ImportError:
        report(mod, False, fix)

try:
    import sentence_transformers  # noqa
    report("sentence-transformers (optional)", True)
except ImportError:
    print("  [-- ] sentence-transformers not installed (optional)")
    print("         -> the app will fall back to keyword search. That is fine.")

from pathlib import Path
here = Path(__file__).parent
report(".env file exists", (here / ".env").exists(),
       "Copy .env.example to .env and paste your Groq key into it")
report("data/handbook.md exists", (here / "data" / "handbook.md").exists())

try:
    from dotenv import load_dotenv
    import os
    load_dotenv(here / ".env")
    key = os.getenv("GROQ_API_KEY", "")
    report("GROQ_API_KEY is set", key.startswith("gsk_"),
           "Your key should start with gsk_ — check .env")
except Exception:
    pass

if ok:
    try:
        from groq import Groq
        models = [m.id for m in Groq().models.list().data]
        report(f"Groq reachable ({len(models)} models live)", True)
    except Exception as e:
        report("Groq reachable", False, f"{type(e).__name__}: {e}")

print("-" * 48)
print("\n  READY.  Run:  streamlit run app.py\n" if ok
      else "\n  Not ready yet. Fix the XX lines above and run this again.\n")
