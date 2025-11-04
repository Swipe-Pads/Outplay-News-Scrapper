# Docker Deployment Guide

Complete guide for deploying the SwipePads News Scraper using Docker.

---

## Quick Start (2 Steps) 🚀

### 1. Configure Environment

```bash
# Create .env file with your API key
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
SCRAPER_RATE_LIMIT_SECONDS=2
LOG_LEVEL=INFO
ARTICLE_RETENTION_DAYS=30
EOF
```

### 2. Start the Scraper

```bash
# Build and start in daemon mode
docker-compose up -d

# View logs
docker-compose logs -f scraper
```

**That's it!** The scraper is now running and will:
- Scrape articles every 4 hours
- Generate AI summaries
- Export daily at 2 AM
- Clean up old data weekly

---

## Detailed Usage

### Building the Image

```bash
# Build the Docker image
docker-compose build

# Or manually
docker build -t swipepads-scraper .
```

### Running the Scheduler (Default)

```bash
# Start scheduler daemon
docker-compose up -d

# Check status
docker-compose ps

# View logs (real-time)
docker-compose logs -f scraper

# Stop
docker-compose down
```

### One-Off Commands

#### Verify System
```bash
docker-compose run --rm verify python src/verify_system.py
```

#### Manual Scrape
```bash
docker-compose run --rm scraper python src/pipeline.py --batch --limit 10 --summarize
```

#### Generate Export
```bash
docker-compose run --rm scraper python src/export_cli.py --format json --validate
```

#### View Database Stats
```bash
docker-compose run --rm scraper python -c "
from src.database import get_article_count, get_recent_articles
print(f'Total articles: {get_article_count()}')
recent = get_recent_articles(days=7)
print(f'Last 7 days: {len(recent)}')
"
```

#### Check API Costs
```bash
docker-compose run --rm scraper python src/cost_stats.py
```

#### Cleanup Old Articles
```bash
docker-compose run --rm scraper python src/cleanup.py --verify
docker-compose run --rm scraper python src/cleanup.py --articles --days 30
```

---

## Volume Mounts (Data Persistence)

Data is persisted in the following directories:

```
./data/          → Database files
./images/        → Downloaded article images
./logs/          → Application logs
./exports/       → Exported JSON/XML files
./test_data/     → Test HTML files (for fallback)
```

### Backup Data

```bash
# Backup database
cp data/articles.db data/articles.db.backup

# Or backup everything
tar -czf scraper-backup-$(date +%Y%m%d).tar.gz data/ images/ exports/
```

### Restore Data

```bash
# Stop container
docker-compose down

# Restore files
cp data/articles.db.backup data/articles.db

# Restart
docker-compose up -d
```

---

## Environment Variables

Configure in `.env` file or `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *required* | Claude API key for summarization |
| `SCRAPER_RATE_LIMIT_SECONDS` | `2` | Seconds between requests |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ARTICLE_RETENTION_DAYS` | `30` | Days to keep articles before cleanup |
| `DATABASE_PATH` | `data/articles.db` | Database file path |

---

## Monitoring

### View Logs

```bash
# Real-time logs
docker-compose logs -f scraper

# Last 100 lines
docker-compose logs --tail=100 scraper

# Since specific time
docker-compose logs --since="2025-11-04T10:00:00" scraper
```

### Health Check

```bash
# Check container health
docker-compose ps

# Manual health check
docker-compose exec scraper python -c "
from src.database import get_article_count
print(f'✅ Healthy: {get_article_count()} articles in database')
"
```

### Resource Usage

```bash
# Container stats (CPU, Memory, etc.)
docker stats swipepads-scraper

# Disk usage
docker system df
du -sh data/ images/ exports/
```

---

## Scheduler Behavior

When running `docker-compose up -d`, the scheduler:

### Automated Jobs

| Job | Frequency | Description |
|-----|-----------|-------------|
| **Scrape** | Every 4 hours | Scrapes 20 articles + AI summaries |
| **Summarize** | Daily at 1 AM | Summarizes articles without summaries |
| **Export** | Daily at 2 AM | Exports all articles to JSON |
| **Cleanup** | Weekly (Sunday 3 AM) | Removes articles >30 days old |
| **Health Check** | Every hour | Logs system status |

### Immediate Scrape on Startup

