from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claude_md_exists():
    assert (ROOT / "CLAUDE.md").is_file()


def test_env_is_ignored():
    gitignore = (ROOT / ".gitignore").read_text()
    assert ".env" in gitignore
