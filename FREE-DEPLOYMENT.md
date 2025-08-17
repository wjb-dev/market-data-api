# 🆓 Free Deployment Guide

## Quick Start - Choose Your Free Service

Run the deployment script to get started:
```bash
./deploy-free.sh
```

## 🐳 Option 1: Local Docker Compose (Easiest)

**Deploy locally for free:**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**Benefits:**
- ✅ Completely free
- ✅ Runs on your machine
- ✅ Full control
- ✅ No external dependencies

**Access:**
- API: http://localhost:8000
- Redis: localhost:6379

## 🚂 Option 2: Railway (Recommended)

**Free tier:** 500 hours/month

**Deploy:**
1. Install CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Deploy: `railway up`

**Benefits:**
- ✅ Very easy deployment
- ✅ Automatic Redis provisioning
- ✅ Good free tier
- ✅ Built-in monitoring

## 🎨 Option 3: Render

**Free tier:** 750 hours/month

**Deploy:**
1. Go to [render.com](https://render.com)
2. Create account
3. Create new Web Service
4. Connect your GitHub repo
5. Add Redis service

**Benefits:**
- ✅ Generous free tier
- ✅ Automatic deployments
- ✅ Built-in Redis
- ✅ Good documentation

## ✈️ Option 4: Fly.io

**Free tier:** 3 shared-cpu-1x 256mb VMs

**Deploy:**
1. Install CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Deploy: `fly deploy`

**Benefits:**
- ✅ Global edge deployment
- ✅ Good performance
- ✅ Redis support
- ✅ Generous free tier

## 🦸 Option 5: Heroku

**Free tier:** 550-1000 dyno hours/month

**Deploy:**
1. Install CLI: [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Login: `heroku login`
3. Create app: `heroku create your-app-name`
4. Add Redis: `heroku addons:create heroku-redis:hobby-dev`

**Benefits:**
- ✅ Very reliable
- ✅ Excellent Redis integration
- ✅ Good free tier
- ✅ Extensive add-ons

## 🔧 Environment Variables

Make sure to set these in your free service:

```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET=your_secret_here
REDIS_ENABLED=true
REDIS_URL=your_redis_url_here
SERVICE_NAME=market-data-api
ENVIRONMENT=production
```

## 📊 Monitoring Your Free Deployment

**Check status:**
```bash
# Local
docker-compose -f docker-compose.production.yml ps

# Railway
railway status

# Render
# Check dashboard at render.com

# Fly.io
fly status

# Heroku
heroku ps
```

**View logs:**
```bash
# Local
docker-compose -f docker-compose.production.yml logs -f

# Railway
railway logs

# Render
# Check dashboard

# Fly.io
fly logs

# Heroku
heroku logs --tail
```

## 🚨 Free Tier Limitations

- **Railway:** 500 hours/month, sleep after inactivity
- **Render:** 750 hours/month, sleep after inactivity  
- **Fly.io:** 3 VMs, 256MB each
- **Heroku:** 550-1000 hours/month, sleep after inactivity

## 💡 Pro Tips

1. **Start with local deployment** to test everything works
2. **Use Railway** for easiest cloud deployment
3. **Monitor your usage** to stay within free limits
4. **Set up health checks** to ensure your app stays running
5. **Use environment variables** for sensitive data

## 🆘 Need Help?

- **Local issues:** Check Docker logs
- **Railway:** `railway --help`
- **Render:** Check their docs
- **Fly.io:** `fly help`
- **Heroku:** `heroku help`
