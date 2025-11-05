const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const csv = require('csv-parser');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files from React build
app.use(express.static(path.join(__dirname, '../frontend/build')));

// In-memory data storage
let ummMessages = [];
let dataLoaded = false;

// Load CSV data
function loadCSVData() {
  return new Promise((resolve, reject) => {
    const messages = [];
    const csvPath = path.join(__dirname, 'data/umm_area_outage_events.csv');
    
    if (!fs.existsSync(csvPath)) {
      console.error(`CSV file not found: ${csvPath}`);
      resolve([]);
      return;
    }

    fs.createReadStream(csvPath)
      .pipe(csv())
      .on('data', (row) => {
        // Transform CSV row to match expected format
        messages.push({
          message_id: messages.length + 1,
          area_names: row.area || '',
          unavailable_mw: parseFloat(row.mw) || 0,
          installed_mw: parseFloat(row.mw) || 0,
          available_mw: 0,
          event_status: row.status || 'Unknown',
          publication_date: row.publication_date || '',
          message_text: row.remarks || '',
          message_type: getMessageType(row.status),
          message_type_name: getMessageTypeName(row.status),
          publisher_name: 'System Operator',
          production_unit_names: '',
          generation_unit_names: '',
          fuel_type: 'Unknown'
        });
      })
      .on('end', () => {
        console.log(`Loaded ${messages.length} UMM messages from CSV`);
        resolve(messages);
      })
      .on('error', (error) => {
        console.error('Error reading CSV:', error);
        reject(error);
      });
  });
}

function getMessageType(status) {
  const statusMap = {
    'Planned': 1,
    'Unplanned': 2,
    'Unknown': 3
  };
  return statusMap[status] || 3;
}

function getMessageTypeName(status) {
  return status || 'Unknown';
}

// Initialize data
async function initData() {
  try {
    ummMessages = await loadCSVData();
    dataLoaded = true;
    console.log('Data initialization complete');
  } catch (error) {
    console.error('Failed to initialize data:', error);
    dataLoaded = false;
  }
}

// ============================================================
// AUTHENTICATION ROUTES
// ============================================================

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  
  if (username && password) {
    res.json({
      success: true,
      message: 'Login successful',
      user: {
        username,
        token: 'prototype-token-' + Date.now()
      }
    });
  } else {
    res.status(400).json({
      success: false,
      message: 'Username and password required'
    });
  }
});

// ============================================================
// WATER VALUES ROUTES
// ============================================================

app.get('/api/watervalues/plants', (req, res) => {
  try {
    const plantsPath = path.join(__dirname, 'data/plants_config.json');
    if (fs.existsSync(plantsPath)) {
      const plants = JSON.parse(fs.readFileSync(plantsPath, 'utf8'));
      res.json(plants);
    } else {
      res.json([]);
    }
  } catch (error) {
    console.error('Error loading plants:', error);
    res.status(500).json({ error: 'Failed to load plant configurations' });
  }
});

app.get('/api/watervalues/summary', (req, res) => {
  try {
    const summaryPath = path.join(__dirname, 'data/production_summary.json');
    if (fs.existsSync(summaryPath)) {
      const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
      res.json(summary);
    } else {
      res.json({});
    }
  } catch (error) {
    console.error('Error loading production summary:', error);
    res.status(500).json({ error: 'Failed to load production summary' });
  }
});

app.get('/api/watervalues/production/:plantId', (req, res) => {
  try {
    const { plantId } = req.params;
    const productionPath = path.join(__dirname, `data/production_${plantId}.json`);
    
    if (fs.existsSync(productionPath)) {
      const production = JSON.parse(fs.readFileSync(productionPath, 'utf8'));
      res.json(production);
    } else {
      res.json({ production: [], waterValues: [] });
    }
  } catch (error) {
    console.error(`Error loading production data for ${req.params.plantId}:`, error);
    res.status(500).json({ error: 'Failed to load production data' });
  }
});

app.get('/api/watervalues/prices', (req, res) => {
  try {
    const pricesPath = path.join(__dirname, 'data/prices.json');
    if (fs.existsSync(pricesPath)) {
      const prices = JSON.parse(fs.readFileSync(pricesPath, 'utf8'));
      res.json(prices);
    } else {
      res.json({});
    }
  } catch (error) {
    console.error('Error loading prices:', error);
    res.status(500).json({ error: 'Failed to load price data' });
  }
});

// ============================================================
// UMM ROUTES
// ============================================================

