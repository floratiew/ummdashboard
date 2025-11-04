# 🔧 Troubleshooting Render Deployment

## Your Current Error: "Bad Gateway"

This error means Render deployed your app, but the server isn't responding correctly.

## 🔍 Immediate Steps to Diagnose:

### 1. Check Render Logs
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click on your `umm-dashboard` service
3. Click **"Logs"** tab
4. Look for errors (especially during startup)

**Common log errors to look for:**
- ❌ `ENOENT: no such file or directory` → CSV file missing
- ❌ `Cannot find module` → npm install failed
- ❌ `Port already in use` → Port configuration issue
- ❌ `npm ERR!` → Build failed

### 2. Access Health Check (Once Deployed)
Visit: `https://your-app-name.onrender.com/health`

This will show:
```json
{
  "status": "OK",
  "csvExists": true/false,
  "buildExists": true/false,
  "indexHtmlExists": true/false
}
```

## 🎯 Most Likely Causes & Fixes:

### Issue #1: Git LFS Files Not Downloaded (MOST LIKELY!)

**Problem:** Your `umm_messages1.csv` is 130MB and uses Git LFS. **Render Free tier doesn't support Git LFS by default!**

**Solution A: Add Git LFS to Render (Recommended)**

Update your `render.yaml`:
```yaml
services:
  - type: web
    name: umm-dashboard
    env: node
    rootDir: umm-dashboard-react
    buildCommand: git lfs pull && npm run render-build
    startCommand: npm run render-start
    plan: free
    envVars:
      - key: NODE_ENV
        value: production
```

**Solution B: Use smaller test data (Quick fix)**

Create a smaller CSV for testing:
```bash
cd /Users/floratiew/Desktop/UMM
head -n 10000 data/umm_messages1.csv > data/umm_messages_small.csv
git add data/umm_messages_small.csv
git commit -m "Add small test CSV"
git push
```

Then update `backend/server.js`:
```javascript
const CSV_PATH = path.join(__dirname, '../../data/umm_messages_small.csv');
```

### Issue #2: Build Command Failing

Check if React build is successful:

**In Render logs, look for:**
```
Creating an optimized production build...
Compiled successfully.
```

**If it fails:**
- Check for TypeScript errors
- Check for missing dependencies
- Verify Node version (Render uses Node 20)

### Issue #3: Port Configuration

Render automatically sets `PORT` environment variable. Your code should use:
```javascript
const PORT = process.env.PORT || 5001;
```

✅ This is already correct in your code!

### Issue #4: Frontend Build Not Found

**Check in logs:**
```
🌐 Serving React app from: /opt/render/project/src/umm-dashboard-react/frontend/build
```

**If build folder missing:**
- Build command didn't run
- Check `npm run render-build` works locally

## 📋 Step-by-Step Debugging Checklist:

### Step 1: View Render Logs
```
Go to Render Dashboard → Your Service → Logs
```

Look for:
- [ ] "🚀 Nord Pool UMM Backend running" ← Server started?
- [ ] "📊 Loading data from:" ← CSV path logged?
- [ ] Any error messages?
- [ ] Port number shown?

### Step 2: Test Health Endpoint
Once service is "Live":
```
curl https://your-app.onrender.com/health
```

Expected response:
```json
{
  "status": "OK",
  "csvExists": true,  ← Should be true!
  "buildExists": true, ← Should be true!
  "indexHtmlExists": true ← Should be true!
}
```

### Step 3: Check Build Output
In Render logs during deployment:
```
==> Building...
==> Running 'npm run render-build'
...
Build succeeded ✅
```

### Step 4: Verify Data Files
```bash
# Locally, check what's actually in Git
cd /Users/floratiew/Desktop/UMM
git lfs ls-files  # Should show umm_messages1.csv
```

## 🚀 Quick Fixes to Try:

### Fix #1: Add Git LFS to Build Command

Update `/Users/floratiew/Desktop/UMM/render.yaml`:

```yaml
services:
  - type: web
    name: umm-dashboard
    env: node
    rootDir: umm-dashboard-react
    buildCommand: git lfs install && git lfs pull && npm run render-build
    startCommand: npm run render-start
    plan: free
    envVars:
      - key: NODE_ENV
        value: production
      - key: GIT_LFS_SKIP_SMUDGE
        value: 0
```

Then:
```bash
cd /Users/floratiew/Desktop/UMM
git add render.yaml
git commit -m "Add Git LFS support to Render build"
git push origin main
```

Render will auto-redeploy!

### Fix #2: Manual Redeploy
Sometimes Render just needs a kick:
1. Go to Render Dashboard
2. Click your service
3. Click **"Manual Deploy"** → **"Clear build cache & deploy"**

### Fix #3: Check Environment Variables
In Render Dashboard → Your Service → Environment:
- Verify `NODE_ENV` = `production`
- Add if missing: `PORT` (should be auto-set by Render)

## 📊 Expected Deployment Timeline:

```
0:00 - Cloning repository from GitHub
0:30 - Installing npm dependencies (backend)
2:00 - Installing npm dependencies (frontend)
4:00 - Building React app (npm run build)
5:00 - Starting server
5:30 - Service Live! 🎉
```

Total: ~5-6 minutes for first deployment

## 🐛 Common Error Messages & Solutions:

### "ENOENT: no such file or directory, open '...umm_messages1.csv'"
**Cause:** Git LFS file not downloaded
**Fix:** Add `git lfs pull` to build command (see Fix #1 above)

### "Cannot find module 'express'"
**Cause:** npm install failed
**Fix:** Check package.json dependencies, try "Clear build cache"

### "Error: listen EADDRINUSE"
**Cause:** Port already in use
**Fix:** Should not happen on Render (Render assigns unique ports)

### "404: File or directory not found"
**Cause:** React build failed or wrong path
**Fix:** Check build logs, verify `npm run build` works locally

## 💡 Pro Tips:

1. **Watch logs in real-time** during deployment
2. **Test locally first:**
   ```bash
   cd /Users/floratiew/Desktop/UMM/umm-dashboard-react
   NODE_ENV=production npm run render-build
   npm run render-start
   ```
3. **Use smaller data** for initial testing
4. **Check Render status:** https://status.render.com/

## 📞 Next Steps:

1. **Check Render logs** - This is #1 priority!
2. **Try Fix #1** (Add Git LFS support)
3. **Access `/health` endpoint** to see what's missing
4. **Share logs with me** if still stuck

## 🎯 Most Likely Solution:

Based on your 130MB CSV file, **99% chance** the issue is Git LFS. Try Fix #1 first!

```bash
cd /Users/floratiew/Desktop/UMM
# Edit render.yaml (add git lfs pull to buildCommand)
git add render.yaml
git commit -m "Fix: Add Git LFS support for large CSV files"
git push origin main
```

Wait 5-6 minutes for Render to redeploy, then check!
