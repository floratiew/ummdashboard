# UMM and Water Values Dashboard Prototype

A self-contained web application prototype that combines the UMM (Urgent Market Messages) dashboard and Water Values monitoring system.

## Features

- **Login Page**: Simple authentication (accepts any username/password for prototype purposes)
- **Water Values Dashboard**: 
  - Real-time power plant production monitoring
  - Water value calculations
  - Production interval analysis
  - Day-ahead and intra-day price tracking
  - Interactive charts and data tables
- **UMM Dashboard**: 
  - Urgent market messages monitoring
  - Outage tracking and analysis
  - Capacity availability statistics
  - Advanced filtering capabilities

## Technology Stack

- **Backend**: Node.js + Express
- **Frontend**: React + Material-UI
- **Database**: SQLite
- **Charts**: Chart.js + react-chartjs-2

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn

## Installation

1. Navigate to the main_prototype directory:
```bash
cd main_prototype
```

2. Install backend dependencies:
```bash
cd backend
npm install
```

3. Install frontend dependencies:
```bash
cd ../frontend
npm install
```

## Running the Application

### Option 1: Run Both Services Simultaneously (Recommended)

From the `main_prototype` directory:
```bash
npm start
```

This will start both the backend server (port 5000) and frontend development server (port 3000).

### Option 2: Run Services Separately

**Terminal 1 - Backend:**
```bash
cd backend
npm start
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

## Accessing the Application

1. Open your browser and navigate to: `http://localhost:3000`
2. Login with any username and password (e.g., username: `admin`, password: `admin`)
3. You'll be redirected to the Water Values dashboard
4. Use the sidebar navigation to switch between pages

## Project Structure

```
main_prototype/
├── backend/
│   ├── server.js              # Express server
│   ├── package.json
│   └── data/
│       ├── plants_config.json  # Power plant configurations
│       ├── prices.json         # Price data
│       ├── production_summary.json
│       └── umm_messages.db     # SQLite database for UMM data
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js              # Main app component with routing
│   │   ├── index.js
│   │   ├── index.css
│   │   └── components/
│   │       ├── LoginPage.js
│   │       ├── DashboardLayout.js
│   │       ├── WaterValuesPage.js
│   │       └── UMMPage.js
│   └── package.json
├── package.json               # Root package with scripts
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (accepts any credentials)

### Water Values
- `GET /api/watervalues/plants` - Get plant configurations
- `GET /api/watervalues/summary` - Get production summary
- `GET /api/watervalues/production/:plantId` - Get plant production data
- `GET /api/watervalues/prices` - Get price data

### UMM
- `GET /api/umm/messages` - Get UMM messages (with filtering)
- `GET /api/umm/stats` - Get UMM statistics
- `GET /api/umm/filters` - Get available filter options
- `GET /api/umm/yearly-stats` - Get yearly statistics

## Notes

- This is a prototype application designed for demonstration purposes
- Authentication is simplified and accepts any credentials
- Data is loaded from static JSON files and SQLite database
- The application is self-contained within the `main_prototype` folder

## Troubleshooting

If you encounter any issues:

1. Make sure all dependencies are installed:
   ```bash
   cd backend && npm install
   cd ../frontend && npm install
   ```

2. Check that ports 3000 and 5000 are available

3. Ensure the SQLite database file exists at `backend/data/umm_messages.db`

4. Clear browser cache and restart the servers if needed
