import os
from pathlib import Path
from shutil import which

from invoke import task

PKG_NAME = "seagull"
PKG_PATH = Path(PKG_NAME)
DOCS_PORT = int(os.environ.get("DOCS_PORT", "8000"))
BIN_DIR = "bin" if os.name != "nt" else "Scripts"
PTY = os.name != "nt"
ACTIVE_VENV = os.environ.get("VIRTUAL_ENV", None)
VENV_HOME = Path(os.environ.get("WORKON_HOME", "~/virtualenvs"))
VENV_PATH = Path(ACTIVE_VENV) if ACTIVE_VENV else (VENV_HOME / PKG_NAME)
VENV = str(VENV_PATH.expanduser())
VENV_BIN = Path(VENV) / Path(BIN_DIR)
THEME_DIR = PKG_PATH / "themes/simple/"

TOOLS = ["pdm", "pre-commit", "psutil", "Babel"]
PDM = which("pdm") or VENV_BIN / "pdm"
PRECOMMIT = which("pre-commit") or VENV_BIN / "pre-commit"


@task
def tests(c):
    """Run the test suite"""
    c.run(f"{VENV_BIN}/pytest", pty=PTY)


@task
def coverage(c):
    """Generate code coverage of running the test suite."""
    c.run(
        f"{VENV_BIN}/pytest --cov=seagull --cov-report term-missing "
        "--cov-fail-under 75",
        pty=PTY,
    )
    c.run(f"{VENV_BIN}/coverage html", pty=PTY)


@task
def formatcode(c, check=False, diff=False):
    """Run Ruff's auto-formatter, optionally with --check or --diff"""
    check_flag, diff_flag = "", ""
    if check:
        check_flag = "--check"
    if diff:
        diff_flag = "--diff"
    c.run(
        f"{VENV_BIN}/ruff format {check_flag} {diff_flag} {PKG_PATH} tasks.py", pty=PTY
    )


@task
def ruff(c, fix=False, diff=False):
    """Run Ruff to ensure code meets project standards."""
    diff_flag, fix_flag = "", ""
    if fix:
        fix_flag = "--fix"
    if diff:
        diff_flag = "--diff"
    c.run(f"{VENV_BIN}/ruff check {diff_flag} {fix_flag} .", pty=PTY)


@task
def lint(c, fix=False, diff=False):
    """Check code style via linting tools."""
    ruff(c, fix=fix, diff=diff)
    formatcode(c, check=not fix, diff=diff)


@task
def tools(c):
    """Install tools in the virtual environment if not already on PATH"""
    for tool in TOOLS:
        if not which(tool):
            c.run(f"{VENV_BIN}/python -m pip install {tool}", pty=PTY)


@task
def precommit(c):
    """Install pre-commit hooks to .git/hooks/pre-commit"""
    c.run(f"{PRECOMMIT} install", pty=PTY)


@task
def setup(c):
    c.run(f"{VENV_BIN}/python -m pip install -U pip", pty=PTY)
    tools(c)
    c.run(f"{PDM} install", pty=PTY)
    precommit(c)

@task
def themepot(c):
    """Extract all messages from templates and create `messages.pot`."""
    c.run(f"{VENV_BIN}/pybabel extract -s --no-wrap "
          f"--project=\"seagull\" "
          f"--mapping={THEME_DIR / "translations/babel.cfg"} "
          f"--output={THEME_DIR / "translations/messages.pot"} "
          f"{THEME_DIR}")

@task
def updatetrans(c):
    """Update all translations based on `messages.pot`."""
    c.run(f"{VENV_BIN}/pybabel update --no-wrap "
          f"--input-file {THEME_DIR / "translations/messages.pot"} "
          f"--output-dir {THEME_DIR / "translations/"} "
          f"--domain messages")

@task
def newtrans(c, lang):
    """Create a new translation for the base theme."""
    c.run(f"{VENV_BIN}/pybabel init --no-wrap "
          f"--input-file {THEME_DIR / "translations/messages.pot"} "
          f"--output-dir {THEME_DIR / "translations/"} "
          f"--locale {lang} "
          f"--domain messages")

@task
def compiletrans(c):
    """Compile translations."""
    c.run(f"{VENV_BIN}/pybabel compile -f "
          f"--directory {THEME_DIR / "translations/"} "
          f"--domain messages")
