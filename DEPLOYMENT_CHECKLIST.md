# SwipePads News Scraper - Deployment Checklist

**Purpose**: Ensure all prerequisites and steps are completed before and after deployment
**Date**: _____________
**Deployed By**: _____________

---

## Pre-Deployment Checklist

### 1. Environment Setup

- [ ] **Server/VPS provisioned**
  - Minimum: 1 CPU, 1GB RAM, 5GB storage
  - OS: Linux (Ubuntu 20.04+ recommended)
  - SSH access confirmed

- [ ] **Docker installed and running**
  ```bash
  docker --version  # Should be 20.10+
  docker-compose --version  # Should be 1.29+
  ```

- [ ] **Git installed**
  ```bash
  git --version
  ```

- [ ] **Network connectivity verified**
  ```bash
  ping -c 3 github.com
  ping -c 3 www.pocketgamer.com
  curl -I https://api.anthropic.com
  ```

### 2. API Keys & Credentials

- [ ] **Anthropic API key obtained**
  - Source: https://console.anthropic.com/
  - Key format: `sk-ant-api03-...`
  - Credits available: $______

- [ ] **API key tested**
  ```bash
  # Test with curl (replace YOUR_KEY)
  curl https://api.anthropic.com/v1/messages \
    -H "x-api-key: YOUR_KEY" \
    -H "anthropic-version: 2023-06-01"
  ```

- [ ] **`.env` file configured**
  - File created from `.env.docker.example`
  - `ANTHROPIC_API_KEY` set
  - Other variables reviewed and adjusted if needed

### 3. Repository Setup

- [ ] **Repository cloned**
  ```bash
  git clone https://github.com/waligorskim/Outplay-News-Scrapper.git
  cd Outplay-News-Scrapper
  ```

- [ ] **On correct branch**
  ```bash
  git branch  # Should show main or production branch
  ```

- [ ] **Latest changes pulled**
  ```bash
  git pull origin main
  ```

- [ ] **All required files present**
  - [ ] `Dockerfile`
  - [ ] `docker-compose.yml`
  - [ ] `docker-compose.prod.yml`
  - [ ] `.env.docker.example`
  - [ ] `requirements.txt`
  - [ ] `src/` directory with all modules

### 4. Configuration Review

- [ ] **Scraping interval appropriate** (default: 4 hours)
  - Adjust in `docker-compose.yml` if needed
  - Consider server load and API costs

- [ ] **Retention period set** (default: 30 days)
  - Check `.env` file: `ARTICLE_RETENTION_DAYS=30`

- [ ] **Log level configured** (default: INFO)
  - For production: `LOG_LEVEL=INFO`
  - For debugging: `LOG_LEVEL=DEBUG`

- [ ] **Rate limiting configured** (default: 2 seconds)
  - Check `.env` file: `SCRAPER_RATE_LIMIT_SECONDS=2`

---

## Deployment Checklist

### 5. Build & Start

- [ ] **Docker images built successfully**
  ```bash
  # Development:
  docker-compose build

  # Production:
  docker-compose -f docker-compose.prod.yml build
  ```
  - No build errors
  - All dependencies installed

- [ ] **Containers started**
  ```bash
  # Development:
  docker-compose up -d

  # Production:
  docker-compose -f docker-compose.prod.yml up -d
  ```
  - Container status: "Up"
  - No immediate crashes

- [ ] **Health check passing**
  ```bash
  docker-compose ps
  ```
  - Health status: "healthy" (after 60 seconds)

### 6. Initial Verification

- [ ] **System verification passed**
  ```bash
  docker-compose exec scraper python src/verify_system.py
  ```
  - Output: `✅ ALL TESTS PASSED`
  - 19/19 tests passed
  - Only warnings about API key (if placeholder) acceptable

- [ ] **Database initialized**
  ```bash
  docker-compose exec scraper ls -la data/articles.db
  ```
  - File exists
  - Has read/write permissions

- [ ] **Directories created**
  ```bash
  docker-compose exec scraper ls -la
  ```
  - `data/` exists
  - `images/` exists
  - `logs/` exists
  - `exports/` exists

