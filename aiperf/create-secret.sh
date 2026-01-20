#!/bin/bash
# Create Kubernetes secret for Cloudflare Access credentials
# Usage: ./create-secret.sh [CLIENT_ID] [CLIENT_SECRET] [NAMESPACE]

set -e

# Default values
NAMESPACE="${3:-inference-benchmark}"
SECRET_NAME="cloudflare-access-credentials"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Cloudflare Access Credentials Secret Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get credentials
if [ -n "$1" ] && [ -n "$2" ]; then
    CLIENT_ID="$1"
    CLIENT_SECRET="$2"
    echo -e "${GREEN}✅ Using provided credentials${NC}"
elif [ -f "cloudflare-access-credentials.txt" ]; then
    echo -e "${BLUE}📋 Loading credentials from cloudflare-access-credentials.txt${NC}"
    source cloudflare-access-credentials.txt
    CLIENT_ID="$CLIENT_ID"
    CLIENT_SECRET="$CLIENT_SECRET"
elif [ -f "../../cloudflare-access-credentials.txt" ]; then
    echo -e "${BLUE}📋 Loading credentials from ../../cloudflare-access-credentials.txt${NC}"
    source ../../cloudflare-access-credentials.txt
    CLIENT_ID="$CLIENT_ID"
    CLIENT_SECRET="$CLIENT_SECRET"
else
    echo -e "${YELLOW}⚠️  No credentials provided${NC}"
    echo ""
    echo "Usage:"
    echo "  $0 CLIENT_ID CLIENT_SECRET [NAMESPACE]"
    echo ""
    echo "Or set environment variables:"
    echo "  export CLIENT_ID='your-client-id'"
    echo "  export CLIENT_SECRET='your-client-secret'"
    echo "  $0"
    echo ""
    echo "Or create cloudflare-access-credentials.txt with:"
    echo "  CLIENT_ID=your-client-id"
    echo "  CLIENT_SECRET=your-client-secret"
    exit 1
fi

# Validate credentials
if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}❌ Error: CLIENT_ID and CLIENT_SECRET are required${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Creating Kubernetes secret...${NC}"
echo -e "  Namespace: ${YELLOW}$NAMESPACE${NC}"
echo -e "  Secret name: ${YELLOW}$SECRET_NAME${NC}"
echo -e "  Client ID: ${YELLOW}${CLIENT_ID:0:20}...${NC}"
echo ""

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Namespace '$NAMESPACE' does not exist. Creating it...${NC}"
    kubectl create namespace "$NAMESPACE"
    echo -e "${GREEN}✅ Namespace created${NC}"
fi

# Delete existing secret if it exists
if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Secret '$SECRET_NAME' already exists. Updating it...${NC}"
    kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE"
fi

# Create the secret
kubectl create secret generic "$SECRET_NAME" \
    --from-literal=client-id="$CLIENT_ID" \
    --from-literal=client-secret="$CLIENT_SECRET" \
    -n "$NAMESPACE"

echo ""
echo -e "${GREEN}✅ Secret created successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Verification:${NC}"
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.client-id}' | base64 -d | head -c 20 && echo "..."
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📝 Next Steps:${NC}"
echo "  1. The CronJob will automatically use this secret"
echo "  2. Verify with: kubectl get secret $SECRET_NAME -n $NAMESPACE"
echo "  3. Check CronJob logs: kubectl logs -n $NAMESPACE -l app=aiperf --tail=50"
echo ""
