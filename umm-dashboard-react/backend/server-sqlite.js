const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');

const app = express();
const PORT = process.env.PORT || 5001;

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files from React build (for production)
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../frontend/build')));
}

// Path to SQLite database
const DB_PATH = path.join(__dirname, '../../data/umm_messages.db');

// Initialize database connection
let db;
try {
  db = new Database(DB_PATH);
  db.pragma('journal_mode = WAL'); // Enable Write-Ahead Logging for better concurrency
  console.log(`Connected to database: ${DB_PATH}`);
} catch (error) {
  console.error(`Failed to connect to database: ${error.message}`);
  process.exit(1);
}

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

// Helper function to format duration
const formatDuration = (hours) => {
  if (!hours) return null;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
};

// Helper function to process row for API response
const processRow = (row) => {
  return {
    ...row,
    area_names: row.area_names ? row.area_names.split(',') : [],
    production_unit_names: row.production_unit_names ? row.production_unit_names.split(',') : [],
    generation_unit_names: row.generation_unit_names ? row.generation_unit_names.split(',') : [],
    installedMW: row.installed_mw,
    unavailableMW: row.unavailable_mw,
    availableMW: row.available_mw,
    fuelType: row.fuel_type,
    duration: formatDuration(row.duration_hours)
  };
};

// API Routes

