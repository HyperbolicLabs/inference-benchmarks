#!/usr/bin/env bash
# Create the Kubernetes secret holding Cloudflare Access credentials.
#
# Usage:
#   CLIENT_ID=... CLIENT_SECRET=... ./create-secret.sh [NAMESPACE]
#   ./create-secret.sh [NAMESPACE]        # prompts for both values
#
# Credentials are read from the environment or prompted for. They are
# deliberately NOT accepted as command-line arguments: every process on the host
# can read another process's argv (`ps auxww`), and the shell records the command
# — including the secret — in its history file.

# `-u` makes an unset variable a fatal error instead of an empty string (the old
# script would happily create a secret with an empty value), and `pipefail` means
# a failure in `kubectl create ... | kubectl apply` is not masked by the exit
# status of the last stage.
set -euo pipefail

# The old signature was `create-secret.sh CLIENT_ID CLIENT_SECRET [NAMESPACE]`.
# Now that the namespace is the first argument, silently accepting three
# arguments would create a namespace named after a client ID, so refuse instead
# and say what changed.
if [ "$#" -gt 1 ]; then
    echo "Error: credentials are no longer passed as arguments (they leak via 'ps' and shell history)." >&2
    echo "Usage: CLIENT_ID=... CLIENT_SECRET=... $0 [NAMESPACE]" >&2
    exit 2
fi

NAMESPACE="${1:-inference-benchmark}"
SECRET_NAME="cloudflare-access-credentials"
CREDENTIALS_FILE="${CLOUDFLARE_CREDENTIALS_FILE:-cloudflare-access-credentials.env}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Cloudflare Access Credentials Secret Setup${NC}"

CLIENT_ID="${CLIENT_ID:-}"
CLIENT_SECRET="${CLIENT_SECRET:-}"

# A credentials file is still supported, but it is *parsed* rather than sourced.
# `source` executes the file as shell script, so anything that could write to it
# — or a stray backtick in a pasted value — ran with the privileges of whoever
# ran this script. Only `KEY=value` lines for the two expected keys are read.
if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    for candidate in "$CREDENTIALS_FILE" "../../$CREDENTIALS_FILE" \
        "cloudflare-access-credentials.txt" "../../cloudflare-access-credentials.txt"; do
        if [ -f "$candidate" ]; then
            echo -e "${BLUE}Loading credentials from ${candidate}${NC}"
            while IFS='=' read -r key value; do
                case "$key" in
                    CLIENT_ID) [ -z "$CLIENT_ID" ] && CLIENT_ID="$value" ;;
                    CLIENT_SECRET) [ -z "$CLIENT_SECRET" ] && CLIENT_SECRET="$value" ;;
                esac
            done < "$candidate"
            break
        fi
    done
fi

# `read -s` keeps the value off the screen and out of scrollback.
if [ -z "$CLIENT_ID" ]; then
    read -r -p "Cloudflare Access Client ID: " CLIENT_ID
fi
if [ -z "$CLIENT_SECRET" ]; then
    read -r -s -p "Cloudflare Access Client Secret: " CLIENT_SECRET
    echo ""
fi

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}Error: CLIENT_ID and CLIENT_SECRET are both required${NC}" >&2
    exit 1
fi

echo -e "${BLUE}Creating Kubernetes secret...${NC}"
echo -e "  Namespace:   ${YELLOW}${NAMESPACE}${NC}"
echo -e "  Secret name: ${YELLOW}${SECRET_NAME}${NC}"
# The client ID's first 20 characters used to be echoed here. A partial
# credential is still a credential once it reaches a shared terminal or CI log,
# and it narrows a brute-force search considerably, so nothing is printed.

if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    echo -e "${YELLOW}Namespace '${NAMESPACE}' does not exist. Creating it...${NC}"
    kubectl create namespace "$NAMESPACE"
fi

# The previous version deleted the secret and then created it again. Between the
# two calls the secret did not exist, so any pod that started (or restarted) in
# that window came up without credentials; and if the create failed, the cluster
# was left with no secret at all. `apply` from a client-side manifest is a single
# atomic update and is safe to re-run.
kubectl create secret generic "$SECRET_NAME" \
    --from-literal=client-id="$CLIENT_ID" \
    --from-literal=client-secret="$CLIENT_SECRET" \
    -n "$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo -e "${GREEN}Secret ${SECRET_NAME} created/updated in ${NAMESPACE}${NC}"
echo ""
# Verification confirms the keys exist without decoding their values; the old
# `base64 -d | head -c 20` printed the beginning of the real client ID.
echo -e "${BLUE}Keys present in the secret:${NC}"
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{range $k, $v := .data}{$k}{"\n"}{end}'
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. The CronJob picks the secret up automatically on its next run."
echo "  2. Inspect it with: kubectl get secret ${SECRET_NAME} -n ${NAMESPACE}"
echo "  3. Check CronJob logs: kubectl logs -n ${NAMESPACE} -l app=aiperf --tail=50"
echo ""
