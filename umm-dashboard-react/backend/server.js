const express = require('express');
const cors = require('cors');
const fs = require('fs');
const csv = require('csv-parser');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5001;

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files from React build (for production)
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../frontend/build')));
}

// Path to CSV data
const CSV_PATH = path.join(__dirname, '../../data/umm_messages1.csv');

// Helper function to parse JSON strings
const parseJSON = (value) => {
  if (!value || value === 'null' || value === '') return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch (e) {
    return [];
  }
};

// Helper function to extract area names from all sources
const extractAreaNames = (row) => {
  const areas = new Set();
  
  // From areas_json
  parseJSON(row.areas_json).forEach(item => {
    if (item.name) areas.add(item.name);
  });
  
  // From production_units_json
  parseJSON(row.production_units_json).forEach(item => {
    if (item.areaName) areas.add(item.areaName);
  });
  
  // From generation_units_json
  parseJSON(row.generation_units_json).forEach(item => {
    if (item.areaName) areas.add(item.areaName);
  });
  
  // From transmission_units_json
  parseJSON(row.transmission_units_json).forEach(item => {
    if (item.inAreaName) areas.add(item.inAreaName);
    if (item.outAreaName) areas.add(item.outAreaName);
  });
  
  return Array.from(areas).sort();
};

// Helper function to extract unit names
const extractUnitNames = (jsonArray) => {
  const names = new Set();
  parseJSON(jsonArray).forEach(item => {
    const name = item.name || item.productionUnitName || item.generationUnitName;
    if (name) names.add(name);
  });
  return Array.from(names).sort();
};

// Helper function to extract capacity info
const extractCapacityInfo = (row) => {
  let totalInstalled = 0;
  let totalUnavailable = 0;
  let totalAvailable = 0;
  const fuelTypes = new Set();
  
  const fuelMap = {
    1: "Nuclear", 2: "Lignite", 3: "Hard Coal", 4: "Natural Gas",
    5: "Oil", 6: "Biomass", 7: "Geothermal", 8: "Waste",
    9: "Wind Onshore", 10: "Wind Offshore", 11: "Solar", 12: "Hydro",
    13: "Pumped Storage", 14: "Marine", 15: "Other"
  };
  
  // Process production units
  parseJSON(row.production_units_json).forEach(unit => {
    totalInstalled += unit.installedCapacity || 0;
    if (unit.fuelType) fuelTypes.add(fuelMap[unit.fuelType] || `Type ${unit.fuelType}`);
    if (unit.timePeriods && unit.timePeriods[0]) {
      totalUnavailable += unit.timePeriods[0].unavailableCapacity || 0;
      totalAvailable += unit.timePeriods[0].availableCapacity || 0;
    }
  });
  
  // Process generation units
  parseJSON(row.generation_units_json).forEach(unit => {
    totalInstalled += unit.installedCapacity || 0;
    if (unit.fuelType) fuelTypes.add(fuelMap[unit.fuelType] || `Type ${unit.fuelType}`);
    if (unit.timePeriods && unit.timePeriods[0]) {
      totalUnavailable += unit.timePeriods[0].unavailableCapacity || 0;
      totalAvailable += unit.timePeriods[0].availableCapacity || 0;
    }
  });
  
  return {
    installedMW: totalInstalled > 0 ? totalInstalled : null,
    unavailableMW: totalUnavailable > 0 ? totalUnavailable : null,
    availableMW: totalAvailable > 0 ? totalAvailable : null,
    fuelType: Array.from(fuelTypes).sort().join(', ') || null
  };
};

// Calculate duration
const calculateDuration = (start, stop) => {
  if (!start || !stop) return null;
  const duration = new Date(stop) - new Date(start);
  const hours = duration / (1000 * 60 * 60);
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
};

// Load and cache data
let cachedData = null;
let cacheTime = null;
const CACHE_DURATION = 10 * 60 * 1000; // 10 minutes (longer to reduce reloads)

