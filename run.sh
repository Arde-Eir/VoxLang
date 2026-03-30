#!/usr/bin/env bash
# ── Utter / VoxLang – Start Script ────────────────────────────────────────────
# Works on:  macOS · Linux · Windows (Git Bash / MSYS2 / WSL)
#
# Usage:
#   bash run.sh                 start on default port 8000
#   bash run.sh --port 9000    use a custom port
#   bash run.sh --no-reload    disable hot-reload (production mode)

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Parse args ────────────────────────────────────────────────────────────────
PORT=8000
RELOAD_FLAG="--reload --reload-dir backend --reload-dir shared --reload-dir frontend"

for arg in "$@"; do
  case $arg in
    --port=*)    PORT="${arg#*=}" ;;
    --port)      shift; PORT="$1" ;;
    --no-reload) RELOAD_FLAG="" ;;
  esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
R='\033[0;31m' Y='\033[0;33m' G='\033[0;32m' C='\033[0;36m' B='\033[1;34m'
W='\033[1;37m' D='\033[2m' N='\033[0m'

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="unknown"
case "$(uname -s 2>/dev/null)" in
  Darwin*)              OS="mac" ;;
  Linux*)               OS="linux" ;;
  CYGWIN*|MINGW*|MSYS*) OS="windows" ;;
esac
# Also catch native Windows where uname might not exist
[ "$OS" = "unknown" ] && OS="windows"

# ── Detect Python ─────────────────────────────────────────────────────────────
# Try common executable names; skip the Windows Store stub (returns exit 1 on version check)
PY=""
for cmd in python3 python py python3.12 python3.11 python3.10 python3.9; do
  if command -v "$cmd" >/dev/null 2>&1; then
    if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
      PY="$cmd"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo ""
  echo -e "${R}✗  Python 3.8+ was not found on your system.${N}"
  echo ""
  if [ "$OS" = "mac" ]; then
    echo -e "${W}  macOS – install Python:${N}"
    echo ""
    echo "  Option A  Homebrew (recommended):"
    echo "    brew install python"
    echo ""
    echo "  Option B  Official installer:"
    echo "    https://www.python.org/downloads/macos/"
    echo ""
    echo "  Option C  pyenv (version manager):"
    echo "    brew install pyenv"
    echo "    pyenv install 3.12"
    echo "    pyenv global 3.12"
  elif [ "$OS" = "windows" ]; then
    echo -e "${W}  Windows – install Python:${N}"
    echo ""
    echo "  Option A  Official installer (recommended):"
    echo "    https://www.python.org/downloads/windows/"
    echo "    ✔ Check 'Add Python to PATH' during install"
    echo ""
    echo "  Option B  winget:"
    echo "    winget install Python.Python.3.12"
    echo ""
    echo "  Option C  Microsoft Store (easiest, but disable the stub alias first):"
    echo "    Settings → Apps → Advanced app settings → App execution aliases"
    echo "    → turn OFF the python / python3 Store shortcuts, then install from Store"
  else
    echo -e "${W}  Linux – install Python:${N}"
    echo ""
    echo "  Ubuntu / Debian:  sudo apt install python3 python3-pip"
    echo "  Fedora:           sudo dnf install python3 python3-pip"
    echo "  Arch:             sudo pacman -S python python-pip"
  fi
  echo ""
  echo "  After installing, re-open your terminal and run:  bash run.sh"
  echo ""
  exit 1
fi

PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo -e "${D}  Python $PY_VER  ($PY)${N}"

# ── .env check ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    echo -e "${Y}⚠  No .env found — copying from .env.example…${N}"
    cp .env.example .env
    echo -e "${D}   Open .env and fill in your API keys, then re-run: bash run.sh${N}"
  else
    echo -e "${Y}⚠  No .env file found.${N}"
    echo    "   Create one with at least:"
    echo    "     GROQ_API_KEY=your_key_here"
    echo    "     DEEPGRAM_API_KEY=your_key_here"
  fi
  exit 1
