# n8n.io Deployment Guide (Visual Workflow Approach)

**Time**: 30 minutes
**Difficulty**: ⭐⭐⭐ Moderate
**Cost**: $0-20/month
**Best for**: Visual workflows, integrations, no-code preference

---

## What is n8n?

n8n is a workflow automation tool (like Zapier or Make.com) that lets you:
- Build workflows visually (drag-and-drop)
- Connect 350+ services
- Run scheduled tasks
- No coding required (mostly)

---

## Two Options

### Option A: n8n Cloud (Easier)
- Hosted by n8n
- No server setup needed
- Free tier: 5,000 executions/month
- Paid: $20/month unlimited

### Option B: Self-Hosted n8n (Cheaper)
- Deploy on your own server
- Free (except server costs ~$5/month)
- Requires Docker knowledge

**Recommendation**: Start with **Option A (n8n Cloud)** for testing.

---

## Option A: n8n Cloud Deployment (Easiest)

### Step 1: Create n8n Cloud Account (3 minutes)

1. Go to https://n8n.io/cloud/
2. Click **"Start free"**
3. Sign up with email or GitHub
4. Verify your email
5. Login to n8n dashboard

### Step 2: Import Workflow Template (5 minutes)

We've created a ready-to-use workflow for you!

1. **Download the template**:
   - Go to your repository on GitHub
   - Find file: `n8n-workflow-template.json`
   - Click "Download" or copy the content

2. **Import to n8n**:
   - In n8n dashboard, click **"Workflows"**
   - Click **"Add Workflow"** → **"Import from File"**
   - Upload `n8n-workflow-template.json`
   - Click **"Import"**

### Step 3: Configure Credentials (7 minutes)

#### 3.1 Add Anthropic API Credentials