const loadData = () => {
  return new Promise((resolve, reject) => {
    // Check cache
    if (cachedData && cacheTime && Date.now() - cacheTime < CACHE_DURATION) {
      console.log(`Using cached data (${cachedData.length} rows)`);
      return resolve(cachedData);
    }
    
    // Check memory before loading
    const memUsage = process.memoryUsage();
    console.log(`Memory before load: ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB / ${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`);
    
    const data = [];
    fs.createReadStream(CSV_PATH)
      .pipe(csv())
      .on('data', (row) => {
        const areas = extractAreaNames(row);
        const productionUnits = extractUnitNames(row.production_units_json);
        const generationUnits = extractUnitNames(row.generation_units_json);
        const capacity = extractCapacityInfo(row);
        const duration = calculateDuration(row.event_start, row.event_stop);
        
        data.push({
          ...row,
          area_names: areas,
          production_unit_names: productionUnits,
          generation_unit_names: generationUnits,
          ...capacity,
          duration
        });
      })
      .on('end', () => {
        cachedData = data;
        cacheTime = Date.now();
        
        const memUsage = process.memoryUsage();
        console.log(`✅ Loaded ${data.length} messages`);
        console.log(`Memory after load: ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB / ${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`);
        console.log(`RSS: ${Math.round(memUsage.rss / 1024 / 1024)}MB`);
        
        // Force garbage collection if available
        if (global.gc) {
          global.gc();
          console.log('Garbage collection triggered');
        }
        
        resolve(data);
      })
      .on('error', (err) => {
        console.error('❌ Error loading CSV:', err);
        reject(err);
      });
  });
};

// API Routes

// Get all messages with filters
app.get('/api/messages', async (req, res) => {
  try {
    const data = await loadData();
    const {
      startDate,
      endDate,
      messageType,
      area,
      publisher,
      search,
      limit = 999999, // Return all messages by default
      offset = 0
    } = req.query;
    
    let filtered = data;
    
    // Apply filters
    if (startDate) {
      filtered = filtered.filter(row => new Date(row.publication_date) >= new Date(startDate));
    }
    if (endDate) {
      filtered = filtered.filter(row => new Date(row.publication_date) <= new Date(endDate));
    }
    if (messageType) {
      filtered = filtered.filter(row => row.message_type === messageType);
    }
    if (area) {
      filtered = filtered.filter(row => row.area_names.includes(area));
    }
    if (publisher) {
      filtered = filtered.filter(row => row.publisher_name === publisher);
    }
    if (search) {
      filtered = filtered.filter(row => 
        row.remarks?.toLowerCase().includes(search.toLowerCase())
      );
    }
    
    // Sort by publication date (newest first)
    filtered.sort((a, b) => new Date(b.publication_date) - new Date(a.publication_date));
    
    // Paginate
    const total = filtered.length;
    const paginated = filtered.slice(parseInt(offset), parseInt(offset) + parseInt(limit));
    
    res.json({
      data: paginated,
      total,
      limit: parseInt(limit),
      offset: parseInt(offset)
    });
  } catch (error) {
    console.error('Error loading messages:', error);
    res.status(500).json({ error: 'Failed to load messages' });
  }
});

// Get statistics
app.get('/api/stats', async (req, res) => {
  try {
    const data = await loadData();
    
    const stats = {
      totalMessages: data.length,
      publishers: [...new Set(data.map(row => row.publisher_name).filter(Boolean))].length,
      areas: [...new Set(data.flatMap(row => row.area_names))].length,
      productionUnits: [...new Set(data.flatMap(row => row.production_unit_names))].length,
      messageTypes: {}
    };
    
    // Count message types
    data.forEach(row => {
      const type = row.message_type;
      stats.messageTypes[type] = (stats.messageTypes[type] || 0) + 1;
    });
    
    res.json(stats);
  } catch (error) {
    console.error('Error loading stats:', error);
    res.status(500).json({ error: 'Failed to load statistics' });
  }
});

// Get unique values for filters
app.get('/api/filters', async (req, res) => {
  try {
    const data = await loadData();
    
    const filters = {
      areas: [...new Set(data.flatMap(row => row.area_names))].sort(),
      publishers: [...new Set(data.map(row => row.publisher_name).filter(Boolean))].sort(),
      messageTypes: [...new Set(data.map(row => row.message_type).filter(Boolean))],
      units: [...new Set([
        ...data.flatMap(row => row.production_unit_names),
        ...data.flatMap(row => row.generation_unit_names)
      ])].sort()
    };
    
    res.json(filters);
  } catch (error) {
    console.error('Error loading filters:', error);
    res.status(500).json({ error: 'Failed to load filters' });
  }
});

