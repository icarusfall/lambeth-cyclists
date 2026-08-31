# Railway Deployment Guide

This guide will help you deploy the Lambeth Cyclists Email Processor to Railway for 24/7 operation.

## Prerequisites

- ✅ Local testing complete (emails processing successfully)
- ✅ All API connections working
- ✅ Geocoding working
- GitHub account
- Railway account (free tier is fine to start)

## Estimated Time

**20-30 minutes** for first-time setup

---

> Updated 30 August 2026. This guide described deploying one repo as one
> service. It is now **one repo, several services**: `processor/` (worker),
> `portal/` (web), and `mcp/` (web, only while the Vercel CycleBot front end
> still needs it). Each is a separate Railway service pointed at a different
> **Root Directory** in the same repo.

## Step 1: Prepare Your Repository

The repository already exists and is already pushed - this section is kept for
setting up a fresh environment.

```bash
git remote -v      # should show icarusfall/lambeth-cyclists
git push origin main
```

**IMPORTANT:** every service's `.env` is gitignored (the pattern matches at any
depth, so `processor/.env`, `portal/.env` and `mcp/.env` are all covered).
Verify with `git check-ignore -v processor/.env` before pushing.

---

## Step 2: Set Up Railway

### 2.1 Create Railway Account

1. Go to https://railway.app/
2. Sign up with your GitHub account (easiest method)
3. Verify your email

### 2.2 Create the Project and its Services

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Connect your GitHub account if prompted
4. Select the `lambeth-cyclists` repository
5. Railway will detect it's a Python project

Then add **one service per directory**, in the same project so they can share
variables. This is the part the old version of this guide got wrong: with three
apps in one repo, Railway needs to be told which one each service is.

### 2.3 Configure Each Service

Set a **Custom Start Command** per service in **Settings -> Deploy**:

| Service | Custom Start Command |
|---|---|
| processor | `cd processor && python main.py` |
| portal | `cd portal && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| mcp | `cd mcp && python server.py` |

**This is not optional.** There is no `Procfile` and no `railway.json` in this
repo, so without a start command Nixpacks builds successfully and then has
nothing to run. The failure mode is nasty: the deploy fails, Railway keeps
serving the **last good build**, and the service looks healthy while running
code from before the merge. That is exactly what happened to the portal on
31 August 2026 - it had been pointed at this repo for a while, quietly failing
every deploy, still serving the old separate-repo build.

If a service looks like it is ignoring your pushes, check Deployments for
failures before assuming the source is wrong.

**Leave Root Directory unset (the repo root).** It is tempting to point each
service at its own subdirectory, but `requirements.txt` and `pyproject.toml`
live at the **repo root** - one dependency set for everything, which is what
stopped the processor sitting a major version behind on `notion-client`. Point
Root Directory at `portal/` and the build finds no `requirements.txt` and
fails.

So the build always runs from the root and the start command `cd`s into the
service. That is also what makes `-e .` work: it installs the shared `core`
package in editable mode, which is how each service imports `core.*` while
running from its own directory.

Set the restart policy per service too: on failure, 10 retries for the
processor, 3 for the web services.

> **On config files.** Railway's Config as Code (`railway.json` / `railway.toml`)
> is deprecated in favour of Infrastructure as Code (`.railway/railway.ts`).
> This repo deliberately has neither: the settings above are few enough to hold
> in the dashboard, and adopting IaC means one file describing every service,
> which is worth doing deliberately rather than during an outage. If you migrate
> later, `railway config migrate --apply` generates it, and the per-service
> Config File Path must then be cleared so there is one source of truth.

**`mcp` no longer needs deploying.** Since 30 August 2026 the portal's chat
runs CycleBot's tools in-process via `core.cyclebot`, and the only other
consumer - the Vercel front end at `cyclebot.vercel.app` - is being retired.
Deploy this service only if you want CycleBot reachable by a third-party MCP
client. See [cyclebot-architecture.md](cyclebot-architecture.md).

---

## Step 3: Configure Environment Variables

This is the most important step! You need to add all your environment variables from `.env` to Railway.

### 3.1 Open Variables Settings

1. In your Railway project, click "Variables" tab
2. Click "RAW Editor" for easier bulk input

### 3.2 Copy Environment Variables

Copy these from your local `.env` file and paste into Railway's RAW Editor:

```bash
# Gmail API Configuration
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token
GMAIL_LABEL=Lambeth Cycling Projects