1. In the workflow, click on **"Claude AI Summarize"** node
2. Click **"Credentials"** dropdown
3. Click **"Create New"**
4. Enter:
   - **Name**: `Anthropic API`
   - **API Key**: `sk-ant-api03-YOUR_KEY_HERE` (from https://console.anthropic.com/)
5. Click **"Save"**

#### 3.2 Add Database Credentials

**Choose one database option:**

##### Option 1: PostgreSQL (Most Powerful)

If you have a PostgreSQL database (from Railway, Render, etc.):

1. Click **"Save to Database"** node
2. Click **"Credentials"** → **"Create New"**
3. Enter your database details:
   ```
   Host: your-db-host.railway.app
   Database: railway
   User: postgres
   Password: your_password
   Port: 5432
   ```
4. Click **"Test Connection"**
5. Click **"Save"**

##### Option 2: Airtable (Easiest)

1. Delete **"Save to Database"** node
2. Add new node: Search for **"Airtable"**
3. Configure:
   - **Operation**: Create
   - **Base**: Create a base at airtable.com
   - **Table**: `articles`
4. Connect Airtable credentials

##### Option 3: Google Sheets (Free)

1. Delete **"Save to Database"** node
2. Add new node: Search for **"Google Sheets"**
3. Configure:
   - **Operation**: Append
   - **Spreadsheet**: Create one in Google Sheets
   - **Sheet**: `Articles`
4. Connect Google credentials

### Step 4: Customize Workflow (5 minutes)

#### 4.1 Adjust Schedule

1. Click **"Every 4 Hours"** node
2. Change interval if needed:
   - Every 2 hours
   - Every 6 hours
   - Daily at specific time
3. Click **"Save"**

#### 4.2 Adjust Article Limit

1. Click **"Extract Article URLs"** node
2. Find line: `.slice(0, 5)`
3. Change `5` to how many articles you want per run
4. Click **"Save"**

### Step 5: Test Workflow (5 minutes)

1. Click **"Execute Workflow"** button (top right)
2. Watch nodes execute one by one (they turn green)
3. Click each node to see output data
4. Check for errors (red nodes)

**Expected output**:
- Fetch News Page: ✅ HTML content
- Extract Article URLs: ✅ 5 article objects
- Fetch Article Content: ✅ Full article HTML
- Parse Article: ✅ Structured data
- Claude AI Summarize: ✅ Summary text
- Save to Database: ✅ Saved successfully

### Step 6: Activate Workflow (1 minute)

1. Toggle **"Active"** switch (top right)
2. Workflow now runs every 4 hours automatically
3. Check **"Executions"** tab to see history

---

## Option B: Self-Hosted n8n (Advanced)

### Why Self-Host?
- ✅ Free (except server costs)
- ✅ Unlimited executions
- ✅ Full control
- ❌ Requires server management

### Prerequisites
- Server with Docker (Railway, Google Cloud, etc.)
- Domain name (optional)

### Quick Deploy to Railway

1. **Fork n8n template**:
   ```bash
   git clone https://github.com/n8n-io/n8n-railway-template.git
   cd n8n-railway-template
   ```

2. **Deploy to Railway**:
   - Go to Railway.app
   - Click "Deploy from GitHub"
   - Select the n8n template repo
   - Add environment variables:
     ```
     N8N_BASIC_AUTH_ACTIVE=true
     N8N_BASIC_AUTH_USER=admin
     N8N_BASIC_AUTH_PASSWORD=your_secure_password
     ```

3. **Access n8n**:
   - Railway gives you a URL: `https://your-app.up.railway.app`
   - Login with credentials from step 2
   - Import workflow template (same as Option A, Step 2)

### Cost
- Railway: ~$5/month
- + Anthropic API: ~$5/month
- **Total: ~$10/month**

---

## Workflow Explanation

Here's what the workflow does:

```
1. [Schedule Trigger] - Runs every 4 hours
         ↓
2. [Fetch News Page] - Downloads Pocket Gamer news listing
         ↓
3. [Extract Article URLs] - Parses HTML, finds 5 article links
         ↓
4. [Fetch Article Content] - Downloads each article page
         ↓
5. [Parse Article] - Extracts title, date, author, content, image
         ↓
6. [Claude AI Summarize] - Generates 200-300 char summary
         ↓
7. [Combine Data] - Merges article + summary
         ↓
8. [Save to Database] - Stores in PostgreSQL/Airtable/Sheets
         ↓
9. [Check for Errors] - Routes to success/error handling
```

---

## Customization Ideas

### Add Email Notifications

After **"Success Summary"** node:

1. Add **"Gmail"** or **"Send Email"** node
2. Configure:
   ```
   To: your@email.com
   Subject: Daily News Scrape Complete
   Body: Processed {{$json.articlesProcessed}} articles
   ```

### Add Slack Notifications

After **"Success Summary"** node:

1. Add **"Slack"** node
2. Configure:
   - **Channel**: `#news-alerts`
   - **Message**: `✅ Scraped {{$json.articlesProcessed}} articles`

### Add RSS Feed Generation

After **"Save to Database"**:

1. Add **"RSS"** node
2. Generate RSS feed from articles
3. Host feed for readers

### Add Duplicate Detection

Before **"Save to Database"**:

1. Add **"HTTP Request"** node
2. Check if URL already exists in database
3. Add **"IF"** node to skip duplicates

---

## Monitoring & Maintenance

### View Execution History

1. Click **"Executions"** in left menu
2. See all workflow runs
3. Click any execution to see details
4. Check success/failure status

### View Logs

1. Each node shows its output
2. Click node → **"Output"** tab
3. See processed data
4. Check for errors (red nodes)

### Costs Monitoring

n8n Cloud free tier:
- 5,000 workflow executions/month
- This workflow: ~180 executions/month (every 4 hours)
- **You're well within free tier!**

If you exceed:
- Upgrade to Starter: $20/month unlimited

---

## Advantages of n8n Approach

✅ **Visual workflows**: See what's happening
✅ **Easy integrations**: Add Slack, email, etc. with clicks
✅ **No code changes**: Modify in browser
✅ **Built-in monitoring**: Execution history
✅ **Easy testing**: Click "Execute" to test
✅ **Error handling**: Visual error paths

---

## Disadvantages of n8n Approach

❌ **More expensive**: $20/month vs $5 for Railway
❌ **Less control**: Can't customize scraping logic easily
❌ **Vendor lock-in**: Tied to n8n
❌ **Execution limits**: 5K/month on free tier
❌ **Learning curve**: New tool to learn

---

## Hybrid Approach (Best of Both Worlds)

Use both your Python scraper AND n8n:

### Architecture

```
n8n Workflow (Orchestration)
    ↓
Triggers Python scraper API (deployed on Railway)
    ↓
Python returns scraped articles
    ↓
n8n runs Claude AI
    ↓
n8n saves to database
    ↓
n8n sends notifications (Slack, email)
```

### Why This Works

- ✅ Python does complex scraping (your code)
- ✅ n8n does orchestration (scheduling, monitoring)
- ✅ n8n adds integrations (Slack, email)
- ✅ Easy to modify both separately

### How to Set Up

1. **Deploy Python scraper to Railway**:
   - Remove scheduler from code
   - Add Flask/FastAPI endpoint
   - Returns JSON of articles

2. **Create n8n workflow**:
   - Schedule trigger (every 4 hours)
   - HTTP Request to Railway API
   - Claude AI node
   - Database node
   - Slack/Email nodes

**I can create this setup if you're interested!**

---

## Comparison with Other Options

| Feature | n8n Cloud | Python (Railway) | Hybrid |
|---------|-----------|------------------|---------|
| Setup Time | 30 min | 15 min | 45 min |
| Cost | $20/month | $5/month | $25/month |
| Difficulty | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Integrations | ✅ Easy | ❌ Manual | ✅ Easy |
| Customization | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Monitoring | ✅ Visual | ⭐⭐ Logs | ✅ Visual |

---

## My Recommendation

**For you specifically:**

Since you're new to deployment and want to test quickly:

1. **Start with Railway.app** (Option 2 from DEPLOYMENT_OPTIONS.md)
   - Get it working in production first
   - $5/month, very simple

2. **After 1-2 weeks, consider adding n8n** if you need:
   - Slack notifications when scraping fails
   - Email digests of new articles
   - Visual monitoring dashboard
   - Integration with other tools

3. **Don't start with n8n** unless you specifically need visual workflows

---

## Next Steps

**If you want to try n8n:**

1. Sign up at https://n8n.io/cloud/ (free)
2. Import the workflow template (provided)
3. Add your Anthropic API key
4. Choose database (Airtable easiest)
5. Test workflow
6. Activate

**If you want Python + n8n hybrid:**

Let me know and I'll create:
- Modified Python scraper with API endpoint
- n8n workflow to call it
- Full integration guide

---

## Questions?

**Tell me:**
1. Does n8n sound interesting to you?
2. Do you want visual workflows?
3. Do you need integrations (Slack, email, etc.)?
4. Should we go with Railway instead (simpler)?

I'll guide you through whichever option you choose!
