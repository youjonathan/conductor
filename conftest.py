"""Pytest path shim so tests can `from conductor import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
