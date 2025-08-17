

# ---------------------------------------------------------------------------
# Universal Makefile
# Supports: python · java · csharp · cpp
# ---------------------------------------------------------------------------
# -------------------------------
# Configuration
# -------------------------------
APP_NAME             := market-data-api
IMG                  := $(APP_NAME):local

PORT                 := 8000
DOCKER_COMPOSE_FILE  ?= docker-compose.yml
REDIS_NAME           ?= redis
KAFKA_NAME           ?= kafka
KIND_NAME            ?= dev

LINT_CMD             := pip install -q ruff black && ruff src tests && black --check src tests
TEST_CMD             := pip install -q pytest && pytest -q

.PHONY: help build-app app-up redis-up build run-dev clean \
        init-kind destroy-kind init-colima destroy-colima \
        status logs-app skaffold-dev skaffold-deploy-test \
        skaffold-deploy skaffold-stop wait-healthy

# -------------------------------
# Help
# -------------------------------
help:
	@echo "🛠️  Available targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?#' Makefile | \
	  awk 'BEGIN {FS = ":.*?#"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------
# Local
# --------------------------------------------------------------
local-up: ## Start Redis & Kafka containers for local uncontainerized dev
	@echo "🚀 Starting containers for: Redis"
	docker-compose up -d redis
	@echo "✅ Services are up! Ready for local development."

local-down: ## Stop and remove local dev containers
	@echo "🛑 Stopping local dev services..."
	docker-compose down

# Multi-API Development
# -------------------------------
run: ## Run the Market Data API Platform (Multi-API Mode - Default)
	@echo "🚀 Starting Market Data API Platform (Multi-API Mode)..."
	@echo "📚 Single Swagger UI with API selector dropdown:"
	@echo "   - Swagger UI: http://localhost:$(PORT)/market-data-api/docs"
	@echo "   - Use dropdown in top right to switch between APIs"
	@echo "   - Market Data API: Financial data and market intelligence"
	@echo "   - Utils API: System performance and monitoring"
	@echo "   - Root Info: http://localhost:$(PORT)/"
	@echo ""
	python -m src.app.main

run-single-api: ## Run the single API version (legacy mode)
	@echo "🚀 Starting Market Data API (Legacy Single API Mode)..."
	@echo "📚 API Documentation: http://localhost:$(PORT)/market-data-api/docs"
	@echo ""
	python -m src.app.main

# --------------------------------------------------------------
# Docker
# --------------------------------------------------------------
# Application
# -------------------------------
build-app: # Build only the app service
	@echo "🏗️ Building app service only..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) build $(APP_NAME)

app-up: # Start only the app service
	@echo "🚀 Starting the app service..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d $(APP_NAME)




# -------------------------------
# Redis Service
# -------------------------------
redis-up: # Start the Redis service
	@echo "🚀 Starting the Redis service..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d $(REDIS_NAME)


# -------------------------------
# Services + Application
# -------------------------------
run-dev: redis-up app-up wait-healthy # Start all active services and the app

build: # Build all Docker services
	@echo "🏗️ Building all Docker services..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) build

clean: # Stop all services and clean up Docker Compose resources
	@echo "🛑 Stopping all services..."
	docker-compose down --volumes
	@echo "✅ System cleaned up."

# -------------------------------
# Healthcheck Waiter
# -------------------------------
wait-healthy: # Wait until all services are healthy
	@echo "⏳ Waiting for services to become healthy..."
	@until [ "$$(docker inspect --format='json .State.Health.Status' $$(docker-compose ps -q $(APP_NAME)) 2>/dev/null | grep -c healthy)" -eq 1 ]; do \
		echo "Waiting on $(APP_NAME)..."; sleep 2; \
	done
	@echo "✅ All services are healthy."

# -------------------------------
# Kubernetes Cluster Management
# -------------------------------
init-kind: # Initialize the Kind cluster
	@echo "⚙️ Creating Kubernetes cluster with kind (name: '$(KIND_NAME)')..."
	kind create cluster --name $(KIND_NAME)
	@echo "✅ Kubernetes cluster '$(KIND_NAME)' has been created successfully!"

destroy-kind: # Destroy the Kind cluster
	@echo "🔥 Destroying Kind cluster..."
	kind delete cluster --name $(KIND_NAME) || true
	@echo "✅ Kind cluster destroyed."

# -------------------------------
# Colima Management
# -------------------------------
init-colima: # Start the Colima runtime
	@echo "🚀 Starting Colima runtime..."
	colima start
	@echo "✅  Colima runtime started successfully!"

destroy-colima: # Stop the Colima runtime
	colima stop
	@echo "✅  All infrastructure has been successfully destroyed!"
	@echo "✅ Colima runtime stopped."

# --------------------------------------------------------------
# Skaffold-based Commands
# --------------------------------------------------------------
skaffold-dev: # Start Skaffold in dev mode (with hot reload)
	@echo "🚀 Starting Skaffold in development mode (hot-reload enabled)..."
	skaffold dev -p dev

skaffold-deploy-test: # Deploy test profile with Skaffold
	@echo "🚀 Deploying application via Skaffold..."
	skaffold apply -p test

skaffold-deploy: # Deploy prod profile with Skaffold
	@echo "🚀 Deploying application via Skaffold..."
	skaffold apply -p prod

skaffold-stop: # Tear down all resources managed by Skaffold
	@echo "🛑 Stopping all resources deployed via Skaffold..."
	skaffold delete
	@echo "✅ Resources cleaned up."

# -------------------------------
# Utility Commands
# -------------------------------
status: # Show Kubernetes pod statuses
	@echo "👀 Showing Kubernetes pod statuses..."
	kubectl get pods -A

logs-app: # Tail logs for app service (in Kubernetes)
	@echo "📄 Tailing logs for app..."
	kubectl logs -f $$(kubectl get pods -l app=$(APP_NAME) -o name | head -n1)

logs-docker-app: ## Tail logs for app service (Docker Compose)
	@echo "📄 Tailing logs for $(APP_NAME)..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) logs -f $(APP_NAME)

shell: ## Open shell inside app container
	docker-compose -f $(DOCKER_COMPOSE_FILE) exec $(APP_NAME) sh || docker exec -it $(APP_NAME) sh

lint: ## Language-specific lint
	$(LINT_CMD)

test: ## Language-specific test
	$(TEST_CMD)

ci: lint test build ## Lint, test, then build (for CI pipeline)