fi

# ── Python deps ───────────────────────────────────────────────────────────────
MISSING=()
for pkg in fastapi uvicorn pydantic groq deepgram; do
  "$PY" -c "import ${pkg//-/_}" 2>/dev/null || MISSING+=("$pkg")
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo -e "${Y}📦  Installing missing packages: ${MISSING[*]}…${N}"
  "$PY" -m pip install -r requirements.txt --quiet
  echo -e "${G}    Done.${N}"
fi

# ── Port in use? ──────────────────────────────────────────────────────────────
port_in_use() {
  # lsof works on mac/linux; use Python socket fallback on Windows
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti:"$1" >/dev/null 2>&1
  else
    "$PY" -c "
import socket, sys
s = socket.socket()
try:
    s.bind(('0.0.0.0', int(sys.argv[1])))
    s.close(); sys.exit(1)   # free
except OSError:
    sys.exit(0)              # in use
" "$1" 2>/dev/null
  fi
}

if port_in_use "$PORT"; then
  echo -e "${Y}⚠  Port $PORT is already in use.${N}"
  echo ""
  if [ "$OS" = "mac" ] || [ "$OS" = "linux" ]; then
    echo -e "   Find the process:  ${W}lsof -i :$PORT${N}"
    echo -e "   Kill it:           ${W}lsof -ti:$PORT | xargs kill -9${N}"
  else
    echo -e "   Find the process:  ${W}netstat -ano | findstr :$PORT${N}"
    echo -e "   Kill it:           ${W}taskkill /PID <PID> /F${N}"
  fi
  echo -e "   Or use a different port:  ${W}bash run.sh --port=9000${N}"
  echo ""
  exit 1
fi

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${B}  ██╗   ██╗ ██████╗ ██╗  ██╗██╗      █████╗ ███╗   ██╗ ██████╗ ${N}"
echo -e "${B}  ██║   ██║██╔═══██╗╚██╗██╔╝██║     ██╔══██╗████╗  ██║██╔════╝ ${N}"
echo -e "${B}  ██║   ██║██║   ██║ ╚███╔╝ ██║     ███████║██╔██╗ ██║██║  ███╗${N}"
echo -e "${B}  ╚██╗ ██╔╝██║   ██║ ██╔██╗ ██║     ██╔══██║██║╚██╗██║██║   ██║${N}"
echo -e "${B}   ╚████╔╝ ╚██████╔╝██╔╝ ██╗███████╗██║  ██║██║ ╚████║╚██████╔╝${N}"
echo -e "${B}    ╚═══╝   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ${N}"
echo ""
echo -e "${W}  VoxLang — Voice-First Programming Language${N}"
echo -e "${D}  ────────────────────────────────────────────────────────────${N}"
echo -e "  ${G}▶  IDE      ${N}→  ${C}http://localhost:${PORT}${N}"
echo -e "  ${G}▶  Reference${N}→  ${C}http://localhost:${PORT}/reference${N}"
echo -e "  ${G}▶  API docs ${N}→  ${C}http://localhost:${PORT}/docs${N}"
echo -e "${D}  ────────────────────────────────────────────────────────────${N}"
if [ "$OS" = "mac" ]; then
  echo -e "  ${D}Platform: macOS${N}"
elif [ "$OS" = "windows" ]; then
  echo -e "  ${D}Platform: Windows (Git Bash / MSYS2)${N}"
else
  echo -e "  ${D}Platform: Linux${N}"
fi
[ -n "$RELOAD_FLAG" ] && echo -e "  ${D}Hot-reload: ON  (--no-reload to disable)${N}" \
                      || echo -e "  ${Y}Hot-reload: OFF${N}"
echo ""

# ── Launch ────────────────────────────────────────────────────────────────────
# shellcheck disable=SC2086
exec "$PY" -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  $RELOAD_FLAG