"""Memory and conversation survive a real restart: two separate processes on the same SQLite files."""

import subprocess
import sys
from pathlib import Path

WORKER = Path(__file__).with_name("restart_worker.py")
SRC = Path(__file__).resolve().parents[1] / "src"


def run_pass(n: int, data_dir: Path) -> str:
    out = subprocess.run([sys.executable, str(WORKER), str(n), str(data_dir)], capture_output=True, text=True,
                         timeout=300, env={**__import__("os").environ, "PYTHONPATH": str(SRC)})
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout


def test_memory_and_conversation_survive_restart(tmp_path):
    first = run_pass(1, tmp_path)
    second = run_pass(2, tmp_path)   # a fresh interpreter: nothing shared but the files
    assert "memory=- prefers short answers" in first
    assert "memory=- prefers short answers" in second
    before = int(first.split("messages=")[1].split()[0])
    after = int(second.split("messages=")[1].split()[0])
    assert after > before            # the old conversation was loaded, then the new turn appended
