#!/usr/bin/env bash
# One-time secret provisioner for tower-ha-discovery.
# Run manually: [MQTT_USER=x MQTT_PASSWORD=y] ./scripts/create-secret.sh
# Never run from an agent — token would leak into conversation context.
set -euo pipefail

NAMESPACE=home-assistant
SECRET_NAME=tower-ha-discovery

if kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" &>/dev/null; then
    echo "Secret '$SECRET_NAME' already exists in namespace '$NAMESPACE'. Nothing to do."
    exit 0
fi

MQTT_USER="${MQTT_USER:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"

if [[ -z "$MQTT_USER" ]]; then
    read -rp "MQTT username (leave empty if broker needs no auth): " MQTT_USER
fi
if [[ -n "$MQTT_USER" && -z "$MQTT_PASSWORD" ]]; then
    read -rsp "MQTT password: " MQTT_PASSWORD; echo
fi

API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
    --from-literal=MQTT_USER="$MQTT_USER" \
    --from-literal=MQTT_PASSWORD="$MQTT_PASSWORD" \
    --from-literal=API_TOKEN="$API_TOKEN"

echo ""
echo "Secret created. Store this API_TOKEN securely (e.g. in Bitwarden):"
echo "  API_TOKEN=${API_TOKEN}"
echo ""
echo "This is the only time it will be displayed."
