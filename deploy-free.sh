#!/bin/bash

# Free deployment script for Market Data API with Redis

set -e

echo "🚀 Deploying Market Data API with Redis for FREE!"

echo "📋 Choose your free deployment option:"
echo "1) Local Docker Compose (Free, runs on your machine)"
echo "2) Railway (Free tier: 500 hours/month)"
echo "3) Render (Free tier: 750 hours/month)"
echo "4) Fly.io (Free tier: 3 shared-cpu-1x 256mb VMs)"
echo "5) Heroku (Free tier: 550-1000 dyno hours/month)"

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "🐳 Deploying locally with Docker Compose..."
        docker-compose -f docker-compose.production.yml up -d
        echo "✅ Local deployment complete!"
        echo "🌐 Your API is running at: http://localhost:8000"
        echo "🔴 Redis is running at: localhost:6379"
        echo ""
        echo "📊 Check status: docker-compose -f docker-compose.production.yml ps"
        echo "🔍 View logs: docker-compose -f docker-compose.production.yml logs -f"
        ;;
    2)
        echo "🚂 Deploying to Railway..."
        echo "📝 Make sure you have Railway CLI installed: npm i -g @railway/cli"
        echo "📝 Login to Railway: railway login"
        echo "📝 Then run: railway up"
        ;;
    3)
        echo "🎨 Deploying to Render..."
        echo "📝 Create account at: https://render.com"
        echo "📝 Create a new Web Service and Redis service"
        echo "📝 Use the docker-compose.production.yml as reference"
        ;;
    4)
        echo "✈️ Deploying to Fly.io..."
        echo "📝 Install Fly CLI: curl -L https://fly.io/install.sh | sh"
        echo "📝 Login: fly auth login"
        echo "📝 Deploy: fly deploy"
        ;;
    5)
        echo "🦸 Deploying to Heroku..."
        echo "📝 Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli"
        echo "📝 Login: heroku login"
        echo "📝 Create app: heroku create your-app-name"
        echo "📝 Add Redis: heroku addons:create heroku-redis:hobby-dev"
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "🔗 Free Service Links:"
echo "   Railway: https://railway.app"
echo "   Render: https://render.com"
echo "   Fly.io: https://fly.io"
echo "   Heroku: https://heroku.com"
