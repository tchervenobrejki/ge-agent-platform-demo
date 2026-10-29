from dotenv import load_dotenv

# Load .env before agent.py reads its settings at import time.
load_dotenv()

from . import agent  # noqa: E402
