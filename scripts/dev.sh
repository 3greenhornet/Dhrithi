#!/usr/bin/env bash
# Convenience runners for development on this repository.
set -e
cd "$(dirname "$0")/.."

case "${1:-help}" in
  test)
    find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
    python3 -m unittest discover -s tests ;;
  demo)
    python3 examples/demo/run_demo.py "${@:2}" ;;
  cli)
    shift
    python3 -m dhriti.cli "$@" ;;
  smoke)
    # real-clock CLI smoke test in a throwaway home
    TMPHOME=$(mktemp -d)
    export DHRITI_HOME="$TMPHOME"
    python3 -m dhriti.cli init
    python3 -m dhriti.cli status
    python3 -m dhriti.cli adapter status
    python3 -m dhriti.cli verify
    unset DHRITI_HOME
    rm -rf "$TMPHOME"
    echo "smoke: OK" ;;
  *)
    echo "usage: scripts/dev.sh {test|demo|cli ...|smoke}" ;;
esac
