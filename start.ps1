# ═══════════════════════════════════════════════════════
#   Smart Financial Reconciliation - Startup Script
# ═══════════════════════════════════════════════════════

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Smart Financial Reconciliation" -ForegroundColor Cyan
Write-Host "  DevOps Startup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Docker Desktop ──────────────────────
Write-Host "[1/6] Checking Docker Desktop..." -ForegroundColor Yellow
$docker = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "  Please open Docker Desktop and wait for it to start, then run this script again." -ForegroundColor Red
    exit 1
}
Write-Host "  Docker Desktop is running!" -ForegroundColor Green

# ── Step 2: Start Minikube ────────────────────────────
Write-Host ""
Write-Host "[2/6] Starting Minikube..." -ForegroundColor Yellow
minikube start --driver=docker --cpus=2 --memory=4096
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Minikube failed to start!" -ForegroundColor Red
    exit 1
}
Write-Host "  Minikube started!" -ForegroundColor Green

# ── Step 3: Point Docker to Minikube ─────────────────
Write-Host ""
Write-Host "[3/6] Configuring Docker for Minikube..." -ForegroundColor Yellow
minikube docker-env --shell powershell | Invoke-Expression
Write-Host "  Docker configured!" -ForegroundColor Green

# ── Step 4: Start Monitoring Stack ───────────────────
Write-Host ""
Write-Host "[4/6] Starting Prometheus + Grafana + Monitoring..." -ForegroundColor Yellow
minikube docker-env --unset --shell powershell | Invoke-Expression 2>$null
docker rm -f prometheus grafana node-exporter cadvisor 2>$null
docker compose up -d grafana node-exporter cadvisor
docker run -d --name prometheus `
    --network financial-net `
    -p 9090:9090 `
    -v "${PWD}/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml" `
    prom/prometheus:latest
Write-Host "  Monitoring stack started!" -ForegroundColor Green

# ── Step 5: Deploy App to Kubernetes ─────────────────
Write-Host ""
Write-Host "[5/6] Deploying app to Kubernetes..." -ForegroundColor Yellow
minikube docker-env --shell powershell | Invoke-Expression
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

Write-Host "  Waiting for pods to be ready..." -ForegroundColor Yellow
kubectl rollout status deployment/financial-reconciliation -n financial-app
Write-Host "  App deployed!" -ForegroundColor Green

# ── Step 6: Show Status ───────────────────────────────
Write-Host ""
Write-Host "[6/6] Checking all status..." -ForegroundColor Yellow
Write-Host ""
Write-Host "── Kubernetes Pods ──" -ForegroundColor Cyan
kubectl get all -n financial-app
Write-Host ""
Write-Host "── Docker Containers ──" -ForegroundColor Cyan
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

# ── Done! ─────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Everything is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  App         -> opening in browser..." -ForegroundColor Cyan
Write-Host "  Prometheus  -> http://localhost:9090" -ForegroundColor Cyan
Write-Host "  Grafana     -> http://localhost:3000" -ForegroundColor Cyan
Write-Host "              -> admin / admin123" -ForegroundColor Cyan
Write-Host ""

# Open monitoring in browser
Start-Process "http://localhost:9090"
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"
Start-Sleep -Seconds 2

# Open App
Write-Host "  Opening app in browser..." -ForegroundColor Yellow
minikube service financial-reconciliation-svc -n financial-app