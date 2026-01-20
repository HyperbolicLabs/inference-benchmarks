.PHONY: help build push deploy login build-push create-secret deploy-job test

# Include common Makefile functions
-include ../common/Makefile.common

# Default values
IMAGE_REPO ?= ghcr.io/hyperboliclabs/aiperf
IMAGE_TAG ?= latest
NAMESPACE ?= inference-benchmark
KUBECONFIG ?= $(HOME)/hyperbolic/yoofi-cluster.yml

# Build configuration
DOCKER_PLATFORM ?= linux/amd64
DOCKER_BUILDX ?= docker buildx

# GitHub Container Registry authentication
GITHUB_USER ?= hyperboliclabs

# Full image name
IMAGE := $(IMAGE_REPO):$(IMAGE_TAG)

help: ## Show this help message
	$(call show-help,"AIPerf Benchmark")
	@echo ""
	@echo "Benchmark-specific:"
	@echo "  create-secret    Create Kubernetes secret for Cloudflare Access"

build: ## Build the Docker image
	@echo "Building Docker image: $(IMAGE)"
	@echo "Platform: $(DOCKER_PLATFORM)"
	@$(DOCKER_BUILDX) build \
		--platform $(DOCKER_PLATFORM) \
		-f aiperf/Dockerfile \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		-t $(IMAGE) \
		.
	@echo "✅ Image built successfully: $(IMAGE)"

login: ## Login to GitHub Container Registry
	$(call docker-login)

push: build ## Build and push the Docker image
	$(call push-image)

build-push: login push ## Login, build and push the Docker image
	@echo "✅ Build and push complete"

create-secret: ## Create Kubernetes secret for Cloudflare Access credentials
	@echo "Creating Cloudflare Access credentials secret..."
	@echo "Usage: make create-secret CLIENT_ID=xxx CLIENT_SECRET=yyy"
	@if [ -z "$(CLIENT_ID)" ] || [ -z "$(CLIENT_SECRET)" ]; then \
		echo "Error: CLIENT_ID and CLIENT_SECRET are required"; \
		echo "Usage: make create-secret CLIENT_ID=xxx CLIENT_SECRET=yyy [NAMESPACE=inference-benchmark]"; \
		exit 1; \
	fi
	@kubectl --kubeconfig=$(KUBECONFIG) create secret generic cloudflare-access-credentials \
		--from-literal=client-id="$(CLIENT_ID)" \
		--from-literal=client-secret="$(CLIENT_SECRET)" \
		-n $(NAMESPACE) --dry-run=client -o yaml | \
		kubectl --kubeconfig=$(KUBECONFIG) apply -f -

deploy: ## Deploy the CronJob to Kubernetes
	@echo "Deploying PVC (if not exists)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f pvc.yaml || echo "PVC may already exist"
	@echo "Deploying CronJob to namespace $(NAMESPACE)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f cronjob.yaml
	@echo "✅ CronJob deployed"

deploy-job: ## Deploy a one-time Job (for manual testing)
	@echo "Deploying PVC (if not exists)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f pvc.yaml || echo "PVC may already exist"
	@echo "Deploying Job to namespace $(NAMESPACE)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f job.yaml
	@echo "✅ Job deployed"

test: deploy-job ## Deploy Job and wait for completion
	@echo "Waiting for job to complete..."
	@kubectl --kubeconfig=$(KUBECONFIG) wait --for=condition=complete --timeout=600s job/aiperf-benchmark -n $(NAMESPACE) || true
	@echo ""
	@echo "=== Job Logs ==="
	@kubectl --kubeconfig=$(KUBECONFIG) logs -n $(NAMESPACE) -l app=aiperf --tail=100

.DEFAULT_GOAL := help