// Get production unit analysis
app.get('/api/units/:unitName', async (req, res) => {
  try {
    const data = await loadData();
    const { unitName } = req.params;
    const { year, messageType, plannedStatus } = req.query;
    
    let unitData = data.filter(row => 
      row.production_unit_names.includes(unitName) ||
      row.generation_unit_names.includes(unitName)
    );
    
    if (unitData.length === 0) {
      return res.status(404).json({ error: 'Unit not found' });
    }
    
    // Calculate message type breakdown BEFORE filtering
    const messageTypeBreakdown = {};
    const messageTypeLabels = {
      '1': 'Production unavailability',
      '2': 'Consumption unavailability',
      '3': 'Transmission outage',
      '4': 'Market notice',
      '5': 'Other'
    };
    unitData.forEach(row => {
      const type = row.message_type;
      const label = messageTypeLabels[type] || 'Other';
      messageTypeBreakdown[label] = (messageTypeBreakdown[label] || 0) + 1;
    });
    
    // Extract unit info from first few rows for capacity/area
    let unitInfo = { areas: new Set(), capacity: null, owner: null, publishers: new Set() };
    for (const row of unitData.slice(0, 10)) {
      const prodUnits = parseJSON(row.production_units_json);
      const genUnits = parseJSON(row.generation_units_json);
      
      [...prodUnits, ...genUnits].forEach(unit => {
        const name = unit.name || unit.productionUnitName || unit.generationUnitName;
        if (name === unitName) {
          if (unit.areaName) unitInfo.areas.add(unit.areaName);
          if (!unitInfo.capacity && unit.installedCapacity) {
            unitInfo.capacity = unit.installedCapacity;
          }
        }
      });
    }
    
    // Get all unique publishers from ALL events
    unitData.forEach(row => {
      if (row.publisher_name) {
        unitInfo.publishers.add(row.publisher_name);
        if (!unitInfo.owner) unitInfo.owner = row.publisher_name;
      }
    });
    
    // Get all affected areas from events and count events per area
    const affectedAreas = new Set();
    const areaEventCounts = {};
    unitData.forEach(row => {
      row.area_names.forEach(area => {
        affectedAreas.add(area);
        areaEventCounts[area] = (areaEventCounts[area] || 0) + 1;
      });
    });
    
    // Convert to array format for charting
    const areaBreakdown = Object.keys(areaEventCounts).sort().map(area => ({
      area,
      count: areaEventCounts[area]
    }));
    
    // Calculate yearly breakdown - apply message type filter if specified
    let dataForYearlyCalc = unitData;
    if (messageType) {
      dataForYearlyCalc = unitData.filter(row => 
        row.message_type === parseInt(messageType)
      );
    }
    
    const yearlyBreakdown = {};
    dataForYearlyCalc.forEach(row => {
      const eventYear = new Date(row.publication_date).getFullYear();
      const msgType = row.message_type;
      
      if (!yearlyBreakdown[eventYear]) {
        yearlyBreakdown[eventYear] = {};
      }
      yearlyBreakdown[eventYear][msgType] = (yearlyBreakdown[eventYear][msgType] || 0) + 1;
    });
    
    // Convert to array format for charting
    const yearlyData = Object.keys(yearlyBreakdown).sort().map(yr => ({
      year: parseInt(yr),
      counts: yearlyBreakdown[yr],
      total: Object.values(yearlyBreakdown[yr]).reduce((a, b) => a + b, 0)
    }));
    
    // Calculate planned/unplanned breakdown
    const plannedKeywords = ['planned', 'maintenance', 'scheduled'];
    const unplannedKeywords = ['unplanned', 'unexpected', 'fault', 'failure', 'emergency'];
    
    const plannedUnplannedBreakdown = {
      'Planned': 0,
      'Unplanned': 0,
      'Unknown': 0
    };
    
    unitData.forEach(row => {
      const unavailabilityType = row.unavailability_type ? parseFloat(row.unavailability_type) : null;
      
      if (unavailabilityType === 1) {
        plannedUnplannedBreakdown['Planned']++;
      } else if (unavailabilityType === 2) {
        plannedUnplannedBreakdown['Unplanned']++;
      } else {
        const remarks = (row.remarks || '').toLowerCase();
        const isPlanned = plannedKeywords.some(kw => remarks.includes(kw));
        const isUnplanned = unplannedKeywords.some(kw => remarks.includes(kw));
        
        if (isPlanned) {
          plannedUnplannedBreakdown['Planned']++;
        } else if (isUnplanned) {
          plannedUnplannedBreakdown['Unplanned']++;
        } else {
          plannedUnplannedBreakdown['Unknown']++;
        }
      }
    });
    
    // Filter by year, message type, and planned status if specified
    let filteredEvents = unitData;
    if (year) {
      filteredEvents = filteredEvents.filter(row => {
        const eventYear = new Date(row.publication_date).getFullYear();
        return eventYear === parseInt(year);
      });
    }
    if (messageType) {
      filteredEvents = filteredEvents.filter(row => row.message_type === messageType);
    }
    if (plannedStatus) {
      filteredEvents = filteredEvents.filter(row => {
        const unavailabilityType = row.unavailability_type ? parseFloat(row.unavailability_type) : null;
        const remarks = (row.remarks || '').toLowerCase();
        
        if (plannedStatus === 'Planned') {
          if (unavailabilityType === 1) return true;
          return plannedKeywords.some(kw => remarks.includes(kw));
        } else if (plannedStatus === 'Unplanned') {
          if (unavailabilityType === 2) return true;
          return unplannedKeywords.some(kw => remarks.includes(kw));
        } else if (plannedStatus === 'Unknown') {
          if (unavailabilityType === 1 || unavailabilityType === 2) return false;
          const isPlanned = plannedKeywords.some(kw => remarks.includes(kw));
          const isUnplanned = unplannedKeywords.some(kw => remarks.includes(kw));
          return !isPlanned && !isUnplanned;
        }
        return true;
      });
    }
    
    res.json({
      unitName,
      areas: Array.from(unitInfo.areas),
      capacity: unitInfo.capacity,
      owner: unitInfo.owner,
      totalEvents: unitData.length,
      filteredEvents: filteredEvents.length,
      affectedAreas: Array.from(affectedAreas).length,
      uniquePublishers: unitInfo.publishers.size,
      publishers: Array.from(unitInfo.publishers),
      messageTypeBreakdown,
      plannedUnplannedBreakdown,
      yearlyData,
      areaBreakdown,
      availableYears: Object.keys(yearlyBreakdown).sort(),
      events: filteredEvents.slice(0, 100) // Return first 100 events
    });
  } catch (error) {
    console.error('Error loading unit data:', error);
    res.status(500).json({ error: 'Failed to load unit data' });
  }
});

