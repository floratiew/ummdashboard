# UMM Dashboard

Nord Pool UMM (Urgent Market Messages) Dashboard - React + Node.js

## 🚀 Deployment on Render (FREE)

### Quick Deploy
1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" → "Web Service"
4. Connect your GitHub repo (`umm-dashboard-react` folder)
5. Use these settings:
   - **Name**: `umm-dashboard`
   - **Environment**: `Node`
   - **Build Command**: `npm run render-build`
   - **Start Command**: `npm run render-start`
   - **Instance Type**: `Free`

### Environment Variables (Optional)
- `NODE_ENV`: `production`
- `PORT`: (Leave empty, Render sets this automatically)

### ⚠️ Note about Free Tier
- Spins down after 15 minutes of inactivity
- Takes ~30 seconds to wake up on first request
- Perfect for demos and testing!

## 💻 Local Development

```bash
# Install all dependencies
npm run install-all

# Run backend only (http://localhost:5001)
npm run dev:backend

# Run frontend only (http://localhost:3001)
npm run dev:frontend
```

## 📁 Project Structure

```
umm-dashboard-react/
├── frontend/          # React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardView.js
│   │   │   ├── ProductionUnitsView.js
│   │   │   └── OutagesView.js
│   │   └── App.js
│   └── package.json
├── backend/           # Express API
│   ├── server.js
│   └── package.json
├── data/              # CSV data files
│   └── umm_messages1.csv
└── package.json       # Root build scripts
```

## 🔧 Tech Stack

- **Frontend**: React 18, Material-UI 5, Chart.js 4
- **Backend**: Node.js, Express 4, CSV Parser
- **Deployment**: Render (Free tier)

## 📊 Features

- 📋 Real-time UMM message dashboard
- 🏭 Production unit analysis with year/type/status filters
- ⚡ Outage analysis with MW threshold filtering (100-2000 MW)
- 🌐 Full area rankings showing all areas before filtering
- 📈 Planned/Unplanned/Unknown breakdown with percentages
- 📊 Interactive stacked bar charts with rounded corners
- 🔍 Advanced filtering by year, area, message type
- 📱 Responsive dark theme with gradient UI

A modern, beautiful dashboard for visualizing Nord Pool UMM (Urgent Market Messages) data with React.js frontend and Node.js backend.

## 🎨 Features

- **Modern Material-UI Design**: Beautiful dark theme with gradient accents
- **Real-time Data Visualization**: Interactive charts and tables
- **Advanced Filtering**: Filter by date, area, publisher, message type
- **Production Unit Analysis**: Deep dive into specific production units
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Fast Performance**: Efficient data caching and pagination

## 📁 Project Structure

```
umm-dashboard-react/
├── backend/           # Node.js + Express API server
│   ├── server.js     # Main server file
│   └── package.json
├── frontend/          # React.js application
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardView.js
│   │   │   ├── ProductionUnitsView.js
│   │   │   └── OutagesView.js
│   │   ├── App.js
│   │   ├── index.js
│   │   └── index.css
│   └── package.json
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn
- CSV data file at `../../data/umm_messages1.csv`

### Installation

1. **Install Backend Dependencies**

```bash
cd backend
npm install
```

2. **Install Frontend Dependencies**

```bash
cd ../frontend
npm install
```

### Running the Application

#### Option 1: Run Both Servers Separately

**Terminal 1 - Start Backend Server:**
```bash
cd backend
npm start
```
Backend will run on http://localhost:5000

**Terminal 2 - Start Frontend Server:**
```bash
cd frontend
npm start
```
Frontend will run on http://localhost:3000

#### Option 2: Development Mode (with auto-restart)

**Backend (with nodemon):**
```bash
cd backend
npm run dev
```

**Frontend:**
```bash
cd frontend
npm start
```

### 🎯 Quick Start Commands

From the `umm-dashboard-react` directory:

```bash
# Install all dependencies
cd backend && npm install && cd ../frontend && npm install && cd ..

# Start backend (Terminal 1)
cd backend && npm start

# Start frontend (Terminal 2)
cd frontend && npm start
```

## 📊 API Endpoints

### Messages
- `GET /api/messages` - Get filtered messages
  - Query params: `startDate`, `endDate`, `messageType`, `area`, `publisher`, `search`, `limit`, `offset`

### Statistics
- `GET /api/stats` - Get overall statistics

### Filters
- `GET /api/filters` - Get all available filter options (areas, publishers, units)

### Units
- `GET /api/units/:unitName` - Get specific production unit details

### Charts
- `GET /api/charts/yearly` - Get yearly aggregated data

## 🎨 UI Features

### Dashboard View
- **Statistics Cards**: Total messages, publishers, areas, production units
- **Interactive Chart**: Messages over time
- **Advanced Filters**: Area, message type, publisher, search
- **Data Table**: Sortable, paginated table with capacity and fuel type info

### Production Units View
- **Unit Search**: Autocomplete search for production units
- **Unit Overview**: Location, capacity, owner, total events
- **Event History**: Complete timeline of unit-specific messages

### Outages View
- Coming soon: Outage trends, timeline analysis, impact assessment

## 🛠 Technology Stack

### Frontend
- **React 18** - UI framework
- **Material-UI (MUI)** - Component library
- **Chart.js** + **react-chartjs-2** - Data visualization
- **MUI DataGrid** - Advanced tables
- **Axios** - HTTP client

### Backend
- **Node.js** - Runtime environment
- **Express** - Web framework
- **csv-parser** - CSV file parsing
- **CORS** - Cross-origin resource sharing

## 🎨 Design Features

- **Dark Theme**: Professional dark mode with purple/blue gradients
- **Glass Morphism**: Modern translucent card designs
- **Smooth Animations**: Transitions and hover effects
- **Responsive Layout**: Mobile-first design
- **Color Palette**:
  - Primary: `#667eea` (Purple-blue)
  - Secondary: `#764ba2` (Deep purple)
  - Accent: `#f093fb` (Pink)
  - Background: `#0a0e27` (Dark blue)

## 📝 Data Format

The backend expects CSV data with these key fields:
- `message_id`, `publication_date`, `event_start`, `event_stop`
- `message_type`, `event_status`, `publisher_name`
- `production_units_json`, `generation_units_json`
- `areas_json`, `transmission_units_json`
- `remarks`, `unavailability_reason`

## 🔧 Configuration

### Backend Port
Change in `backend/server.js`:
```javascript
const PORT = process.env.PORT || 5000;
```

### Frontend Proxy
Frontend proxies API requests to backend. Change in `frontend/package.json`:
```json
"proxy": "http://localhost:5000"
```

## 🚀 Deployment

### Production Build

**Frontend:**
```bash
cd frontend
npm run build
```
Creates optimized production build in `frontend/build/`

**Backend:**
```bash
cd backend
NODE_ENV=production node server.js
```

## 📄 License

ISC

## 🙏 Credits

Built for Nord Pool UMM data analysis and visualization.

---

**Enjoy your beautiful new dashboard! 🎉**
