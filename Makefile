.PHONY: help build run stop clean test lint deploy delete status logs setup

IMAGE_NAME = financial-reconciliation
TAG        = latest
NAMESPACE  = financial-app

help:  ## Show all commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Docker ────────────────────────────────────────────
build:  ## Build Docker image
	docker build -t $(IMAGE_NAME):$(TAG) .

run:  ## Run app with Docker Compose
	docker compose up -d

stop:  ## Stop Docker Compose
	docker compose down

logs:  ## View container logs
	docker compose logs -f app

clean:  ## Remove containers and images
	docker compose down --rmi all --volumes --remove-orphans

# ── Code Quality ──────────────────────────────────────
lint:  ## Run linting
	flake8 src/ tests/ --max-line-length=100
	black --check src/ tests/
	isort --check-only src/ tests/

format:  ## Auto format code
	black src/ tests/
	isort src/ tests/

test:  ## Run tests
	pytest tests/ -v --cov=src --cov-report=term-missing

# ── Minikube ──────────────────────────────────────────
minikube-start:  ## Start Minikube
	minikube start --driver=docker --cpus=2 --memory=4096

minikube-load:  ## Load image into Minikube
	minikube image load $(IMAGE_NAME):$(TAG)

minikube-enable-ingress:  ## Enable Nginx Ingress
	minikube addons enable ingress

# ── Kubernetes ────────────────────────────────────────
deploy:  ## Deploy to Kubernetes
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	kubectl apply -f k8s/ingress.yaml
	kubectl apply -f k8s/hpa.yaml
	kubectl rollout status deployment/financial-reconciliation -n $(NAMESPACE)

delete:  ## Delete all K8s resources
	kubectl delete -f k8s/ --ignore-not-found

status:  ## Check pod status
	kubectl get all -n $(NAMESPACE)

pod-logs:  ## View pod logs
	kubectl logs -l app=financial-reconciliation -n $(NAMESPACE) --tail=50 -f

# ── Monitoring ────────────────────────────────────────
monitoring-up:  ## Start Prometheus + Grafana
	docker compose up -d prometheus grafana
	@echo "Prometheus → http://localhost:9090"
	@echo "Grafana    → http://localhost:3000"
	@echo "Grafana login → admin / admin123"

monitoring-down:  ## Stop monitoring
	docker compose stop prometheus grafana

# ── Full Setup ────────────────────────────────────────
setup: minikube-start build minikube-load minikube-enable-ingress deploy  ## Full local setup
	@echo ""
	@echo "✅ App is running!"
	@echo "Access → http://$$(minikube ip):30001"