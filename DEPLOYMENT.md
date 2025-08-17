# Market Data API Deployment Guide

## Quick Deploy to Production

### Prerequisites
- `kubectl` installed and configured for your production cluster
- `helm` installed
- Access to your production Kubernetes cluster

### Simple Deployment

1. **Deploy everything with one command:**
   ```bash
   ./deploy.sh
   ```

   This script will:
   - Create the namespace `market-data-api`
   - Deploy Redis with persistent storage
   - Deploy your Market Data API
   - Wait for all services to be ready
   - Show you how to access your API

### Manual Deployment

If you prefer to deploy manually:

1. **Create namespace:**
   ```bash
   kubectl create namespace market-data-api
   ```

2. **Deploy with Helm:**
   ```bash
   helm install market-data-api ./chart -n market-data-api
   ```

3. **Check status:**
   ```bash
   kubectl get pods -n market-data-api
   kubectl get services -n market-data-api
   ```

### What Gets Deployed

- **Redis**: 
  - Persistent storage (1GB)
  - Memory limit: 256MB
  - Health checks enabled
  
- **Market Data API**:
  - Connects to Redis automatically
  - Health checks on `/healthz`
  - Waits for Redis to be ready before starting

### Configuration

Edit `chart/values.yaml` to customize:
- Redis resources
- Storage size
- Environment variables
- Replica count

### Troubleshooting

**Check Redis logs:**
```bash
kubectl logs -f deployment/market-data-api-redis -n market-data-api
```

**Check API logs:**
```bash
kubectl logs -f deployment/market-data-api -n market-data-api
```

**Test Redis connection:**
```bash
kubectl exec -it deployment/market-data-api-redis -n market-data-api -- redis-cli ping
```

**Access your API:**
```bash
kubectl port-forward service/market-data-api 8000:8000 -n market-data-api
```

Then visit: http://localhost:8000
