#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# VIGIL — démarrage tout-en-un (serveur + agent local)
# Usage :
#   ./start.sh            → serveur seul
#   ./start.sh agent      → serveur + agent local (test/démo)
#   ./start.sh stop       → arrête serveur et agent
# ─────────────────────────────────────────────────────────────
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

start() {
  if ss -tln 2>/dev/null | grep -q ":5000 "; then
    echo "✅ Serveur déjà en cours sur le port 5000"
  else
    echo "🚀 Démarrage du serveur VIGIL…"
    cd "$ROOT/server"
    setsid nohup .venv/bin/python server.py --skip-config-prompt \
      > /tmp/vigil_server.log 2>&1 < /dev/null &
    sleep 3
    if curl -sf http://localhost:5000/health > /dev/null; then
      echo "✅ Serveur démarré → http://localhost:5000"
    else
      echo "❌ Le serveur n'a pas répondu — voir /tmp/vigil_server.log"
      exit 1
    fi
  fi
}

start_agent() {
  if pgrep -f "agent\.py" > /dev/null; then
    echo "✅ Agent déjà en cours"
  else
    echo "🤖 Démarrage de l'agent local…"
    cd "$ROOT/agent"
    setsid nohup .venv/bin/python agent.py \
      > /tmp/vigil_agent.log 2>&1 < /dev/null &
    sleep 2
    echo "✅ Agent lancé (log : /tmp/vigil_agent.log)"
  fi
}

stop_all() {
  pkill -f "server\.py --skip-config-prompt" 2>/dev/null && echo "🛑 Serveur arrêté"
  pkill -f "agent\.py" 2>/dev/null && echo "🛑 Agent arrêté"
  exit 0
}

case "${1:-}" in
  stop) stop_all ;;
  agent) start; start_agent ;;
  *) start ;;
esac

echo ""
echo "📊 Dashboard  : http://localhost:5000"
echo "📝 Logs       : /tmp/vigil_server.log  /tmp/vigil_agent.log"
