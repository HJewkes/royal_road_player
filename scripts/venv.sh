#!/usr/bin/env bash
# venv.sh — the one place that decides which Python venv the project runs on.
#
# Preference: $AUDIOBOOK_VENV, else venv-cu128 (Linux CUDA, `make setup-cuda`),
# else venv311 (the Mac, `make setup`).
#
#   source scripts/venv.sh; audiobook_venv_dir "$PROJECT_DIR"   # prints the venv dir
#   bash scripts/venv.sh main.py ...                            # runs its python
#
# Sourcing never fails, even with no venv on disk: autopull.sh sources this at
# load time and its tests do so on a bare CI runner. With nothing found it names
# venv311, so a missing venv surfaces where the interpreter is actually used.

audiobook_venv_dir() {
  local root="$1" name
  case "${AUDIOBOOK_VENV:-}" in
    "") ;;
    /*) echo "$AUDIOBOOK_VENV"; return 0 ;;
    *) echo "$root/$AUDIOBOOK_VENV"; return 0 ;;
  esac
  for name in venv-cu128 venv311; do
    if [ -x "$root/$name/bin/python" ]; then
      echo "$root/$name"
      return 0
    fi
  done
  echo "$root/venv311"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  python="$(audiobook_venv_dir "$root")/bin/python"
  if [ ! -x "$python" ]; then
    echo "venv.sh: no interpreter at $python; run 'make setup-cuda' (Linux) or 'make setup' (Mac)" >&2
    exit 1
  fi
  exec "$python" "$@"
fi