# Claude API
CLAUDE_API_KEY=sk-ant-your-claude-api-key

# Notion API
NOTION_API_KEY=secret_your-notion-integration-key
NOTION_ITEMS_DB_ID=your-items-database-id
NOTION_PROJECTS_DB_ID=your-projects-database-id
NOTION_MEETINGS_DB_ID=your-meetings-database-id

# Google Maps API
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id

# Application Configuration
EMAIL_POLL_INTERVAL=300
MEETING_CHECK_INTERVAL=3600
LOG_LEVEL=INFO
ADMIN_EMAIL=your-email@example.com

# Rate Limits
CLAUDE_RPM=50
GMAIL_QPM=250
NOTION_RPM=3
```

**Replace all the `your-*` placeholders with your actual values from `.env`!**

### 3.3 Save Variables

Click "Update Variables" to save.

---

## Step 4: Deploy

### 4.1 Trigger Deployment

Railway will automatically deploy when you push to GitHub, but you can also:

1. Click "Deploy" in the Railway dashboard
2. Watch the build logs in real-time

### 4.2 Monitor Build

You'll see:
- Installing dependencies from `requirements.txt`
- Starting the application with `python main.py`

Expected build time: 2-3 minutes

### 4.3 Check Deployment Status

Once deployed, you should see:
- Status: "Active" (green)
- Logs showing: "Lambeth Cyclists Email Processor Starting"

---

## Step 5: Verify It's Working

### 5.1 Check Logs

1. Click "Deployments" → "View Logs"
2. You should see logs similar to your local run:
   ```
   ============================================================
   Lambeth Cyclists Email Processor Starting
   ============================================================
   ✓ Configuration validated successfully
   Startup complete
   Starting email polling loop (interval: 300s)
   Starting meeting agenda loop (interval: 3600s)
   ```

### 5.2 Send Test Email

1. Send a test email to your Gmail
2. Add the "Lambeth Cycling Projects" label
3. Wait up to 5 minutes (polling interval)
4. Check Railway logs - you should see:
   ```
   Found 1 new emails to process
   Retrieved email: 'Your Test Email'
   Analyzing email with Claude AI
   Created Notion item: ...
   Successfully processed email
   ```
5. Verify the Notion item was created

### 5.3 Check for Errors

If you see errors in the logs:
- **Configuration errors**: Double-check environment variables
- **API authentication errors**: Verify all API keys are correct
- **Network errors**: Usually temporary, Railway will retry

---

## Step 6: Configure Railway Settings (Optional)

### 6.1 Set Up Custom Domain (Optional)

Railway doesn't need a domain for this background service, but if you want to add monitoring endpoints later:

1. Click "Settings" → "Domains"
2. Generate a Railway domain or add your own

### 6.2 Configure Restart Policy

Set per service in Settings (there is no `railway.json`):
- Restart on failure: Yes
- Max retries: 10
- This ensures the app recovers from temporary errors

### 6.3 Resource Limits

Free tier includes:
- 500 hours/month execution time ($5 credit)
- 512 MB RAM
- Shared CPU

For this application, free tier should be sufficient unless processing hundreds of emails daily.

---

## Step 7: Ongoing Monitoring

### 7.1 Check Logs Regularly

Visit Railway dashboard to monitor:
- Email processing activity
- Any error messages
- API rate limit warnings

### 7.2 Set Up Notifications (Future - Phase 9)

Phase 9 will add:
- Health checks
- Error notifications to your email
- Sentry integration for error tracking

### 7.3 Monitor Costs

- Railway: Free tier is sufficient to start ($5/month credit)
- Claude API: ~$2-5/month (check at https://console.anthropic.com/)
- Google Maps: Free up to $200/month credit

**Total estimated cost: $0-10/month depending on volume**

---

## Troubleshooting

### Build Fails

**Check:**
- `requirements.txt` is in the repository
- All dependencies are compatible with Linux (Railway uses Linux)
- No Windows-specific dependencies

**Fix:**
- Check build logs for specific error
- Check the service's **Root Directory** is set (`processor`, `portal` or
  `mcp`). Unset, Railway builds the repo root and starts the wrong thing.

### App Starts But Crashes

**Check logs for:**
- Missing environment variables
- Invalid API keys
- Database connection issues

**Fix:**
- Verify all environment variables in Railway match `.env`
- Test API keys locally first
- Check Railway logs for specific error messages

### No Emails Being Processed

**Check:**
- Logs show "Starting email polling loop"
- Gmail label is exactly "Lambeth Cycling Projects" (case-sensitive)
- Emails don't already have "processed" label
- Railway app is running (not sleeping)

**Fix:**
- Check Railway "Deployments" - should show "Active"
- Verify Gmail API credentials are correct
- Send a test email and watch logs

### High Railway Costs

**Check:**
- How many hours/month the app is running
- Whether you've exceeded free tier limits

**Fix:**
- Increase `EMAIL_POLL_INTERVAL` to reduce CPU usage
- Use Railway's usage dashboard to monitor
- Free tier should handle typical usage

---

## Updating the Application

### When You Make Changes

1. **Commit changes locally:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Railway auto-deploys:**
   - Railway detects the push
   - Automatically rebuilds and redeploys
   - Zero downtime (new version replaces old)

3. **Monitor deployment:**
   - Watch logs to ensure successful restart
   - Test with a new email

### Rolling Back

If a deployment breaks something:

1. Go to "Deployments" in Railway
2. Find a previous working deployment
3. Click "Redeploy"

---

## Security Best Practices

### ✓ Already Implemented

- ✅ `.env` in `.gitignore` (secrets not in GitHub)
- ✅ Environment variables in Railway (not hardcoded)
- ✅ OAuth for Gmail (more secure than password)

### Additional Recommendations

1. **Enable 2FA** on all accounts:
   - GitHub
   - Railway
   - Google Cloud Console
   - Anthropic Console

2. **Rotate API keys** periodically:
   - Every 6-12 months
   - Immediately if compromised

3. **Monitor access logs**:
   - Check Railway logs for unusual activity
   - Review Google Cloud Console audit logs

4. **Keep dependencies updated**:
   ```bash
   pip list --outdated
   pip install --upgrade [package-name]
   ```

---

## Success Checklist

Before considering deployment complete:

- [ ] Railway project created and connected to GitHub
- [ ] All environment variables configured in Railway
- [ ] Deployment successful (status: Active)
- [ ] Logs show application started correctly
- [ ] Test email processed successfully
- [ ] Notion item created from test email
- [ ] No errors in Railway logs
- [ ] Geocoding working (check test email has coordinates)
- [ ] Attachments uploaded to Google Drive

---

## What Happens Now?

Once deployed, your application will:

1. **Run 24/7** on Railway servers
2. **Poll Gmail** every 5 minutes automatically
3. **Process new emails** as they arrive
4. **Create Notion items** without your intervention
5. **Recover automatically** from temporary errors

You can:
- Close your laptop - it keeps running
- Check Railway logs anytime to see activity
- Push updates to GitHub - Railway auto-deploys
- Monitor Notion to see new items appear

---

## Next Steps (Optional)

After Railway deployment, you can continue with:

- **Phase 8**: Meeting agenda generation
- **Phase 9**: Health monitoring and error notifications
- **Phase 10**: Migrate your existing Notion data
- **Phase 11**: Comprehensive testing

But for now, **your core system is live and running remotely!** 🚀

---

## Quick Reference

**Railway Dashboard:** https://railway.app/dashboard

**Key Commands:**
```bash
# Deploy new changes
git add .
git commit -m "Your message"
git push origin main

# View logs locally (if needed)
railway logs
```

**Support:**
- Railway docs: https://docs.railway.app/
- Railway Discord: https://discord.gg/railway

---

## Cost Tracking

Keep an eye on your monthly costs:

| Service | Free Tier | Expected Cost |
|---------|-----------|---------------|
| Railway | $5 credit/month | $0 (within free tier) |
| Claude API | Pay per token | $2-5/month |
| Google Maps | $200 credit/month | $0 (within free tier) |
| Gmail API | Free | $0 |
| Notion API | Free | $0 |
| **Total** | | **$2-5/month** |

For monitoring 50-100 emails/month with attachments and geocoding, you should stay within all free tiers except Claude.

---

**Questions or issues during deployment? Check the logs first - they usually tell you exactly what's wrong!**
