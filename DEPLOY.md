# SwipePads News Scraper - Deployment Guide

**Version**: 1.0
**Last Updated**: 2026-01-28
**Target Audience**: Development Team

---

## 📋 Prerequisites

Before deploying, ensure you have:

### Required
- [ ] **Docker** (version 20.10+) and **docker-compose** (version 1.29+)
  ```bash
  docker --version
  docker-compose --version
  ```

- [ ] **Server/VPS** with:
  - Minimum: 1 CPU, 1GB RAM, 5GB storage
  - Recommended: 2 CPU, 2GB RAM, 10GB storage
  - OS: Linux (Ubuntu 20.04+ or similar)

- [ ] **Anthropic API Key** for AI summarization
  - Get key from: https://console.anthropic.com/
  - Free tier: $5 credit (sufficient for testing)
  - Production cost: ~$5/month

### Optional
- [ ] Domain name (for accessing via custom URL)
- [ ] SSL certificate (if not using Docker proxy)
- [ ] Monitoring service (DataDog, New Relic, etc.)

---

## 🚀 Quick Deployment (Docker - Recommended)

### Step 1: Clone Repository

```bash
# SSH method (if you have SSH keys configured)
git clone git@github.com:waligorskim/Outplay-News-Scrapper.git
cd Outplay-News-Scrapper

# OR HTTPS method
git clone https://github.com/waligorskim/Outplay-News-Scrapper.git
cd Outplay-News-Scrapper
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.docker.example .env

# Edit with your API key
nano .env  # or vim, or any text editor
```

**Required `.env` configuration:**
```bash
# CRITICAL: Replace with your actual API key
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ACTUAL_KEY_HERE

# Optional: Adjust these if needed
SCRAPER_RATE_LIMIT_SECONDS=2
DATABASE_PATH=data/articles.db
LOG_LEVEL=INFO
ARTICLE_RETENTION_DAYS=30
```

### Step 3: Deploy with Docker Compose

**Development/Testing:**
```bash
docker-compose up -d
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Step 4: Verify Deployment

```bash
# Check container status
docker-compose ps

# Watch logs (Ctrl+C to exit)
docker-compose logs -f scraper

# Check health
docker-compose exec scraper python src/verify_system.py
```

**Expected output:**
```
✅ ALL TESTS PASSED
Total tests: 19
✅ Passed: 19
```

### Step 5: Monitor First Run

```bash
# Follow logs for first scrape cycle
docker-compose logs -f scraper

# Wait ~5-15 minutes for first scrape
# You should see: "Processing article: https://..."
```

---

## 🎯 Alternative Deployment (Manual)

If you prefer not to use Docker:

### Step 1: Setup Python Environment

```bash
# Install Python 3.11+ if not available
python3 --version  # Should be 3.11 or higher

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env with your API key (same as Docker method)
```

### Step 3: Initialize Database

```bash
python -c "from src.database import init_db; init_db()"
```

### Step 4: Test System

```bash
# Run verification
python src/verify_system.py

# Test single scrape (will fail if no internet/HTTP allowed)
python src/pipeline.py --batch --limit 3
```

### Step 5: Start Scheduler

```bash
# Foreground (for testing)
python src/scheduler.py

# Background (production)
nohup python src/scheduler.py > logs/scheduler.out 2>&1 &
echo $! > scheduler.pid  # Save process ID
```

### Step 6: Setup as System Service (Linux)

Create `/etc/systemd/system/swipepads-scraper.service`:

```ini
[Unit]
Description=SwipePads News Scraper
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/Outplay-News-Scrapper
Environment="PATH=/path/to/Outplay-News-Scrapper/venv/bin"
ExecStart=/path/to/Outplay-News-Scrapper/venv/bin/python src/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable swipepads-scraper
sudo systemctl start swipepads-scraper
sudo systemctl status swipepads-scraper
```

---

## 🔍 Verification Checklist

After deployment, verify these items:

### 1. Container/Service Running
```bash
# Docker:
docker-compose ps
# Expected: "Up" status

# Manual:
ps aux | grep scheduler
# Expected: Process running
```

### 2. Database Initialized
```bash
# Docker:
docker-compose exec scraper ls -la data/articles.db

# Manual:
ls -la data/articles.db
```

### 3. First Scrape Successful
```bash
# Docker:
docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"

# Manual:
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"

# Expected: Number > 0 after first run
```

### 4. Exports Generated
```bash
# Docker:
docker-compose exec scraper ls -la exports/

# Manual:
ls -la exports/

# Expected: JSON/XML files after first export job (runs at 2 AM)
```

### 5. Logs Being Written
```bash
# Docker:
docker-compose logs scraper | tail -20

# Manual:
tail -20 logs/scraper.log

# Expected: Recent log entries
```

---

## 📊 Monitoring & Maintenance

### Check System Status

**Docker:**
```bash
# Quick status
docker-compose ps

# Full logs
docker-compose logs scraper | tail -100

# Resource usage
docker stats
```

**Manual:**
```bash
# Process status
ps aux | grep scheduler

# Log files
tail -f logs/scraper.log

# Database size
du -h data/articles.db
```

### View Scraped Articles

```bash
# Docker:
docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"

# Manual:
sqlite3 data/articles.db "SELECT title, date FROM articles ORDER BY scraped_at DESC LIMIT 10;"
```

### Check API Costs

```bash
# Docker:
docker-compose exec scraper python src/cost_stats.py

# Manual:
python src/cost_stats.py
```

### Manual Operations

```bash
# Export articles
docker-compose exec scraper python src/export_cli.py --format json --validate

# Summarize unsummarized articles
docker-compose exec scraper python src/summarize_cli.py --all

