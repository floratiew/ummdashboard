import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Autocomplete,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { Bar } from 'react-chartjs-2';
import axios from 'axios';

function ProductionUnitsView() {
  const [units, setUnits] = useState([]);
  const [selectedUnit, setSelectedUnit] = useState(null);
  const [unitData, setUnitData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedYear, setSelectedYear] = useState('');
  const [selectedMessageType, setSelectedMessageType] = useState('');
  const [selectedPlannedStatus, setSelectedPlannedStatus] = useState('');

  useEffect(() => {
    fetchUnits();
  }, []);

  useEffect(() => {
    if (selectedUnit) {
      fetchUnitData(selectedUnit, selectedYear, selectedMessageType, selectedPlannedStatus);
    }
  }, [selectedYear, selectedMessageType, selectedPlannedStatus]);

  const fetchUnits = async () => {
    try {
      const res = await axios.get('/api/filters');
      setUnits(res.data.units || []);
    } catch (err) {
      console.error('Error fetching units:', err);
      setError('Failed to load units');
    }
  };

  const fetchUnitData = async (unitName, year = '', messageType = '', plannedStatus = '') => {
    if (!unitName) return;
    
    try {
      setLoading(true);
      const params = {};
      if (year) params.year = year;
      if (messageType) params.messageType = messageType;
      if (plannedStatus) params.plannedStatus = plannedStatus;
      const res = await axios.get(`/api/units/${encodeURIComponent(unitName)}`, { params });
      setUnitData(res.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching unit data:', err);
      setError('Failed to load unit data');
    } finally {
      setLoading(false);
    }
  };

  const handleUnitChange = (event, value) => {
    setSelectedUnit(value);
    setSelectedYear(''); // Reset year filter
    setSelectedMessageType(''); // Reset message type filter
    setSelectedPlannedStatus(''); // Reset planned status filter
    if (value) {
      fetchUnitData(value);
    } else {
      setUnitData(null);
    }
  };

  const messageTypeOptions = {
    '1': 'Production unavailability',
    '2': 'Consumption unavailability',
    '3': 'Transmission outage',
    '4': 'Market notice',
    '5': 'Other'
  };

  const columns = [
    {
      field: 'publication_date',
      headerName: 'Publication Date',
      width: 180,
      valueFormatter: (params) => new Date(params.value).toLocaleString(),
    },
    {
      field: 'message_type',
      headerName: 'Type',
      width: 180,
    },
    {
      field: 'area_names',
      headerName: 'Areas',
      width: 150,
      valueFormatter: (params) => params.value?.join(', ') || 'N/A',
    },
    {
      field: 'event_start',
      headerName: 'Event Start',
      width: 180,
      valueFormatter: (params) => params.value ? new Date(params.value).toLocaleString() : 'N/A',
    },
    {
      field: 'event_stop',
      headerName: 'Event Stop',
      width: 180,
      valueFormatter: (params) => params.value ? new Date(params.value).toLocaleString() : 'N/A',
    },
    {
      field: 'duration',
      headerName: 'Duration',
      width: 100,
    },
    {
      field: 'remarks',
      headerName: 'Remarks',
      width: 300,
      flex: 1,
    },
  ];

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
          Production Unit Analysis
        </Typography>
        <Typography color="text.secondary">
          Analyze market events by production and generation units
        </Typography>
      </Box>

      <Card sx={{ mb: 3, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Search Production Units
        </Typography>
        <Autocomplete
          value={selectedUnit}
          onChange={handleUnitChange}
          options={units}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Select or search for a unit (e.g., Kvilldal)"
              placeholder="Start typing..."
            />
          )}
          fullWidth
        />
      </Card>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {unitData && !loading && (
        <>
          {/* Filters - Moved to Top */}
          <Card sx={{ mb: 4, p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              🔍 Filter Events
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Message Type</InputLabel>
                  <Select
                    value={selectedMessageType}
                    label="Message Type"
                    onChange={(e) => setSelectedMessageType(e.target.value)}
                  >
                    <MenuItem value="">All Types</MenuItem>
                    {Object.entries(messageTypeOptions).map(([key, label]) => {
                      const count = unitData.messageTypeBreakdown?.[label] || 0;
                      return (
                        <MenuItem key={key} value={key}>
                          {label} ({count} events)
                        </MenuItem>
                      );
                    })}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Year</InputLabel>
                  <Select
                    value={selectedYear}
                    label="Year"
                    onChange={(e) => setSelectedYear(e.target.value)}
                  >
                    <MenuItem value="">All Years</MenuItem>
                    {unitData.availableYears?.map((year) => (
                      <MenuItem key={year} value={year}>
                        {year} ({unitData.yearlyData?.find(y => y.year === parseInt(year))?.total || 0} events)
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Planned Status</InputLabel>
                  <Select
                    value={selectedPlannedStatus}
                    label="Planned Status"
                    onChange={(e) => setSelectedPlannedStatus(e.target.value)}
                  >
                    <MenuItem value="">All Status</MenuItem>
                    {unitData.plannedUnplannedBreakdown && Object.entries(unitData.plannedUnplannedBreakdown).map(([status, count]) => (
                      <MenuItem key={status} value={status}>
                        {status} ({count} events)
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            {(selectedMessageType || selectedYear || selectedPlannedStatus) && (
              <Box sx={{ mt: 2 }}>
                <Chip 
                  label={`Showing ${unitData.filteredEvents?.toLocaleString() || 0} of ${unitData.totalEvents?.toLocaleString() || 0} events`}
                  color="primary"
                  sx={{ mr: 1 }}
                />
                {selectedMessageType && (
                  <Chip 
                    label={messageTypeOptions[selectedMessageType]}
                    onDelete={() => setSelectedMessageType('')}
                    sx={{ mr: 1 }}
                  />
                )}
                {selectedYear && (
                  <Chip 
                    label={`Year: ${selectedYear}`}
                    onDelete={() => setSelectedYear('')}
                    sx={{ mr: 1 }}
                  />
                )}
                {selectedPlannedStatus && (
                  <Chip 
                    label={`Status: ${selectedPlannedStatus}`}
                    onDelete={() => setSelectedPlannedStatus('')}
                    sx={{ mr: 1 }}
                  />
                )}
              </Box>
            )}
          </Card>

          {/* Unit Overview */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Location
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {unitData.areas?.join(', ') || 'Unknown'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Installed Capacity
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600, color: '#667eea' }}>
                    {unitData.capacity ? `${unitData.capacity.toLocaleString()} MW` : 'N/A'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Primary Owner
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {unitData.owner || 'Unknown'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Total Events
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600, color: '#764ba2' }}>
                    {unitData.totalEvents?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* All Stats in One Row */}
          <Grid container spacing={2} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Affected Price Areas
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#f093fb' }}>
                    {unitData.affectedAreas?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Unique Publishers
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#4facfe' }}>
                    {unitData.uniquePublishers?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Production Unavailable
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#ff6b6b' }}>
                    {unitData.messageTypeBreakdown?.['Production unavailability']?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Transmission Outage
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#ffd93d' }}>
                    {unitData.messageTypeBreakdown?.['Transmission outage']?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Consumption Unavailable
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#6bcf7f' }}>
                    {unitData.messageTypeBreakdown?.['Consumption unavailability']?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Yearly Chart - Now respects message type filter */}
          <Card sx={{ mb: 4, p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              📅 Unavailability Events Over Time
              {selectedMessageType && (
                <Chip 
                  label={messageTypeOptions[selectedMessageType]}
                  size="small"
                  sx={{ ml: 2 }}
                  color="primary"
                />
              )}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
              {selectedMessageType 
                ? `Showing ${messageTypeOptions[selectedMessageType]} events over time`
                : 'Showing all message types over time'}
            </Typography>
            <Bar 
              data={{
                labels: unitData.yearlyData?.map(d => d.year) || [],
                datasets: [
                  {
                    label: 'Number of Events',
                    data: unitData.yearlyData?.map(d => d.total) || [],
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 2,
                  },
                ],
              }}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    position: 'top',
                    labels: { color: '#fff' },
                  },
                  title: {
                    display: true,
                    text: `Events for ${unitData.unitName} by year`,
                    color: '#fff',
                    font: { size: 14 },
                  },
                },
                scales: {
                  y: {
                    ticks: { color: '#fff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                  },
                  x: {
                    ticks: { color: '#fff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                  },
                },
              }}
            />
          </Card>

          {/* Area Breakdown Chart - Only show if multiple areas affected */}
          {unitData.affectedAreas > 1 && unitData.areaBreakdown && (
            <Card sx={{ mb: 4, p: 3 }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                📍 Events by Price Area
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                This unit affects multiple price areas. Distribution of events across areas:
              </Typography>
              <Bar 
                data={{
                  labels: unitData.areaBreakdown?.map(d => d.area) || [],
                  datasets: [
                    {
                      label: 'Events per Area',
                      data: unitData.areaBreakdown?.map(d => d.count) || [],
                      backgroundColor: [
                        'rgba(240, 147, 251, 0.8)',
                        'rgba(79, 172, 254, 0.8)',
                        'rgba(0, 210, 255, 0.8)',
                        'rgba(118, 75, 162, 0.8)',
                      ],
                      borderColor: [
                        'rgba(240, 147, 251, 1)',
                        'rgba(79, 172, 254, 1)',
                        'rgba(0, 210, 255, 1)',
                        'rgba(118, 75, 162, 1)',
                      ],
                      borderWidth: 2,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  plugins: {
                    legend: {
                      display: false,
                    },
                    title: {
                      display: true,
                      text: `Impact distribution across ${unitData.affectedAreas} price areas`,
                      color: '#fff',
                      font: { size: 14 },
                    },
                  },
                  scales: {
                    y: {
                      ticks: { color: '#fff' },
                      grid: { color: 'rgba(255, 255, 255, 0.1)' },
                      beginAtZero: true,
                    },
                    x: {
                      ticks: { color: '#fff' },
                      grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    },
                  },
                }}
              />
            </Card>
          )}

          {/* Filters */}
          <Card sx={{ mb: 3, p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Filter Events
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth size="small">
                  <InputLabel>Message Type</InputLabel>
                  <Select
                    value={selectedMessageType}
                    label="Message Type"
                    onChange={(e) => setSelectedMessageType(e.target.value)}
                  >
                    <MenuItem value="">All Types</MenuItem>
                    {Object.entries(messageTypeOptions).map(([key, label]) => {
                      const count = unitData.messageTypeBreakdown?.[label] || 0;
                      return (
                        <MenuItem key={key} value={key}>
                          {label} ({count} events)
                        </MenuItem>
                      );
                    })}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth size="small">
                  <InputLabel>Year</InputLabel>
                  <Select
                    value={selectedYear}
                    label="Year"
                    onChange={(e) => setSelectedYear(e.target.value)}
                  >
                    <MenuItem value="">All Years</MenuItem>
                    {unitData.availableYears?.map((year) => (
                      <MenuItem key={year} value={year}>
                        {year} ({unitData.yearlyData?.find(y => y.year === parseInt(year))?.total || 0} events)
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            {(selectedMessageType || selectedYear) && (
              <Box sx={{ mt: 2 }}>
                <Chip 
                  label={`Showing ${unitData.filteredEvents?.toLocaleString() || 0} of ${unitData.totalEvents?.toLocaleString() || 0} events`}
                  color="primary"
                  sx={{ mr: 1 }}
                />
                {selectedMessageType && (
                  <Chip 
                    label={messageTypeOptions[selectedMessageType]}
                    onDelete={() => setSelectedMessageType('')}
                    sx={{ mr: 1 }}
                  />
                )}
                {selectedYear && (
                  <Chip 
                    label={`Year: ${selectedYear}`}
                    onDelete={() => setSelectedYear('')}
                  />
                )}
              </Box>
            )}
          </Card>

          {/* Events Table */}
          <Card sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Market Messages for {unitData.unitName}
            </Typography>
            <Box sx={{ height: 600, width: '100%' }}>
              <DataGrid
                rows={unitData.events?.map((row, idx) => ({ id: idx, ...row })) || []}
                columns={columns}
                pageSize={10}
                rowsPerPageOptions={[10, 25, 50]}
                disableSelectionOnClick
                sx={{
                  '& .MuiDataGrid-cell': {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                  },
                  '& .MuiDataGrid-columnHeaders': {
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                  },
                }}
              />
            </Box>
          </Card>
        </>
      )}

      {!selectedUnit && !loading && (
        <Paper sx={{ p: 4, textAlign: 'center', backgroundColor: 'rgba(102, 126, 234, 0.05)' }}>
          <Typography variant="h6" color="text.secondary">
            💡 Search or select a production/generation unit above to view its market events and details
          </Typography>
        </Paper>
      )}
    </Box>
  );
}

export default ProductionUnitsView;