- [ ] **Logs being written**
  ```bash
  docker-compose logs scraper | tail -20
  ```
  - Recent log entries visible
  - No critical errors

### 7. Functional Testing

- [ ] **Scheduler running**
  ```bash
  docker-compose logs scraper | grep -i "scheduled"
  ```
  - 5 jobs scheduled:
    - Scrape job (every 4 hours)
    - Export job (daily at 2 AM)
    - Cleanup job (weekly Sunday at 3 AM)
    - Summarize job (daily at 1 AM)
    - Health check (hourly)

- [ ] **First scrape attempted** (wait 5-15 minutes)
  ```bash
  docker-compose logs scraper | grep -i "processing article"
  ```
  - Articles being processed
  - No HTTP 403 errors (only in Claude Code environment)

- [ ] **Articles in database** (after first scrape)
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
  ```
  - Count > 0
  - Expected: 10-20 articles after first run

- [ ] **Images downloaded** (after first scrape)
  ```bash
  docker-compose exec scraper ls -la images/
  ```
  - Date-based folders created (e.g., `2026-01-28/`)
  - Image files present (`.jpg`, `.png`, `.webp`)

- [ ] **AI summaries generated** (after first scrape)
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles WHERE summary IS NOT NULL;"
  ```
  - Count matches total articles
  - All articles have summaries

---

## Post-Deployment Checklist (24-48 hours)

### 8. Monitoring & Stability

- [ ] **Container uptime verified**
  ```bash
  docker-compose ps
  ```
  - Container running for 24+ hours
  - No restarts (unless scheduled maintenance)

- [ ] **Multiple scrape cycles completed**
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT COUNT(*) FROM articles;"
  ```
  - Expected: 50-100+ articles after 24 hours
  - New articles added each cycle

- [ ] **No critical errors in logs**
  ```bash
  docker-compose logs scraper | grep -i error | grep -v "404\|expected"
  ```
  - No database errors
  - No API connection errors
  - No unhandled exceptions

- [ ] **Resource usage acceptable**
  ```bash
  docker stats --no-stream
  ```
  - Memory: < 500MB (typically 200-300MB)
  - CPU: < 50% average
  - Disk: Check with `df -h`

### 9. Data Quality

- [ ] **Articles have complete data**
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT title, author, date FROM articles LIMIT 5;"
  ```
  - All fields populated
  - Dates are recent
  - Content is mobile gaming news

- [ ] **Summaries are relevant**
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT title, summary FROM articles LIMIT 3;"
  ```
  - Summaries are 200-300 characters
  - 3-5 bullet points
  - Relevant to article content

- [ ] **No duplicate articles**
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db "SELECT url, COUNT(*) as count FROM articles GROUP BY url HAVING count > 1;"
  ```
  - No results (all URLs unique)

- [ ] **Images successfully downloaded**
  ```bash
  docker-compose exec scraper find images/ -type f | wc -l
  ```
  - Count matches article count (approximately)
  - Files are valid images (not 404 pages)

### 10. Exports & API Costs

- [ ] **Exports generated** (after first export job at 2 AM)
  ```bash
  docker-compose exec scraper ls -la exports/
  ```
  - JSON files present
  - XML files present
  - Timestamped filenames

- [ ] **Exports are valid**
  ```bash
  docker-compose exec scraper python src/export_cli.py --format json --validate
  ```
  - Validation passes
  - JSON is well-formed
  - XML is well-formed

- [ ] **API costs tracked**
  ```bash
  docker-compose exec scraper python src/cost_stats.py
  ```
  - Cost log exists: `logs/api_costs.json`
  - Total cost reasonable (~$0.10-0.20 per day)
  - Per-article cost ~$0.002

- [ ] **API costs within budget**
  - Daily cost: $______
  - Monthly projected: $______
  - Within budget: ☐ Yes ☐ No

### 11. Cleanup & Retention