// Get yearly data for charts
app.get('/api/charts/yearly', async (req, res) => {
  try {
    const data = await loadData();
    const { area, messageType } = req.query;
    
    let filtered = data;
    if (area) filtered = filtered.filter(row => row.area_names.includes(area));
    if (messageType) filtered = filtered.filter(row => row.message_type === messageType);
    
    const yearlyData = {};
    filtered.forEach(row => {
      const year = new Date(row.publication_date).getFullYear();
      yearlyData[year] = (yearlyData[year] || 0) + 1;
    });
    
    const chartData = Object.keys(yearlyData).sort().map(year => ({
      year: parseInt(year),
      count: yearlyData[year]
    }));
    
    res.json(chartData);
  } catch (error) {
    console.error('Error loading yearly data:', error);
    res.status(500).json({ error: 'Failed to load yearly data' });
  }
});

// Area outage events endpoint
app.get('/api/outages/area-events', async (req, res) => {
  try {
    const OUTAGE_EVENTS_PATH = path.join(__dirname, '../../data/umm_area_outage_events.csv');
    
    if (!fs.existsSync(OUTAGE_EVENTS_PATH)) {
      return res.status(404).json({ error: 'Area outage events file not found' });
    }

    const { mwThreshold = 400, status = 'Both', areas } = req.query;
    const results = [];

    await new Promise((resolve, reject) => {
      fs.createReadStream(OUTAGE_EVENTS_PATH)
        .pipe(csv())
        .on('data', (data) => {
          results.push({
            area: data.area,
            mw: parseFloat(data.mw) || 0,
            status: data.status,
            publicationDate: data.publication_date,
            remarks: data.remarks
          });
        })
        .on('end', resolve)
        .on('error', reject);
    });

    // Apply filters
    let filtered = results.filter(event => event.mw >= parseFloat(mwThreshold));
    
    if (status !== 'Both') {
      filtered = filtered.filter(event => event.status === status);
    }
    
    if (areas) {
      const areaList = areas.split(',');
      filtered = filtered.filter(event => areaList.includes(event.area));
    }

    // Get summary by area
    const areaStats = {};
    filtered.forEach(event => {
      if (!areaStats[event.area]) {
        areaStats[event.area] = { area: event.area, totalMW: 0, count: 0 };
      }
      areaStats[event.area].totalMW += event.mw;
      areaStats[event.area].count += 1;
    });

    const summary = Object.values(areaStats).sort((a, b) => b.totalMW - a.totalMW);
    
    // Get unique areas for filter
    const uniqueAreas = [...new Set(results.map(e => e.area))].sort();

    res.json({
      events: filtered,
      summary,
      uniqueAreas,
      totalEvents: filtered.length
    });
  } catch (error) {
    console.error('Error loading area outage events:', error);
    res.status(500).json({ error: 'Failed to load area outage events' });
  }
});