app.get('/api/umm/messages', (req, res) => {
  if (!dataLoaded) {
    return res.status(503).json({ error: 'Data not loaded yet' });
  }

  try {
    const {
      startDate,
      endDate,
      messageType,
      area,
      publisher,
      search,
      limit = 1000,
      offset = 0
    } = req.query;
    
    let filtered = [...ummMessages];
    
    // Apply filters
    if (startDate) {
      filtered = filtered.filter(m => m.publication_date >= startDate);
    }
    if (endDate) {
      filtered = filtered.filter(m => m.publication_date <= endDate);
    }
    if (messageType) {
      filtered = filtered.filter(m => m.message_type === parseInt(messageType));
    }
    if (area) {
      filtered = filtered.filter(m => m.area_names.includes(area));
    }
    if (publisher) {
      filtered = filtered.filter(m => m.publisher_name.toLowerCase().includes(publisher.toLowerCase()));
    }
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(m => 
        m.message_text.toLowerCase().includes(searchLower) ||
        m.publisher_name.toLowerCase().includes(searchLower) ||
        m.area_names.toLowerCase().includes(searchLower)
      );
    }
    
    // Sort by publication date descending
    filtered.sort((a, b) => new Date(b.publication_date) - new Date(a.publication_date));
    
    const total = filtered.length;
    const paginatedMessages = filtered.slice(parseInt(offset), parseInt(offset) + parseInt(limit));
    
    // Format messages for frontend
    const formattedMessages = paginatedMessages.map(m => ({
      ...m,
      area_names: m.area_names ? m.area_names.split(',').map(a => a.trim()) : [],
      production_unit_names: m.production_unit_names ? m.production_unit_names.split(',').map(a => a.trim()) : [],
      generation_unit_names: m.generation_unit_names ? m.generation_unit_names.split(',').map(a => a.trim()) : [],
      installedMW: m.installed_mw,
      unavailableMW: m.unavailable_mw,
      availableMW: m.available_mw,
      fuelType: m.fuel_type
    }));
    
    res.json({
      messages: formattedMessages,
      total,
      limit: parseInt(limit),
      offset: parseInt(offset)
    });
  } catch (error) {
    console.error('Error fetching UMM messages:', error);
    res.status(500).json({ error: 'Failed to fetch messages' });
  }
});

app.get('/api/umm/stats', (req, res) => {
  if (!dataLoaded) {
    return res.status(503).json({ error: 'Data not loaded yet' });
  }

  try {
    const totalMessages = ummMessages.length;
    const activeOutages = ummMessages.filter(m => 
      m.event_status === 'Active' || m.event_status === 'Unplanned'
    ).length;
    const totalCapacity = ummMessages.reduce((sum, m) => sum + (m.installed_mw || 0), 0);
    const unavailableCapacity = ummMessages
      .filter(m => m.event_status === 'Active' || m.event_status === 'Unplanned')
      .reduce((sum, m) => sum + (m.unavailable_mw || 0), 0);
    
    res.json({
      totalMessages,
      activeOutages,
      totalCapacity,
      unavailableCapacity
    });
  } catch (error) {
    console.error('Error fetching UMM stats:', error);
    res.status(500).json({ error: 'Failed to fetch statistics' });
  }
});

app.get('/api/umm/filters', (req, res) => {
  if (!dataLoaded) {
    return res.status(503).json({ error: 'Data not loaded yet' });
  }

  try {
    const areaSet = new Set();
    const publisherSet = new Set();
    const messageTypeMap = new Map();
    
    ummMessages.forEach(m => {
      if (m.area_names) {
        m.area_names.split(',').forEach(area => areaSet.add(area.trim()));
      }
      if (m.publisher_name) {
        publisherSet.add(m.publisher_name);
      }
      if (m.message_type && m.message_type_name) {
        messageTypeMap.set(m.message_type, m.message_type_name);
      }
    });
    
    const messageTypes = Array.from(messageTypeMap.entries()).map(([id, name]) => ({
      id,
      name
    }));
    
    res.json({
      areas: Array.from(areaSet).sort(),
      publishers: Array.from(publisherSet).sort(),
      messageTypes
    });
  } catch (error) {
    console.error('Error fetching UMM filters:', error);
    res.status(500).json({ error: 'Failed to fetch filter options' });
  }
});

app.get('/api/umm/yearly-stats', (req, res) => {
  if (!dataLoaded) {
    return res.status(503).json({ error: 'Data not loaded yet' });
  }

  try {
    const yearlyStats = {};
    
    ummMessages.forEach(m => {
      if (m.publication_date) {
        const year = new Date(m.publication_date).getFullYear();
        if (!yearlyStats[year]) {
          yearlyStats[year] = { year: year.toString(), count: 0, outages: 0 };
        }
        yearlyStats[year].count++;
        if (m.message_type === 1 || m.message_type === 2 || m.message_type === 3) {
          yearlyStats[year].outages++;
        }
      }
    });
    
    const results = Object.values(yearlyStats).sort((a, b) => a.year.localeCompare(b.year));
    res.json(results);
  } catch (error) {
    console.error('Error fetching yearly stats:', error);
    res.status(500).json({ error: 'Failed to fetch yearly statistics' });
  }
});

// ============================================================
// CATCH-ALL ROUTE (must be last)
// ============================================================
app.get('*', (req, res) => {
  const indexPath = path.join(__dirname, '../frontend/build/index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('Application not built. Run npm run build in frontend directory.');
  }
});

// Initialize data and start server
initData().then(() => {
  app.listen(PORT, () => {
    console.log(`✓ Server running on port ${PORT}`);
    console.log(`✓ API available at http://localhost:${PORT}/api`);
    console.log(`✓ Loaded ${ummMessages.length} UMM messages`);
  });
});
