#!/bin/bash
# Create Kubernetes secret for api.hyperbolic.xyz API key (benchmarks).
# Usage: OPENAI_API_KEY=your-key ./create-api-key-secret.sh [NAMESPACE]
#   or:  HYPERBOLIC_API_KEY=your-key ./create-api-key-secret.sh [NAMESPACE]
# Never commit the key to the repo; use env var or paste when prompted.

set -e

NAMESPACE="${1:-inference-benchmark}"
SECRET_NAME="hyperbolic-api-key"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

API_KEY="${OPENAI_API_KEY:-${HYPERBOLIC_API_KEY:-}}"
if [ -z "$API_KEY" ]; then
    echo -e "${YELLOW}OPENAI_API_KEY / HYPERBOLIC_API_KEY not set. Paste API key (then Ctrl+D):${NC}"
    API_KEY=$(cat)
fi
if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ No API key provided${NC}"
    echo "Usage: OPENAI_API_KEY=your-key $0 [NAMESPACE]"
    exit 1
fi

echo -e "${BLUE}Creating secret ${SECRET_NAME} in namespace ${NAMESPACE}...${NC}"

if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${YELLOW}Namespace '$NAMESPACE' does not exist. Creating it...${NC}"
    kubectl create namespace "$NAMESPACE"
fi

kubectl create secret generic "$SECRET_NAME" \
    --from-literal=api-key="$API_KEY" \
    -n "$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✅ Secret ${SECRET_NAME} created/updated in ${NAMESPACE}${NC}"
echo "   CronJob will use it for api.hyperbolic.xyz auth."