```bash
# Start scheduler and run scrape immediately
docker-compose up -d
docker-compose exec scraper python src/pipeline.py --batch --limit 20 --summarize
```

Or modify the CMD in docker-compose.yml:
```yaml
command: python src/scheduler.py --run-now
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs scraper

# Check if port is in use
docker-compose ps

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Issues

```bash
# Check database
docker-compose exec scraper python -c "
from src.database import get_article_count
print(f'Articles: {get_article_count()}')
"

# Reinitialize (WARNING: destroys data)
docker-compose down
rm data/articles.db
docker-compose up -d
```

### API Key Not Working

```bash
# Check environment variables
docker-compose exec scraper env | grep ANTHROPIC

# Test API connection
docker-compose exec scraper python -c "
from src.summarizer import test_connection
test_connection()
"
```

### Out of Memory

Increase memory limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 1G  # Increase from 512M
```

### 403 Errors (HTTP Blocks)

If getting 403 errors:
1. Container uses fallback HTML files automatically
2. Test in non-Docker environment first
3. Check if your network/ISP blocks the site
4. Consider using VPN or proxy

---

## Production Deployment

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml scraper

# Check services
docker stack services scraper

# View logs
docker service logs -f scraper_scraper
```

### Using Kubernetes

Create `k8s-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: swipepads-scraper
spec:
  replicas: 1
  selector:
    matchLabels:
      app: scraper
  template:
    metadata:
      labels:
        app: scraper
    spec:
      containers:
      - name: scraper
        image: swipepads-scraper:latest
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: scraper-data
```

### Environment-Specific Configs

```bash
# Development
docker-compose -f docker-compose.yml up

# Production
docker-compose -f docker-compose.prod.yml up -d

# Staging
docker-compose -f docker-compose.staging.yml up -d
```

---

## Best Practices

### Security

1. **Never commit `.env`** - It's in `.gitignore`
2. **Use secrets for API keys**:
   ```bash
   # Docker secrets
   echo "sk-ant-..." | docker secret create anthropic_key -
   ```
3. **Run as non-root** - Already configured (user: scraper)
4. **Limit resources** - Configure CPU/memory limits

### Performance

1. **Volume mounts** - Use for better I/O performance
2. **Resource limits** - Prevent container from consuming all resources
3. **Log rotation** - Configure in `docker-compose.yml`:
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

### Maintenance

1. **Regular backups** - Automate database backups
2. **Monitor disk space** - Images can accumulate
3. **Update images** - Rebuild periodically
4. **Check logs** - Monitor for errors

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build image
        run: docker build -t swipepads-scraper .

      - name: Run tests
        run: |
          docker run --rm \
            -e ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }} \
            swipepads-scraper \
            python src/verify_system.py

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag swipepads-scraper myregistry/swipepads-scraper:latest
          docker push myregistry/swipepads-scraper:latest
```

---

## Useful Commands

```bash
# Shell access
docker-compose exec scraper bash

# Check Python version
docker-compose exec scraper python --version

# List installed packages
docker-compose exec scraper pip list

# Run interactive Python
docker-compose exec scraper python

# Copy files out
docker cp swipepads-scraper:/app/data/articles.db ./backup.db

# Copy files in
docker cp config.py swipepads-scraper:/app/src/

# Restart without rebuild
docker-compose restart scraper

# Rebuild and restart
docker-compose up -d --build
```

---

## Cost Estimates (Docker)

**Resource Usage**:
- CPU: ~5-10% average (spikes during scraping)
- Memory: 200-400 MB
- Disk: ~100 MB + articles/images

**Cloud Hosting**:
- DigitalOcean Droplet: $6/month (1GB RAM)
- AWS ECS Fargate: ~$10/month
- Google Cloud Run: ~$5/month
- Azure Container Instances: ~$8/month

**API Costs** (separate):
- ~$5/month for typical usage

**Total**: ~$11-15/month for fully automated system

---

## Quick Reference

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f scraper

# Status
docker-compose ps

# Restart
docker-compose restart scraper

# Update and restart
docker-compose up -d --build

# Shell access
docker-compose exec scraper bash

# Run command
docker-compose exec scraper python src/export_cli.py --format json

# Cleanup
docker-compose down -v  # Warning: deletes volumes
```

---

**Last Updated**: 2025-11-04
**Docker Version**: 20.10+
**Docker Compose Version**: 2.0+