# Run cleanup manually
docker-compose exec scraper python src/cleanup.py --days 30 --verify
```

---

## 🔄 Updates & Maintenance

### Update Application

```bash
# Pull latest changes
git pull origin main

# Docker: Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Manual: Restart service
sudo systemctl restart swipepads-scraper
```

### Backup Database

```bash
# Docker:
docker-compose exec scraper sqlite3 data/articles.db ".backup /app/data/backup.db"
docker cp swipepads-scraper:/app/data/backup.db ./backup-$(date +%Y%m%d).db

# Manual:
sqlite3 data/articles.db ".backup data/backup-$(date +%Y%m%d).db"
```

### Restore Database

```bash
# Docker:
docker-compose down
docker cp backup-20260128.db swipepads-scraper:/app/data/articles.db
docker-compose up -d

# Manual:
cp backup-20260128.db data/articles.db
sudo systemctl restart swipepads-scraper
```

---

## 🐛 Troubleshooting

### Container Won't Start

**Symptom:** `docker-compose up` fails or container exits immediately

**Solutions:**
1. Check logs: `docker-compose logs scraper`
2. Verify `.env` file exists and has valid API key
3. Check port conflicts: `docker-compose ps`
4. Remove old containers: `docker-compose down -v && docker-compose up -d`

### No Articles Being Scraped

**Symptom:** Database remains empty after several hours

**Solutions:**
1. Check scraper logs: `docker-compose logs scraper | grep -i error`
2. Verify internet connectivity: `docker-compose exec scraper ping -c 3 pocketgamer.com`
3. Check if site is accessible: `curl -I https://www.pocketgamer.com/news/`
4. Manually trigger scrape: `docker-compose exec scraper python src/pipeline.py --batch --limit 3`

### API Rate Limit Errors

**Symptom:** "RateLimitError" in logs

**Solutions:**
1. Wait 60 seconds and retry
2. Check API usage: `docker-compose exec scraper python src/cost_stats.py`
3. Verify API key is valid: Check console.anthropic.com
4. Reduce scraping frequency in docker-compose.yml (change scrape interval)

### High Memory Usage

**Symptom:** Container using >500MB RAM

**Solutions:**
1. Check number of articles: `docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"`
2. Run cleanup: `docker-compose exec scraper python src/cleanup.py --days 30`
3. Restart container: `docker-compose restart scraper`

### Exports Not Generating

**Symptom:** No files in exports/ directory

**Solutions:**
1. Check scheduler is running: `docker-compose ps`
2. Check export job schedule: Runs daily at 2 AM
3. Manually trigger export: `docker-compose exec scraper python src/export_cli.py --format json`
4. Check disk space: `df -h`

---

## 📈 Scaling & Performance

### Increase Scraping Frequency

Edit `docker-compose.yml` or `docker-compose.prod.yml`:

```yaml
environment:
  - SCRAPER_INTERVAL_HOURS=2  # Default: 4
```

Restart: `docker-compose restart scraper`

### Add More Games/Sources

Currently scrapes Pocket Gamer. To add more sources:
1. Modify `src/scraper.py` to add new source URLs
2. Update `src/parser.py` for new HTML structures
3. Test with: `python src/pipeline.py --url "NEW_URL"`

### Horizontal Scaling

For multiple scraper instances:
1. Use separate databases per instance
2. Coordinate via shared task queue (Redis/RabbitMQ)
3. Load balance with Nginx

---

## 🔒 Security Best Practices

### 1. API Key Protection
- ✅ Never commit `.env` to git
- ✅ Use environment variables, not hardcoded keys
- ✅ Rotate API keys periodically
- ✅ Use read-only keys if available

### 2. Network Security
- ✅ Run container as non-root user (already configured)
- ✅ Limit exposed ports (only expose if necessary)
- ✅ Use firewall rules to restrict access
- ✅ Keep Docker and dependencies updated

### 3. Data Protection
- ✅ Regular database backups
- ✅ Secure backup storage
- ✅ Encrypt sensitive data at rest
- ✅ Implement retention policies (30 days default)

---

## 📞 Support & Resources

### Documentation
- **README.md** - Project overview and quick start
- **DOCKER_GUIDE.md** - Comprehensive Docker documentation
- **COMPLETION_SUMMARY.md** - Feature completion status
- **HANDOFF.md** - Project handoff information

### Useful Commands
```bash
# View all Make commands (if using Makefile)
make help

# Docker Compose shortcuts
docker-compose up -d     # Start
docker-compose down      # Stop
docker-compose logs -f   # View logs
docker-compose ps        # Status
docker-compose restart   # Restart
```

### Common Locations
- **Database**: `data/articles.db`
- **Images**: `images/YYYY-MM-DD/`
- **Exports**: `exports/articles_YYYYMMDD_HHMMSS.{json,xml}`
- **Logs**: `logs/scraper.log`, `logs/api_costs.json`

### Getting Help
1. Check logs first: `docker-compose logs scraper`
2. Run verification: `docker-compose exec scraper python src/verify_system.py`
3. Review troubleshooting section above
4. Check GitHub issues
5. Contact development team

---

## 📝 Post-Deployment Checklist

After deployment, complete the [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md).

---

## ✅ Success Criteria

Your deployment is successful when:

- [ ] Container/service running for 24+ hours without crashes
- [ ] At least 20 articles scraped
- [ ] All articles have AI summaries
- [ ] Exports generated successfully
- [ ] Cleanup job ran without errors
- [ ] API costs tracking properly
- [ ] No critical errors in logs

---

**Questions?** Review [HANDOFF.md](HANDOFF.md) for additional information.

**Need help?** Contact the development team or check project documentation.
