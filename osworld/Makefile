.PHONY: help build push deploy login build-push test logs status

# Include common Makefile functions
-include ../common/Makefile.common

# Default values
IMAGE_REPO ?= ghcr.io/hyperboliclabs/osworld
IMAGE_TAG ?= latest
NAMESPACE ?= inference-benchmark
KUBECONFIG ?= $(HOME)/hyperbolic/yoofi-cluster.yml
OSWORLD_VERSION ?= main

# Build configuration
DOCKER_PLATFORM ?= linux/amd64
DOCKER_BUILDX ?= docker buildx

# GitHub Container Registry authentication
GITHUB_USER ?= hyperboliclabs

# Full image name
IMAGE := $(IMAGE_REPO):$(IMAGE_TAG)

help: ## Show this help message
	$(call show-help,"OSWorld Evaluation")
	@echo ""
	@echo "OSWorld-specific:"
	@echo "  OSWORLD_VERSION  OSWorld git branch/tag (default: main)"

build: ## Build the Docker image
	@echo "Building Docker image: $(IMAGE)"
	@echo "Platform: $(DOCKER_PLATFORM)"
	@echo "OSWorld Version: $(OSWORLD_VERSION)"
	@$(DOCKER_BUILDX) build \
		--platform $(DOCKER_PLATFORM) \
		-f osworld/Dockerfile \
		--build-arg OSWORLD_VERSION=$(OSWORLD_VERSION) \
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

deploy: ## Deploy the evaluation job to Kubernetes
	@echo "Deploying PVC (if not exists)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f pvc.yaml || echo "PVC may already exist"
	@echo "Deploying OSWorld evaluation job to namespace $(NAMESPACE)..."
	@kubectl --kubeconfig=$(KUBECONFIG) apply -f osworld-job.yaml
	@echo "✅ Evaluation job deployed"

test: deploy ## Deploy and wait for evaluation job to complete
	@echo "Waiting for evaluation job to complete..."
	@echo "Note: OSWorld evaluations can take a long time (hours)"
	@kubectl --kubeconfig=$(KUBECONFIG) wait --for=condition=complete --timeout=7200s job/osworld -n $(NAMESPACE) || true
	@echo ""
	@echo "=== Evaluation Logs ==="
	@kubectl --kubeconfig=$(KUBECONFIG) logs -n $(NAMESPACE) -l app=osworld,component=evaluation --tail=200

logs: ## Show logs from the evaluation job
	@kubectl --kubeconfig=$(KUBECONFIG) logs -n $(NAMESPACE) -l app=osworld,component=evaluation --tail=100 -f

status: ## Show status of evaluation job
	@kubectl --kubeconfig=$(KUBECONFIG) get job osworld -n $(NAMESPACE) -o wide

.DEFAULT_GOAL := help
