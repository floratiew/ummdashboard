# UMM and Water Values Dashboard - Quick Start Guide

## Overview
This prototype combines the UMM (Urgent Market Messages) dashboard and Water Values monitoring system into a single, self-contained web application. It's designed for demonstration to your manager.

## What's Included

### Features:
1. **Login System** - Simple authentication (any username/password works for demo)
2. **Water Values Dashboard** - Shows:
   - Power plant production statistics
   - Water value calculations  
   - Production intervals
   - Day-ahead and intra-day pricing
   - Interactive charts and data tables
3. **UMM Dashboard** - Displays:
   - Urgent market messages
   - Outage tracking
   - Capacity statistics
   - Advanced filtering

### Technology:
- **Backend**: Node.js + Express
- **Frontend**: React + Material-UI  
- **Database**: SQLite (for UMM data)
- **Charts**: Chart.js

## How to Run

### Method 1: One-Step Launch (Easiest)
```bash
cd /Users/yenkai/Desktop/ummdashboard/main_prototype
./start.sh
```

This will:
- Install any missing dependencies
- Start both backend (port 5000) and frontend (port 3000)
- Open your browser automatically

### Method 2: Manual Start
```bash
# From main_prototype directory
npm start
```

### Method 3: Separate Terminals
```bash
# Terminal 1 - Backend
cd main_prototype/backend
npm start

# Terminal 2 - Frontend  
cd main_prototype/frontend
npm start
```

## Using the Application

1. **Login**:
   - Go to `http://localhost:3000`
   - Enter ANY username and password (e.g., `admin`/`admin`)
   - Click "Sign In"

2. **Water Values Page** (Default landing page):
   - View aggregate production statistics
   - See power plant details in the table
   - Check day-ahead price charts for NO5 and NO2 areas
   - Monitor water values and efficiency metrics

3. **UMM Messages Page**:
   - Click "UMM Messages" in the sidebar
   - View message statistics
   - Filter by area, publisher, message type, or search text
   - See yearly statistics chart
   - Browse paginated message table

4. **Logout**:
   - Click "Logout" in the sidebar

## Project Structure

```
main_prototype/
├── README.md                    # Full documentation
├── package.json                 # Root scripts
├── start.sh                     # One-click startup script
├── backend/
│   ├── server.js               # Express API server
│   ├── package.json
│   └── data/
│       ├── plants_config.json   # Power plant configs
│       ├── prices.json          # Price data
│       ├── production_summary.json
│       └── umm_messages.db      # SQLite database
└── frontend/
    ├── package.json
    ├── public/
    │   └── index.html
    └── src/
        ├── App.js              # Main app + routing
        ├── index.js
        └── components/
            ├── LoginPage.js
            ├── DashboardLayout.js
            ├── WaterValuesPage.js
            └── UMMPage.js
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with any credentials

### Water Values  
- `GET /api/watervalues/plants` - Get plant configurations
- `GET /api/watervalues/summary` - Get production summary
- `GET /api/watervalues/prices` - Get price data

### UMM
- `GET /api/umm/messages` - Get filtered messages
- `GET /api/umm/stats` - Get statistics
- `GET /api/umm/filters` - Get filter options
- `GET /api/umm/yearly-stats` - Get yearly data

## Troubleshooting

### Ports Already in Use
If ports 3000 or 5000 are busy:
```bash
# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Find and kill process on port 5000
lsof -ti:5000 | xargs kill -9
```

### Dependencies Not Installed
```bash
cd main_prototype
npm run install-all
```

### Database Not Loading
- Check that `backend/data/umm_messages.db` exists
- File size should be several MB
- If missing, copy from `/Users/yenkai/Desktop/ummdashboard/data/`

### Browser Cache Issues
- Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- Or clear browser cache

## Demo Tips for Your Manager

1. **Start with Login** - Show the professional login interface
2. **Water Values Page** - Highlight:
   - Real-time production monitoring
   - Water value calculations  
   - Price charts for different areas
   - Comprehensive plant data table
3. **UMM Page** - Demonstrate:
   - Message filtering capabilities
   - Statistics dashboard
   - Yearly trends visualization
   - Detailed message browser
4. **Navigation** - Show the clean sidebar navigation
5. **Responsiveness** - Resize browser to show mobile-friendly design

## Notes

- This is a **prototype** for demonstration purposes
- Authentication is simplified (accepts any credentials)
- Data is loaded from static JSON files and SQLite database
- All code is self-contained in the `main_prototype` folder
- No external APIs or services required

## Next Steps (Optional Enhancements)

If you want to improve the prototype:
1. Add real authentication with user management
2. Connect to live data sources/APIs
3. Add more detailed water value calculations
4. Implement data export features
5. Add user preferences and settings
6. Create production build for deployment

## Support

For issues or questions:
- Check the README.md for detailed documentation
- Review console logs in browser developer tools
- Check terminal output for backend errors
- Verify all dependencies are installed correctly

---

**Ready to go!** Just run `./start.sh` and open `http://localhost:3000` in your browser.
