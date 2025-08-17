#!/bin/bash

# Simple deployment script for Market Data API with Redis

set -e

echo "🚀 Deploying Market Data API with Redis to production..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if helm is available
if ! command -v helm &> /dev/null; then
    echo "❌ helm is not installed. Please install helm first."
    exit 1
fi

# Set namespace (change this to your production namespace)
NAMESPACE="market-data-api"
RELEASE_NAME="market-data-api"

echo "📋 Using namespace: $NAMESPACE"
echo "📋 Release name: $RELEASE_NAME"

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "🔍 Checking current deployment..."

# Check if release exists
if helm list -n $NAMESPACE | grep -q $RELEASE_NAME; then
    echo "📦 Upgrading existing release..."
    helm upgrade $RELEASE_NAME ./chart -n $NAMESPACE
else
    echo "📦 Installing new release..."
    helm install $RELEASE_NAME ./chart -n $NAMESPACE
fi

echo "⏳ Waiting for deployment to be ready..."

# Wait for Redis to be ready
echo "🔴 Waiting for Redis to be ready..."
kubectl wait --for=condition=ready pod -l app=$RELEASE_NAME-redis -n $NAMESPACE --timeout=300s

# Wait for main app to be ready
echo "🟢 Waiting for main application to be ready..."
kubectl wait --for=condition=ready pod -l app=$RELEASE_NAME -n $NAMESPACE --timeout=300s

echo "✅ Deployment complete!"
echo ""
echo "📊 Check status with:"
echo "   kubectl get pods -n $NAMESPACE"
echo "   kubectl get services -n $NAMESPACE"
echo ""
echo "🔍 Check logs with:"
echo "   kubectl logs -f deployment/$RELEASE_NAME -n $NAMESPACE"
echo "   kubectl logs -f deployment/$RELEASE_NAME-redis -n $NAMESPACE"
echo ""
echo "🌐 Access your API:"
echo "   kubectl port-forward service/$RELEASE_NAME 8000:8000 -n $NAMESPACE"