- [ ] **Cleanup job configured**
  ```bash
  docker-compose logs scraper | grep -i "cleanup"
  ```
  - Job scheduled (weekly on Sunday at 3 AM)
  - Retention period: 30 days (or as configured)

- [ ] **Manual cleanup test**
  ```bash
  docker-compose exec scraper python src/cleanup.py --days 30 --verify
  ```
  - No errors
  - Old articles identified (if any)
  - Orphaned images detected (if any)

---

## Security & Backup Checklist

### 12. Security Review

- [ ] **`.env` file not committed to git**
  ```bash
  git status
  ```
  - `.env` in `.gitignore`
  - Not staged for commit

- [ ] **API key not exposed in logs**
  ```bash
  docker-compose logs scraper | grep -i "api.*key"
  ```
  - No API key visible in plaintext logs

- [ ] **Container running as non-root**
  ```bash
  docker-compose exec scraper whoami
  ```
  - Output: `scraper` (not `root`)

- [ ] **Only necessary ports exposed**
  ```bash
  docker-compose ps
  ```
  - No unnecessary port mappings

### 13. Backup Strategy

- [ ] **Database backup tested**
  ```bash
  docker-compose exec scraper sqlite3 data/articles.db ".backup /app/data/backup.db"
  docker cp <container-id>:/app/data/backup.db ./backup-test.db
  ```
  - Backup file created
  - File size reasonable

- [ ] **Backup schedule established**
  - Frequency: Daily / Weekly (choose one)
  - Location: __________________
  - Retention: ____ backups

- [ ] **Backup restoration tested**
  ```bash
  # Test restore process documented in DEPLOY.md
  ```
  - Process works
  - Data intact after restore

---

## Documentation Checklist

### 14. Team Handoff

- [ ] **All team members notified of deployment**
  - Deployment date communicated
  - Access credentials shared (securely)
  - Documentation links provided

- [ ] **Deployment notes documented**
  - Any deployment issues: _______________
  - Deviations from standard process: _______________
  - Custom configurations: _______________

- [ ] **Monitoring access configured**
  - Team can view logs
  - Team can check container status
  - Team can run manual operations

- [ ] **HANDOFF.md reviewed**
  - Team understands current status
  - Known issues documented
  - Next steps clear

### 15. Runbook Created

- [ ] **Common operations documented**
  - How to view logs
  - How to restart service
  - How to check article count
  - How to export manually
  - How to check API costs

- [ ] **Emergency contacts listed**
  - On-call engineer: _______________
  - Backup contact: _______________
  - API provider support: _______________

- [ ] **Escalation procedures defined**
  - When to restart container
  - When to contact support
  - When to stop scraping

---

## Sign-Off

### Deployment Completed By

**Name**: _______________________
**Date**: _______________________
**Signature**: _______________________

### Verified By

**Name**: _______________________
**Date**: _______________________
**Signature**: _______________________

---

## Issues & Notes

### Issues Encountered During Deployment

1. ____________________________________________
2. ____________________________________________
3. ____________________________________________

### Resolutions

1. ____________________________________________
2. ____________________________________________
3. ____________________________________________

### Additional Notes

_______________________________________________
_______________________________________________
_______________________________________________
_______________________________________________

---

## Post-Deployment Monitoring Plan

### First 24 Hours
- [ ] Check logs every 4 hours
- [ ] Verify scrape cycles completing
- [ ] Monitor resource usage
- [ ] Check for errors

### First Week
- [ ] Daily log review
- [ ] Weekly cleanup ran successfully
- [ ] API costs within expectations
- [ ] Export jobs running

### Ongoing
- [ ] Weekly log review
- [ ] Monthly cost review
- [ ] Quarterly performance review
- [ ] Update dependencies as needed

---

**Checklist Complete**: ☐ Yes ☐ No

**Deployment Status**: ☐ Successful ☐ Partial ☐ Failed

**Production Ready**: ☐ Yes ☐ No

---

*For deployment instructions, see [DEPLOY.md](DEPLOY.md)*
*For project status, see [HANDOFF.md](HANDOFF.md)*