// Get all messages with filters
app.get('/api/messages', async (req, res) => {
  try {
    const {
      startDate,
      endDate,
      messageType,
      area,
      publisher,
      search,
      limit = 10000, // Reasonable limit for pagination (10k messages per page)
      offset = 0
    } = req.query;
    
    let query = 'SELECT * FROM messages WHERE 1=1';
    const params = [];
    
    // Apply filters
    if (startDate) {
      query += ' AND publication_date >= ?';
      params.push(startDate);
    }
    if (endDate) {
      query += ' AND publication_date <= ?';
      params.push(endDate);
    }
    if (messageType) {
      query += ' AND message_type = ?';
      params.push(parseInt(messageType));
    }
    if (area) {
      query += ' AND area_names LIKE ?';
      params.push(`%${area}%`);
    }
    if (publisher) {
      query += ' AND publisher_name = ?';
      params.push(publisher);
    }
    if (search) {
      query += ' AND remarks LIKE ?';
      params.push(`%${search}%`);
    }
    
    // Count total
    const countQuery = query.replace('SELECT *', 'SELECT COUNT(*) as total');
    const countResult = db.prepare(countQuery).get(...params);
    const total = countResult.total;
    
    // Sort and paginate
    query += ' ORDER BY publication_date DESC LIMIT ? OFFSET ?';
    params.push(parseInt(limit), parseInt(offset));
    
    const rows = db.prepare(query).all(...params);
    const data = rows.map(processRow);
    
    res.json({
      data,
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
    const totalMessages = db.prepare('SELECT COUNT(*) as count FROM messages').get().count;
    const publishers = db.prepare('SELECT COUNT(DISTINCT publisher_name) as count FROM messages WHERE publisher_name IS NOT NULL').get().count;
    
    // Count distinct areas (need to split comma-separated values)
    const areaRows = db.prepare("SELECT DISTINCT area_names FROM messages WHERE area_names IS NOT NULL AND area_names != ''").all();
    const uniqueAreas = new Set();
    areaRows.forEach(row => {
      if (row.area_names) {
        row.area_names.split(',').forEach(area => uniqueAreas.add(area));
      }
    });
    
    // Count distinct production units
    const unitRows = db.prepare("SELECT DISTINCT production_unit_names FROM messages WHERE production_unit_names IS NOT NULL AND production_unit_names != ''").all();
    const uniqueUnits = new Set();
    unitRows.forEach(row => {
      if (row.production_unit_names) {
        row.production_unit_names.split(',').forEach(unit => uniqueUnits.add(unit));
      }
    });
    
    // Message type breakdown
    const messageTypeRows = db.prepare('SELECT message_type, COUNT(*) as count FROM messages GROUP BY message_type').all();
    const messageTypes = {};
    messageTypeRows.forEach(row => {
      messageTypes[row.message_type] = row.count;
    });
    
    res.json({
      totalMessages,
      publishers,
      areas: uniqueAreas.size,
      productionUnits: uniqueUnits.size,
      messageTypes
    });
  } catch (error) {
    console.error('Error loading stats:', error);
    res.status(500).json({ error: 'Failed to load statistics' });
  }
});

// Get unique values for filters
app.get('/api/filters', async (req, res) => {
  try {
    // Get unique publishers
    const publishers = db.prepare('SELECT DISTINCT publisher_name FROM messages WHERE publisher_name IS NOT NULL ORDER BY publisher_name').all()
      .map(row => row.publisher_name);
    
    // Get unique message types
    const messageTypes = db.prepare('SELECT DISTINCT message_type FROM messages WHERE message_type IS NOT NULL ORDER BY message_type').all()
      .map(row => row.message_type);
    
    // Get unique areas
    const areaRows = db.prepare("SELECT DISTINCT area_names FROM messages WHERE area_names IS NOT NULL AND area_names != ''").all();
    const areasSet = new Set();
    areaRows.forEach(row => {
      if (row.area_names) {
        row.area_names.split(',').forEach(area => areasSet.add(area));
      }
    });
    
    // Get unique units
    const unitRows = db.prepare('SELECT DISTINCT production_unit_names, generation_unit_names FROM messages').all();
    const unitsSet = new Set();
    unitRows.forEach(row => {
      if (row.production_unit_names) {
        row.production_unit_names.split(',').forEach(unit => unitsSet.add(unit));
      }
      if (row.generation_unit_names) {
        row.generation_unit_names.split(',').forEach(unit => unitsSet.add(unit));
      }
    });
    
    res.json({
      areas: Array.from(areasSet).sort(),
      publishers,
      messageTypes,
      units: Array.from(unitsSet).sort()
    });
  } catch (error) {
    console.error('Error loading filters:', error);
    res.status(500).json({ error: 'Failed to load filters' });
  }
});

// Get production unit analysis
app.get('/api/units/:unitName', async (req, res) => {
  try {
    const { unitName } = req.params;
    const { year, messageType, plannedStatus } = req.query;
    
    let query = 'SELECT * FROM messages WHERE (production_unit_names LIKE ? OR generation_unit_names LIKE ?)';
    const params = [`%${unitName}%`, `%${unitName}%`];
    
    const allUnitData = db.prepare(query).all(...params);
    
    if (allUnitData.length === 0) {
      return res.status(404).json({ error: 'Unit not found' });
    }
    
    // Calculate message type breakdown
    const messageTypeBreakdown = {};
    const messageTypeLabels = {
      '1': 'Production unavailability',
      '2': 'Consumption unavailability',
      '3': 'Transmission outage',
      '4': 'Market notice',
      '5': 'Other'
    };
    allUnitData.forEach(row => {
      const type = row.message_type;
      const label = messageTypeLabels[type] || 'Other';
      messageTypeBreakdown[label] = (messageTypeBreakdown[label] || 0) + 1;
    });
    
    // Extract unit info
    const unitInfo = { areas: new Set(), capacity: null, owner: null, publishers: new Set() };
    for (const row of allUnitData.slice(0, 10)) {
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
    
    allUnitData.forEach(row => {
      if (row.publisher_name) {
        unitInfo.publishers.add(row.publisher_name);
        if (!unitInfo.owner) unitInfo.owner = row.publisher_name;
      }
    });
    
    // Calculate area breakdown
    const areaEventCounts = {};
    allUnitData.forEach(row => {
      if (row.area_names) {
        row.area_names.split(',').forEach(area => {
          areaEventCounts[area] = (areaEventCounts[area] || 0) + 1;
        });
      }
    });
    const areaBreakdown = Object.keys(areaEventCounts).sort().map(area => ({
      area,
      count: areaEventCounts[area]
    }));
    
    // Calculate yearly breakdown
    const yearlyBreakdown = {};
    allUnitData.forEach(row => {
      const eventYear = new Date(row.publication_date).getFullYear();
      const msgType = row.message_type;
      
      if (!yearlyBreakdown[eventYear]) {
        yearlyBreakdown[eventYear] = {};
      }
      yearlyBreakdown[eventYear][msgType] = (yearlyBreakdown[eventYear][msgType] || 0) + 1;
    });
    
    const yearlyData = Object.keys(yearlyBreakdown).sort().map(yr => ({
      year: parseInt(yr),
      counts: yearlyBreakdown[yr],
      total: Object.values(yearlyBreakdown[yr]).reduce((a, b) => a + b, 0)
    }));
    
    // Calculate planned/unplanned
    const plannedKeywords = ['planned', 'maintenance', 'scheduled'];
    const unplannedKeywords = ['unplanned', 'unexpected', 'fault', 'failure', 'emergency'];
    
    const plannedUnplannedBreakdown = {
      'Planned': 0,
      'Unplanned': 0,
      'Unknown': 0
    };
    
    allUnitData.forEach(row => {
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
    
    // Apply filters for events list
    let filteredEvents = allUnitData;
    if (year) {
      filteredEvents = filteredEvents.filter(row => {
        const eventYear = new Date(row.publication_date).getFullYear();
        return eventYear === parseInt(year);
      });
    }
    if (messageType) {
      filteredEvents = filteredEvents.filter(row => row.message_type === parseInt(messageType));
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
    
    const eventsWithId = filteredEvents.slice(0, 100).map(row => processRow(row));
    
    res.json({
      unitName,
      areas: Array.from(unitInfo.areas),
      capacity: unitInfo.capacity,
      owner: unitInfo.owner,
      totalEvents: allUnitData.length,
      filteredEvents: filteredEvents.length,
      affectedAreas: areaBreakdown.length,
      uniquePublishers: unitInfo.publishers.size,
      publishers: Array.from(unitInfo.publishers),
      messageTypeBreakdown,
      plannedUnplannedBreakdown,
      yearlyData,
      areaBreakdown,
      availableYears: Object.keys(yearlyBreakdown).sort(),
      events: eventsWithId
    });
  } catch (error) {
    console.error('Error loading unit data:', error);
    res.status(500).json({ error: 'Failed to load unit data' });
  }
});

// Get yearly data for charts
app.get('/api/charts/yearly', async (req, res) => {
  try {
    const { area, messageType } = req.query;
    
    let query = "SELECT strftime('%Y', publication_date) as year, COUNT(*) as count FROM messages WHERE 1=1";
    const params = [];
    
    if (area) {
      query += ' AND area_names LIKE ?';
      params.push(`%${area}%`);
    }
    if (messageType) {
      query += ' AND message_type = ?';
      params.push(parseInt(messageType));
    }
    
    query += ' GROUP BY year ORDER BY year';
    
    const rows = db.prepare(query).all(...params);
    const chartData = rows.map(row => ({
      year: parseInt(row.year),
      count: row.count
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
    const { mwThreshold = 400, status = 'Both', areas } = req.query;
    
    // Query messages with outage types and capacity info
    let query = `
      SELECT 
        area_names,
        unavailable_mw,
        unavailability_type,
        publication_date,
        remarks,
        message_type
      FROM messages 
      WHERE message_type IN (1, 2, 3)
        AND unavailable_mw >= ?
    `;
    const params = [parseFloat(mwThreshold)];
    
    // Filter by status (planned/unplanned) if specified
    if (status !== 'Both') {
      if (status === 'Planned') {
        query += ' AND unavailability_type = ?';
        params.push('1');
      } else if (status === 'Unplanned') {
        query += ' AND unavailability_type = ?';
        params.push('2');
      }
    }
    
    // Filter by areas if specified
    if (areas) {
      const areaList = areas.split(',');
      const areaConditions = areaList.map(() => 'area_names LIKE ?').join(' OR ');
      query += ` AND (${areaConditions})`;
      areaList.forEach(area => params.push(`%${area}%`));
    }
    
    query += ' ORDER BY publication_date DESC';
    
    const rows = db.prepare(query).all(...params);
    
    // Process results - split area_names and create individual events
    // Note: MW value is per MESSAGE, not per area. When splitting by area,
    // we divide the MW by number of areas to avoid inflating the totals.
    const events = [];
    rows.forEach(row => {
      const areaList = row.area_names ? row.area_names.split(',').map(a => a.trim()).filter(a => a) : [];
      const numAreas = areaList.length || 1;
      const mwPerArea = (row.unavailable_mw || 0) / numAreas; // Distribute MW across areas
      
      areaList.forEach(area => {
        // Determine status
        let eventStatus = 'Unknown';
        if (row.unavailability_type === '1') eventStatus = 'Planned';
        else if (row.unavailability_type === '2') eventStatus = 'Unplanned';
        
        events.push({
          area: area.trim(),
          mw: mwPerArea, // Use distributed MW value
          status: eventStatus,
          publicationDate: row.publication_date,
          remarks: row.remarks,
          totalMessageMW: row.unavailable_mw || 0, // Keep original for reference
          affectedAreas: numAreas
        });
      });
    });
    
    // Calculate summary by area
    const areaStats = {};
    events.forEach(event => {
      if (!areaStats[event.area]) {
        areaStats[event.area] = { area: event.area, totalMW: 0, count: 0 };
      }
      areaStats[event.area].totalMW += event.mw; // Now uses distributed MW
      areaStats[event.area].count += 1;
    });
    
    const summary = Object.values(areaStats).sort((a, b) => b.totalMW - a.totalMW);
    
    // Get unique areas for filter
    const uniqueAreas = [...new Set(events.map(e => e.area))].sort();
    
    res.json({
      events,
      summary,
      uniqueAreas,
      totalEvents: events.length
    });
  } catch (error) {
    console.error('Error loading area outage events:', error);
    res.status(500).json({ error: 'Failed to load area outage events' });
  }
});

// Outage summary
app.get('/api/outages/summary', async (req, res) => {
  try {
    const { year, areas, messageType, plannedStatus, topN = 10 } = req.query;
    
    let query = 'SELECT * FROM messages WHERE message_type IN (1, 2, 3)';
    const params = [];
    
    if (year && year !== 'all') {
      query += " AND strftime('%Y', publication_date) = ?";
      params.push(year);
    }
    if (messageType) {
      query += ' AND message_type = ?';
      params.push(parseInt(messageType));
    }
    if (areas) {
      const areaList = areas.split(',');
      const areaConditions = areaList.map(() => 'area_names LIKE ?').join(' OR ');
      query += ` AND (${areaConditions})`;
      areaList.forEach(area => params.push(`%${area}%`));
    }
    
    const rows = db.prepare(query).all(...params);
    
    // Process summary...
    const summary = {};
    const plannedKeywords = ['planned', 'maintenance', 'scheduled'];
    const unplannedKeywords = ['unplanned', 'unexpected', 'fault', 'failure', 'emergency'];
    
    rows.forEach(row => {
      const rowAreas = row.area_names ? row.area_names.split(',') : [];
      const eventYear = new Date(row.publication_date).getFullYear();
      const msgType = row.message_type;
      const unavailabilityType = row.unavailability_type ? parseFloat(row.unavailability_type) : null;
      
      let status = 'Unknown';
      if (unavailabilityType === 1) {
        status = 'Planned';
      } else if (unavailabilityType === 2) {
        status = 'Unplanned';
      } else {
        const remarks = (row.remarks || '').toLowerCase();
        if (plannedKeywords.some(word => remarks.includes(word))) {
          status = 'Planned';
        } else if (unplannedKeywords.some(word => remarks.includes(word))) {
          status = 'Unplanned';
        }
      }
      
      rowAreas.forEach(area => {
        const key = `${area}|${eventYear}|${msgType}|${status}`;
        if (!summary[key]) {
          summary[key] = {
            area,
            year: eventYear,
            messageType: msgType,
            plannedStatus: status,
            count: 0
          };
        }
        summary[key].count += 1;
      });
    });
    
    let summaryArray = Object.values(summary);
    
    if (plannedStatus) {
      summaryArray = summaryArray.filter(item => item.plannedStatus === plannedStatus);
    }
    
    // Get top areas
    const areaTotals = {};
    summaryArray.forEach(item => {
      areaTotals[item.area] = (areaTotals[item.area] || 0) + item.count;
    });
    
    const topAreas = Object.entries(areaTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, parseInt(topN))
      .map(([area]) => area);
    
    // Get unique years and areas
    const uniqueYears = [...new Set(rows.map(row => new Date(row.publication_date).getFullYear()))].sort();
    const uniqueAreasSet = new Set();
    rows.forEach(row => {
      if (row.area_names) {
        row.area_names.split(',').forEach(area => uniqueAreasSet.add(area));
      }
    });
    
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
      uniqueAreas: Array.from(uniqueAreasSet).sort(),
      messageTypeLabels,
      totalRecords: rows.length
    });
  } catch (error) {
    console.error('Error loading outage summary:', error);
    res.status(500).json({ error: 'Failed to load outage summary' });
  }
});

// Get message details
app.get('/api/messages/:messageId', async (req, res) => {
  try {
    const { messageId } = req.params;
    
    const message = db.prepare('SELECT * FROM messages WHERE message_id = ?').get(messageId);
    
    if (!message) {
      return res.status(404).json({ error: 'Message not found' });
    }
    
    const relatedMessages = parseJSON(message.related_messages_json || '[]');
    
    const formattedRelatedMessages = relatedMessages.map(relMsg => ({
      message_id: message.message_id,
      version: relMsg.version,
      message_type: relMsg.messageType,
      event_status: relMsg.eventStatus,
      is_outdated: relMsg.isOutdated,
      publication_date: relMsg.publicationDate,
      event_start: relMsg.eventStart,
      event_stop: relMsg.eventStop,
      publisher_name: relMsg.publisherName,
      unavailability_type: relMsg.unavailabilityType,
      unavailability_reason: relMsg.unavailabilityReason,
      remarks: relMsg.remarks,
      area_names: (relMsg.productionUnits || []).map(u => u.areaName).filter(Boolean),
      production_unit_names: (relMsg.productionUnits || []).map(u => u.name).filter(Boolean),
      generation_unit_names: (relMsg.generationUnits || []).map(u => u.name).filter(Boolean),
    }));
    
    res.json({
      message: processRow(message),
      relatedMessages: formattedRelatedMessages,
      relatedCount: formattedRelatedMessages.length
    });
  } catch (error) {
    console.error('Error fetching message details:', error);
    res.status(500).json({ error: 'Failed to fetch message details' });
  }
});

// Health check
app.get('/health', (req, res) => {
  const healthCheck = {
    status: 'OK',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    port: PORT,
    dbPath: DB_PATH,
    dbExists: fs.existsSync(DB_PATH),
    dbSize: fs.existsSync(DB_PATH) ? `${(fs.statSync(DB_PATH).size / (1024*1024)).toFixed(1)} MB` : 'N/A',
    messageCount: db.prepare('SELECT COUNT(*) as count FROM messages').get().count
  };
  
  res.json(healthCheck);
});

// Serve React app
if (process.env.NODE_ENV === 'production') {
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/build', 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`🚀 Nord Pool UMM Backend running on http://localhost:${PORT}`);
  console.log(`📊 Connected to database: ${DB_PATH}`);
  const count = db.prepare('SELECT COUNT(*) as count FROM messages').get().count;
  console.log(`✅ Database contains ${count.toLocaleString()} messages`);
  if (process.env.NODE_ENV === 'production') {
    console.log(`🌐 Serving React app from: ${path.join(__dirname, '../frontend/build')}`);
  }
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n👋 Closing database connection...');
  db.close();
  process.exit(0);
});
