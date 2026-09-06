#!/bin/bash
# Appelle un outil du serveur MCP local cTrader.
#   ./ct.sh get_trendbars '{"symbolName":"XAUUSD","timeframe":"m1","from":"2026-08-25T09:00:00Z","to":"2026-08-25T10:00:00Z"}'
#
# Prérequis : cTrader ouvert, Paramètres > Serveur MCP > « Enable MCP Server » coché.
# NE JAMAIS appeler un outil préfixé amend_ / place_ / close_ / cancel_ : ils agissent.
U=http://127.0.0.1:9876/mcp/
ARGS="$2"; [ -z "$ARGS" ] && ARGS='{}'
H=$(mktemp)
curl -s -D "$H" -o /dev/null "$U" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
 -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"jt","version":"1.0"}}}'
SID=$(grep -i '^mcp-session-id:' "$H" | tr -d '\r' | awk '{print $2}')
curl -s "$U" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' ${SID:+-H "Mcp-Session-Id: $SID"} \
 -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
curl -s "$U" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' ${SID:+-H "Mcp-Session-Id: $SID"} \
 -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$ARGS}}"
echo
