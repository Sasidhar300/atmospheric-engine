"""Repository-local handoff and graph commands, requiring only the stdlib."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs/HANDOFF.md"
GRAPH = ROOT / "graphify-out"
STAMP = GRAPH / "atmosphere-inputs.json"
SECTIONS = (
    "Objective", "Status", "Git and files", "Work completed", "Decisions",
    "Tests", "Limitations and blockers", "Uncommitted changes",
    "Human approvals", "Next steps",
)
SOURCE_FILES = (".gitignore", ".graphifyignore", "pyproject.toml", "setup.sh", "Makefile", "AGENTS.md", "README.md")
SOURCE_DIRS = ("atmosphere", "scripts", "tests", "scenes", "docs", "tasks")
FALLBACK = "Use rg in atmosphere/, tests/, or scripts/ and verify against source."


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def task_link():
    match = re.search(r"^Active task: \[([A-Z]+-\d+)\]\(\.\./(tasks/[A-Z]+-\d+\.md)\)$",
                      HANDOFF.read_text(), re.MULTILINE)
    if not match:
        raise ValueError("HANDOFF.md must contain one active task link in the documented format")
    task_id, path = match.groups()
    if Path(path).stem != task_id:
        raise ValueError("Active task ID and path disagree")
    return task_id, ROOT / path


def input_hash():
    sha = hashlib.sha256()
    paths = [ROOT / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRS:
        paths.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".md"})
    for path in sorted(paths):
        sha.update(str(path.relative_to(ROOT)).encode() + b"\0")
        sha.update(hashlib.sha256(path.read_bytes()).digest())
    return sha.hexdigest()


def graph_status():
    try:
        stamp = json.loads(STAMP.read_text())
        present = GRAPH / "graph.json"
        if present.is_file() and stamp["inputs"] == input_hash():
            if stamp["graph"] == hashlib.sha256(present.read_bytes()).hexdigest():
                return "current for indexed source"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return "missing or stale"


def status():
    status_result = git("status", "--short", "--branch", "--untracked-files=all")
    if status_result.returncode:
        print(f"Git unavailable for this checkout: {status_result.stderr.strip()}")
    else:
        head = git("rev-parse", "--verify", "HEAD")
        print(f"HEAD: {head.stdout.strip() if head.returncode == 0 else '(unborn branch)'}")
        print(status_result.stdout.rstrip())
    task_id, path = task_link()
    text = path.read_text()
    state = re.search(r"^## Status\n\s*([^\n]+)", text, re.MULTILINE)
    print(f"Task: {task_id} ({state[1] if state else 'unknown'}) — {path.relative_to(ROOT)}")
    print(f"Graphify: {graph_status()}")
    print("Read docs/HANDOFF.md and docs/CURRENT_STATE.md before making edits.")
    return int(bool(status_result.returncode))


def check():
    required = ["AGENTS.md", "docs/ARCHITECTURE.md", "docs/MODULE_MAP.md", "docs/CURRENT_STATE.md",
                "docs/DECISIONS.md", "docs/HANDOFF.md", "docs/AGENT_SETUP.md", "tasks/TEMPLATE.md"]
    for name in required:
        if not (ROOT / name).is_file():
            raise ValueError(f"Missing {name}")
    if not list((ROOT / "docs/adr").glob("*.md")):
        raise ValueError("Missing decision records")
    task_id, path = task_link()
    files = sorted((ROOT / "tasks").glob("*.md"))
    if path not in files:
        raise ValueError(f"Missing active task file {path.name}")
    for file in files:
        text = file.read_text()
        headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
        if headings != list(SECTIONS):
            raise ValueError(f"{file.name}: task headings must match the template")
        blocks = re.split(r"^## .+$", text, flags=re.MULTILINE)[1:]
        if any(not block.strip() for block in blocks):
            raise ValueError(f"{file.name}: empty task section")
        if file.name != "TEMPLATE.md" and not text.startswith(f"# {file.stem} "):
            raise ValueError(f"{file.name}: title must start with its task ID")
    if re.findall(r"^Active task: ", HANDOFF.read_text(), re.MULTILINE) != ["Active task: "]:
        raise ValueError("HANDOFF.md must identify exactly one active task")
    print(f"Documentation and task format OK. Active task: {task_id}.")
    return 0


def graph_command(action):
    executable = os.environ.get("GRAPHIFY_BIN", "graphify")
    if action == "query":
        query = os.environ.get("Q", "").strip()
        if not query:
            raise ValueError("Set Q to a symbol or question.")
        if graph_status() != "current for indexed source":
            raise ValueError(f"Graphify cache missing or stale. Run make graph. {FALLBACK}")
        if query.startswith("-"):
            raise ValueError("Q must begin with a search term.")
        arguments = ["query", query, "--depth", "1", "--graph", str(GRAPH / "graph.json")]
    else:
        STAMP.unlink(missing_ok=True)
        before = input_hash()
        arguments = ["update", "."]
    environment = dict(os.environ, GRAPHIFY_OUT="graphify-out")
    try:
        subprocess.run([executable, *arguments], cwd=ROOT, env=environment, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"Graphify command failed: {error}. {FALLBACK}") from error
    if action == "graph":
        if before != input_hash():
            raise ValueError("Source changed during indexing. Refresh the graph again.")
        graph_hash = hashlib.sha256((GRAPH / "graph.json").read_bytes()).hexdigest()
        temp = STAMP.with_suffix(".tmp")
        temp.write_text(json.dumps({"inputs":before, "graph":graph_hash}) + "\n")
        temp.replace(STAMP)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "check", "graph", "query"])
    command = parser.parse_args().command
    try:
        if command == "status":
            return status()
        if command == "check":
            return check()
        return graph_command(command)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
