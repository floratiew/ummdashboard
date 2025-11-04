# 🚀 Deployment Guide - Render (100% FREE)

## Overview
Your app will run **completely FREE** on Render using ONE Web Service that serves both the API and React frontend.

## Pricing Breakdown
- ✅ **Static Site**: FREE (but we won't use this)
- ✅ **Web Service Free Tier**: FREE with limitations
  - Spins down after 15 min of inactivity
  - ~30 second wake-up time
  - 512 MB RAM, shared CPU
  - 750 hours/month (enough for 24/7)

## 📋 Deployment Steps

### 1. Prepare Your Repo (Already Done ✅)
The following files have been configured:
- `package.json` - Root build scripts
- `backend/server.js` - Serves React build in production
- `frontend/package.json` - Proxy for local dev
- `render.yaml` - Render configuration
- `README.md` - Documentation

### 2. Push to GitHub
```bash
cd /Users/floratiew/Desktop/UMM

# Initialize git (if not done)
git init

# Add remote
git remote add origin https://github.com/floratiew/ablydashboard.git

# Add files
git add umm-dashboard-react/

# Commit
git commit -m "Initial commit: UMM Dashboard with React + Node.js"

# Push
git push -u origin main
```

### 3. Deploy on Render

#### Option A: Using render.yaml (Recommended)
1. Go to https://dashboard.render.com/
2. Click "New +" → "Blueprint"
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml`
5. Click "Apply"

#### Option B: Manual Setup
1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect your GitHub: `floratiew/ablydashboard`
4. Configure:
   ```
   Name: umm-dashboard
   Root Directory: umm-dashboard-react
   Environment: Node
   Build Command: npm run render-build
   Start Command: npm run render-start
   Instance Type: Free
   ```
5. Add Environment Variable:
   - Key: `NODE_ENV`
   - Value: `production`
6. Click "Create Web Service"

### 4. Wait for Deployment
- Build takes ~5-10 minutes
- You'll see logs in real-time
- Once done, you'll get a URL like: `https://umm-dashboard.onrender.com`

## 🔧 Post-Deployment

### Test Your App
1. Visit your Render URL
2. First load may take 30s (cold start)
3. Test all features:
   - Dashboard page
   - Production Units page
   - Outage Analysis page

### Monitor
- Check logs: Render Dashboard → Your Service → Logs
- View metrics: CPU, Memory usage
- Set up health checks (optional)

## 📁 Data Files

### Important: Your CSV Data
Your app needs these files:
```
data/
├── umm_messages1.csv (103,775 records)
└── umm_area_outage_events.csv
```

These files are loaded by the backend at:
```
const CSV_PATH = path.join(__dirname, '../../data/umm_messages1.csv');
```

**Make sure** these files are:
1. ✅ Committed to Git
2. ✅ Pushed to GitHub
3. ✅ In the correct location relative to backend/

### Large Files (If needed)
If your CSV is >100MB, you'll need Git LFS:
```bash
# Install Git LFS
brew install git-lfs  # macOS
# or download from: https://git-lfs.github.com/

# Initialize in your repo
git lfs install

# Track large files
git lfs track "data/*.csv"

# Add .gitattributes
git add .gitattributes

# Commit and push
git add data/*.csv
git commit -m "Add CSV data with Git LFS"
git push
```

## 🎯 Architecture

### Development (localhost)
```
Frontend (port 3001) → proxy → Backend (port 5001)
                                    ↓
                              CSV Data Files
```

### Production (Render)
```
User → Render URL → Backend (Express)
                        ↓
                   Static React Files + API
                        ↓
                   CSV Data Files
```

## 💡 Tips

### Keep App Awake (Optional)
To prevent cold starts, use a free service like UptimeRobot to ping your app every 5 minutes:
1. Sign up at https://uptimerobot.com/ (free)
2. Add Monitor → HTTP(s)
3. URL: Your Render URL
4. Interval: 5 minutes

### View Logs
```bash
# Real-time logs in Render Dashboard
# Or use Render CLI (optional)
render logs -s umm-dashboard
```

### Update Deployment
Just push to GitHub:
```bash
git add .
git commit -m "Update dashboard"
git push
```
Render auto-deploys on git push!

## 🐛 Troubleshooting

### Build Fails
- Check Node version (Render uses v20 by default)
- Verify all dependencies are in package.json
- Check build logs for errors

### 404 on Routes
- Make sure catch-all route is in server.js (✅ already added)
- Verify React build files exist

### API Not Working
- Check environment variables
- Verify CSV file paths
- Check backend logs

### Slow First Load
- Normal! Free tier spins down after 15 min
- Upgrade to $7/month for always-on

## 🔄 Alternative: Keep Separate

If you want separate deployments:

### Backend: Web Service (Free)
- Root: `umm-dashboard-react/backend`
- Build: `npm install`
- Start: `npm start`

### Frontend: Static Site (Free)
- Root: `umm-dashboard-react/frontend`
- Build: `npm install && npm run build`
- Publish: `build`

Then update frontend to point to backend URL:
```javascript
// In frontend, create .env.production
REACT_APP_API_URL=https://your-backend.onrender.com
```

## 📚 Resources

- [Render Docs](https://render.com/docs)
- [Render Free Tier](https://render.com/docs/free)
- [Git LFS](https://git-lfs.github.com/)
- [Node.js on Render](https://render.com/docs/deploy-node-express-app)

## ✅ Checklist

- [ ] Code pushed to GitHub
- [ ] Data files committed
- [ ] Render account created
- [ ] Web Service deployed
- [ ] Environment variables set
- [ ] App tested and working
- [ ] (Optional) UptimeRobot configured

## 🎉 You're Done!

Your dashboard is now live and free! Share your URL:
`https://umm-dashboard.onrender.com`