// Outage summary by year, area, and type (planned/unplanned)
app.get('/api/outages/summary', async (req, res) => {
  try {
    const { year, areas, messageType, topN = 10 } = req.query;
    
    const data = await loadData();
    let filtered = [...data];

    // Only include actual outages (message types 1, 2, 3)
    // Exclude: 4 = Market notice, 5 = Other
    filtered = filtered.filter(row => {
      const msgType = parseInt(row.message_type);
      return msgType === 1 || msgType === 2 || msgType === 3;
    });

    // Filter by year if specified
    if (year && year !== 'all') {
      filtered = filtered.filter(row => {
        const eventYear = new Date(row.publication_date).getFullYear();
        return eventYear === parseInt(year);
      });
    }

    // Filter by message type if specified
    if (messageType) {
      filtered = filtered.filter(row => row.message_type === parseInt(messageType));
    }

    // Filter by areas if specified
    if (areas) {
      const areaList = areas.split(',');
      filtered = filtered.filter(row => {
        const rowAreas = extractAreaNames(row);
        return rowAreas.some(area => areaList.includes(area));
      });
    }

    // Calculate summary by area, year, message type, and planned status
    const summary = {};
    
    filtered.forEach(row => {
      const rowAreas = extractAreaNames(row);
      const eventYear = new Date(row.publication_date).getFullYear();
      const messageType = row.message_type;
      const unavailabilityType = row.unavailability_type ? parseFloat(row.unavailability_type) : null;
      
      // Determine planned/unplanned status
      let plannedStatus = 'Unknown';
      if (unavailabilityType === 1) {
        plannedStatus = 'Planned';
      } else if (unavailabilityType === 2) {
        plannedStatus = 'Unplanned';
      } else {
        // Fallback: check remarks for keywords
        const remarks = (row.remarks || '').toLowerCase();
        const plannedKeywords = ['planned', 'maintenance', 'scheduled'];
        const unplannedKeywords = ['unplanned', 'unexpected', 'fault', 'failure', 'emergency'];
        
        if (plannedKeywords.some(word => remarks.includes(word))) {
          plannedStatus = 'Planned';
        } else if (unplannedKeywords.some(word => remarks.includes(word))) {
          plannedStatus = 'Unplanned';
        }
        // else remains 'Unknown'
      }

      rowAreas.forEach(area => {
        const key = `${area}|${eventYear}|${messageType}|${plannedStatus}`;
        if (!summary[key]) {
          summary[key] = {
            area,
            year: eventYear,
            messageType,
            plannedStatus,
            count: 0
          };
        }
        summary[key].count += 1;
      });
    });

    const summaryArray = Object.values(summary);

    // Get top N areas by total outage count
    const areaTotals = {};
    summaryArray.forEach(item => {
      if (!areaTotals[item.area]) {
        areaTotals[item.area] = 0;
      }
      areaTotals[item.area] += item.count;
    });

    const topAreas = Object.entries(areaTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, parseInt(topN))
      .map(([area]) => area);

    // Get unique years and areas for filters
    const uniqueYears = [...new Set(filtered.map(row => new Date(row.publication_date).getFullYear()))].sort();
    const uniqueAreas = [...new Set(filtered.flatMap(row => extractAreaNames(row)))].sort();

    // Message type labels
    const messageTypeLabels = {
      1: 'Production unavailability',
      2: 'Consumption unavailability',
      3: 'Transmission outage',
      4: 'Market notice',
      5: 'Other'
    };

    res.json({
      summary: summaryArray,
      topAreas,
      uniqueYears,
      uniqueAreas,
      messageTypeLabels,
      totalRecords: filtered.length
    });
  } catch (error) {
    console.error('Error loading outage summary:', error);
    res.status(500).json({ error: 'Failed to load outage summary' });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  const healthCheck = {
    status: 'OK',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    port: PORT,
    csvPath: CSV_PATH,
    csvExists: fs.existsSync(CSV_PATH),
    buildPath: path.join(__dirname, '../frontend/build'),
    buildExists: fs.existsSync(path.join(__dirname, '../frontend/build')),
    indexHtmlExists: fs.existsSync(path.join(__dirname, '../frontend/build', 'index.html'))
  };
  
  console.log('Health check:', JSON.stringify(healthCheck, null, 2));
  res.json(healthCheck);
});

// Serve React app for all other routes (must be after API routes)
if (process.env.NODE_ENV === 'production') {
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/build', 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`🚀 Nord Pool UMM Backend running on http://localhost:${PORT}`);
  console.log(`📊 Loading data from: ${CSV_PATH}`);
  if (process.env.NODE_ENV === 'production') {
    console.log(`🌐 Serving React app from: ${path.join(__dirname, '../frontend/build')}`);
  }
});
