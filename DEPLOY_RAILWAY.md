# Railway.app Deployment Guide (Easiest Production Deployment)

**Time**: 15 minutes
**Difficulty**: ⭐ Very Easy
**Cost**: ~$5/month
**Best for**: Beginners, production use

---

## Why Railway?

- ✅ No terminal commands needed (mostly)
- ✅ Deploy in 3 clicks
- ✅ Auto-deploys when you push to GitHub
- ✅ Free $5 credit/month (covers this project)
- ✅ Built-in monitoring and logs

---

## Prerequisites

1. ✅ GitHub account (you have this)
2. ✅ Anthropic API key (get from https://console.anthropic.com/)

---

## Step 1: Get Anthropic API Key (5 minutes)

**If you don't have one yet:**

1. Go to https://console.anthropic.com/
2. Click "Sign Up" or "Log In"
3. Click "API Keys" in left menu
4. Click "Create Key"
5. **Copy the key** (looks like: `sk-ant-api03-...`)
6. Save it in a text file - you'll need it in Step 3

---

## Step 2: Create Railway Account & Deploy (5 minutes)

### 2.1 Sign Up for Railway

1. Go to https://railway.app/
2. Click **"Login"** in top right
3. Click **"Login with GitHub"**
4. Authorize Railway to access your GitHub

### 2.2 Create New Project

1. Click **"New Project"** button
2. Select **"Deploy from GitHub repo"**
3. If prompted, click **"Configure GitHub App"**
   - Select your GitHub account
   - Choose **"Only select repositories"**
   - Select `Outplay-News-Scrapper`
   - Click **"Install & Authorize"**

### 2.3 Select Repository

1. In Railway, you should now see your repos
2. Click **`waligorskim/Outplay-News-Scrapper`**
3. Railway will start deploying automatically

**Wait 2-3 minutes** for initial deployment (you'll see progress)

---

## Step 3: Configure Environment Variables (3 minutes)

Your deployment will fail first time (normal) - we need to add your API key.

### 3.1 Add Variables

1. In Railway dashboard, click on your project
2. Click the **"Variables"** tab
3. Click **"New Variable"**
4. Add these one by one:

**Variable 1** (REQUIRED):
```
ANTHROPIC_API_KEY
```
Value: `sk-ant-api03-YOUR_ACTUAL_KEY_HERE` (paste your key from Step 1)

**Variable 2**:
```
SCRAPER_RATE_LIMIT_SECONDS
```
Value: `2`

**Variable 3**:
```
DATABASE_PATH
```
Value: `data/articles.db`

**Variable 4**:
```
LOG_LEVEL
```
Value: `INFO`

**Variable 5**:
```
ARTICLE_RETENTION_DAYS
```
Value: `30`

### 3.2 Trigger Redeploy

1. After adding all variables, Railway auto-redeploys
2. Or click **"Deploy"** → **"Redeploy"**
3. Wait 2-3 minutes

---

## Step 4: Verify It's Working (2 minutes)

### 4.1 Check Deployment Status

1. In Railway dashboard, click **"Deployments"**
2. Latest deployment should show **"Success"** (green checkmark)
3. If "Failed" (red X), see Troubleshooting below

### 4.2 View Logs

1. Click **"Logs"** tab
2. You should see:
   ```
   ✅ Scheduler initialized successfully
   Jobs configured: 5
   - Scrape job (every 4 hours)
   - Export job (daily at 2:00 AM)
   ```

### 4.3 Wait for First Scrape

- Scraper runs every 4 hours automatically
- Check logs after 15 minutes to see first scrape
- Look for: `Processing batch of...` in logs

---

## 🎉 You're Done!

Your news scraper is now running in production on Railway!

---

## What Happens Now?

✅ **Automatic scraping**: Every 4 hours
✅ **AI summaries**: Generated automatically
✅ **Daily exports**: JSON/XML at 2 AM
✅ **Weekly cleanup**: Every Sunday at 3 AM
✅ **Auto-restarts**: If it crashes, Railway restarts it

---

## Monitoring Your Scraper

### View Logs
1. Go to Railway dashboard
2. Click your project
3. Click **"Logs"**
4. See real-time activity

### Check Resource Usage
1. Click **"Metrics"** tab
2. See CPU, Memory, Network usage

### View Costs
1. Click your avatar (top right)
2. Click **"Usage"**
3. See current month's usage

**Expected cost**: ~$5/month (covered by free credit)

---

## Useful Commands

### If You Need Terminal Access

Railway provides a CLI for advanced operations:

**Install Railway CLI**:
```bash
npm install -g @railway/cli
```

**Login**:
```bash
railway login
```

**Link to project**:
```bash
railway link
```

**Run commands in your deployment**:
```bash
# Check article count
railway run python -c "import sqlite3; db=sqlite3.connect('data/articles.db'); print(db.execute('SELECT COUNT(*) FROM articles').fetchone()[0])"

# Check verification
railway run python src/verify_system.py

# Trigger manual scrape
railway run python src/pipeline.py --batch --limit 5
```

**But honestly, you probably won't need these!** Everything works automatically.

---

## Updating Your Code

When you make changes to your code:

1. Commit changes to GitHub:
   ```bash
   git add .
   git commit -m "Updated scraper"
   git push origin main
   ```

2. Railway automatically detects the push and redeploys (2-3 minutes)

3. Check deployment status in Railway dashboard

**That's it!** No manual deployment needed.

---

## Troubleshooting

### Deployment Failed

**Check logs**:
1. Click "Logs" tab
2. Look for error message (usually in red)

**Common issues**:

**Error: "ANTHROPIC_API_KEY not set"**
- Solution: Go to Variables tab, make sure API key is added correctly

**Error: "No module named..."**
- Solution: Make sure `requirements.txt` is in your repo
- Redeploy

**Error: "Port already in use"**
- Solution: This shouldn't happen on Railway, but try redeploying

### No Articles Being Scraped

**Check logs**:
```
Look for: "Processing batch of..." in logs
```

**If you don't see scraping after 4 hours**:
1. Check logs for errors
2. Use Railway CLI to manually trigger:
   ```bash
   railway run python src/pipeline.py --batch --limit 5
   ```

### High Costs

Railway free tier includes $5 credit/month. This project should stay within that.

**If costs are higher**:
1. Check "Metrics" tab
2. Reduce scraping frequency (modify scheduler)
3. Reduce batch size

---

## Advanced: Custom Domain (Optional)

Want to access your logs at a custom domain?

1. In Railway, click your project
2. Click "Settings"
3. Click "Generate Domain"
4. Railway gives you: `your-project.up.railway.app`

Not really useful for this project, but nice to know!

---

## Comparison with Other Options

### Railway vs Local Docker
- Railway: Runs 24/7 in cloud ($5/month)
- Local: Runs on your computer (free, but computer must stay on)

### Railway vs Google Cloud VM
- Railway: Click and deploy, no terminal needed
- Cloud VM: Full control, but complex setup ($20/month)

### Railway vs n8n.io
- Railway: Runs your Python code directly
- n8n: Visual workflows, but more expensive ($20/month)

**Railway is the sweet spot for beginners!**

---

## Next Steps

After deployment is successful:

1. **Monitor for 24 hours**: Check logs, make sure scraping works
2. **Check API costs**: Go to Anthropic dashboard, see usage
3. **Test exports**: After 2 AM, check logs for export job
4. **Iterate**: Make improvements based on real data

---

## Getting Help

**Railway Issues**:
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app/

**Scraper Issues**:
- Check `DEPLOY.md` in your repo for troubleshooting
- Check Railway logs for error messages

---

## Summary

✅ Easiest production deployment
✅ No terminal commands (mostly)
✅ Auto-deploys on git push
✅ $5/month (free tier)
✅ Perfect for beginners

**Total time**: 15 minutes
**Total cost**: ~$5/month

🎉 **Enjoy your automated news scraper!**
