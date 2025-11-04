import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Slider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Autocomplete,
  TextField,
  Tabs,
  Tab
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import axios from 'axios';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function OutagesView() {
  const [tab, setTab] = useState(0);
  
  // Area Events Tab State
  const [mwThreshold, setMwThreshold] = useState(400);
  const [status, setStatus] = useState('Both');
  const [selectedAreas, setSelectedAreas] = useState([]);
  const [eventData, setEventData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Summary Analysis Tab State
  const [summaryYear, setSummaryYear] = useState('');
  const [summaryMessageType, setSummaryMessageType] = useState('');
  const [summaryAreas, setSummaryAreas] = useState([]);
  const [topN, setTopN] = useState(10);
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    if (tab === 0) {
      fetchAreaEvents();
    } else {
      fetchSummaryAnalysis();
    }
  }, [tab, mwThreshold, status, selectedAreas, summaryYear, summaryMessageType, summaryAreas, topN]);

  const fetchAreaEvents = async () => {
    setLoading(true);
    try {
      const params = {
        mwThreshold,
        status
      };
      
      if (selectedAreas.length > 0) {
        params.areas = selectedAreas.join(',');
      }

      const response = await axios.get('/api/outages/area-events', { params });
      setEventData(response.data);
    } catch (error) {
      console.error('Error fetching area events:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummaryAnalysis = async () => {
    setSummaryLoading(true);
    try {
      const params = { topN };
      if (summaryYear) params.year = summaryYear;
      if (summaryMessageType) params.messageType = summaryMessageType;
      if (summaryAreas.length > 0) params.areas = summaryAreas.join(',');

      const response = await axios.get('/api/outages/summary', { params });
      setSummaryData(response.data);
    } catch (error) {
      console.error('Error fetching summary:', error);
    } finally {
      setSummaryLoading(false);
    }
  };

  const messageTypeLabels = {
    '1': 'Production unavailability',
    '2': 'Consumption unavailability',
    '3': 'Transmission outage'
  };

  // Area Events Tab Columns
  const eventColumns = [
    { field: 'area', headerName: 'Area', width: 100 },
    { 
      field: 'mw', 
      headerName: 'MW', 
      width: 120,
      valueFormatter: (params) => `${params.value?.toFixed(1)} MW`
    },
    { field: 'status', headerName: 'Status', width: 120 },
    { 
      field: 'publicationDate', 
      headerName: 'Publication Date', 
      width: 200,
      valueFormatter: (params) => new Date(params.value).toLocaleString()
    },
    { field: 'remarks', headerName: 'Remarks', flex: 1, minWidth: 300 }
  ];

  const eventRows = eventData?.events?.map((event, idx) => ({
    id: idx,
    ...event
  })) || [];

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
          ⚡ Outage Analysis
        </Typography>
        <Typography color="text.secondary">
          Comprehensive outage analysis with MW threshold filtering and planned/unplanned breakdown
        </Typography>
      </Box>

      {/* Tabs */}
      <Card sx={{ mb: 4 }}>
        <Tabs value={tab} onChange={(e, newValue) => setTab(newValue)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Outage Events" />
          <Tab label="Summary Analysis" />
        </Tabs>
      </Card>

      {/* Tab 0: Area Outage Events */}
      {tab === 0 && (
        <>
          {/* Filters */}
          <Card sx={{ mb: 4, p: 3 }}>
            <Typography variant="h6" sx={{ mb: 3, fontWeight: 600 }}>
              🔍 Filters
            </Typography>
            
            <Grid container spacing={3}>
              {/* MW Threshold Slider */}
              <Grid item xs={12} md={4}>
                <Typography gutterBottom>
                  MW Threshold: {mwThreshold} MW
                </Typography>
                <Slider
                  value={mwThreshold}
                  onChange={(e, newValue) => setMwThreshold(newValue)}
                  min={100}
                  max={2000}
                  step={50}
                  marks={[
                    { value: 100, label: '100' },
                    { value: 400, label: '400' },
                    { value: 1000, label: '1000' },
                    { value: 2000, label: '2000' }
                  ]}
                  valueLabelDisplay="auto"
                />
              </Grid>

              {/* Status Filter */}
              <Grid item xs={12} md={4}>
                <FormControl fullWidth size="small">
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={status}
                    label="Status"
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <MenuItem value="Both">All Status</MenuItem>
                    <MenuItem value="Planned">Planned</MenuItem>
                    <MenuItem value="Unplanned">Unplanned</MenuItem>
                    <MenuItem value="Unknown">Unknown</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              {/* Area Filter */}
              <Grid item xs={12} md={4}>
                <Autocomplete
                  multiple
                  size="small"
                  options={eventData?.availableAreas || []}
                  value={selectedAreas}
                  onChange={(e, newValue) => setSelectedAreas(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} label="Filter by Areas" placeholder="Select areas" />
                  )}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip label={option} size="small" {...getTagProps({ index })} />
                    ))
                  }
                />
              </Grid>
            </Grid>
          </Card>

          {/* Stats Cards */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Total Events
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#667eea' }}>
                    {eventData?.events?.length?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Areas Affected
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#764ba2' }}>
                    {eventData?.summary?.length?.toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" gutterBottom variant="body2">
                    Total MW Impact
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#f093fb' }}>
                    {eventData?.summary?.reduce((sum, area) => sum + area.totalMW, 0)?.toFixed(0).toLocaleString() || '0'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Chart */}
          {eventData?.summary && eventData.summary.length > 0 && (
            <Card sx={{ mb: 4, p: 3 }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                📊 Total MW by Area (Top 15)
              </Typography>
              <Bar
                data={{
                  labels: eventData.summary.slice(0, 15).map(s => s.area),
                  datasets: [
                    {
                      label: 'Total MW',
                      data: eventData.summary.slice(0, 15).map(s => s.totalMW),
                      backgroundColor: 'rgba(102, 126, 234, 0.8)',
                      borderColor: 'rgba(102, 126, 234, 1)',
                      borderWidth: 2,
                    }
                  ]
                }}
                options={{
                  responsive: true,
                  plugins: {
                    legend: { display: false },
                    title: {
                      display: true,
                      text: `Top 15 Areas by Total MW Impact (≥${mwThreshold} MW, ${status})`,
                      color: '#fff',
                      font: { size: 14 }
                    }
                  },
                  scales: {
                    y: {
                      ticks: { color: '#fff' },
                      grid: { color: 'rgba(255, 255, 255, 0.1)' },
                      title: { display: true, text: 'Total MW', color: '#fff' }
                    },
                    x: {
                      ticks: { color: '#fff' },
                      grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    }
                  }
                }}
              />
            </Card>
          )}

          {/* Data Table */}
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                📋 Outage Events (≥{mwThreshold} MW)
              </Typography>
              <Box sx={{ height: 600, width: '100%' }}>
                <DataGrid
                  rows={eventRows}
                  columns={eventColumns}
                  pageSize={10}
                  rowsPerPageOptions={[10, 25, 50, 100]}
                  disableSelectionOnClick
                  loading={loading}
                  sx={{
                    '& .MuiDataGrid-cell': { color: '#fff' },
                    '& .MuiDataGrid-columnHeaders': {
                      backgroundColor: 'rgba(102, 126, 234, 0.1)',
                      color: '#fff',
                      fontWeight: 600
                    }
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      {/* Tab 1: Summary Analysis */}
      {tab === 1 && (
        <>
          {/* Summary Filters */}
          <Card sx={{ mb: 4, p: 3 }}>
            <Typography variant="h6" sx={{ mb: 3, fontWeight: 600 }}>
              🔍 Analysis Filters
            </Typography>
            
            <Grid container spacing={3}>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Year</InputLabel>
                  <Select
                    value={summaryYear}
                    label="Year"
                    onChange={(e) => setSummaryYear(e.target.value)}
                  >
                    <MenuItem value="">All Years</MenuItem>
                    {summaryData?.uniqueYears?.map(year => (
                      <MenuItem key={year} value={year}>{year}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Message Type</InputLabel>
                  <Select
                    value={summaryMessageType}
                    label="Message Type"
                    onChange={(e) => setSummaryMessageType(e.target.value)}
                  >
                    <MenuItem value="">All Types</MenuItem>
                    {Object.entries(messageTypeLabels).map(([key, label]) => (
                      <MenuItem key={key} value={key}>{label}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={3}>
                <Autocomplete
                  multiple
                  size="small"
                  options={summaryData?.uniqueAreas || []}
                  value={summaryAreas}
                  onChange={(e, newValue) => setSummaryAreas(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} label="Areas" placeholder="Select areas" />
                  )}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip label={option} size="small" {...getTagProps({ index })} />
                    ))
                  }
                />
              </Grid>

              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Top N Areas</InputLabel>
                  <Select
                    value={topN}
                    label="Top N Areas"
                    onChange={(e) => setTopN(e.target.value)}
                  >
                    <MenuItem value={5}>Top 5</MenuItem>
                    <MenuItem value={10}>Top 10</MenuItem>
                    <MenuItem value={15}>Top 15</MenuItem>
                    <MenuItem value={20}>Top 20</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Card>

          {/* Full Analysis - All Areas */}
          {summaryData && (() => {
            // Calculate stats for ALL areas (not filtered by topN)
            const allAreasAggregates = {};
            summaryData.summary.forEach(row => {
              if (!allAreasAggregates[row.area]) {
                allAreasAggregates[row.area] = { planned: 0, unplanned: 0, unknown: 0, total: 0 };
              }
              if (row.plannedStatus === 'Planned') allAreasAggregates[row.area].planned += row.count;
              else if (row.plannedStatus === 'Unplanned') allAreasAggregates[row.area].unplanned += row.count;
              else allAreasAggregates[row.area].unknown += row.count;
              allAreasAggregates[row.area].total += row.count;
            });
            
            const allTotalPlanned = Object.values(allAreasAggregates).reduce((sum, a) => sum + a.planned, 0);
            const allTotalUnplanned = Object.values(allAreasAggregates).reduce((sum, a) => sum + a.unplanned, 0);
            const allTotalUnknown = Object.values(allAreasAggregates).reduce((sum, a) => sum + a.unknown, 0);
            const allGrandTotal = allTotalPlanned + allTotalUnplanned + allTotalUnknown;
            const totalAreas = Object.keys(allAreasAggregates).length;

            return (
              <>
                {/* Full Dataset Overview */}
                <Card sx={{ mb: 4, p: 3, background: 'linear-gradient(145deg, #2a1a4a 0%, #1a1232 100%)', border: '2px solid rgba(102, 126, 234, 0.3)' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                    <Box>
                      <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5, color: '#fff' }}>
                        🌐 Full Analysis - All Areas
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Complete overview of all {totalAreas} areas before filtering
                      </Typography>
                    </Box>
                    <Chip 
                      label="UNFILTERED DATA" 
                      size="small" 
                      sx={{ 
                        bgcolor: 'rgba(255, 152, 0, 0.2)', 
                        color: '#ff9800',
                        fontWeight: 700,
                        fontSize: '11px'
                      }} 
                    />
                  </Box>

                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card sx={{ 
                        background: 'linear-gradient(135deg, rgba(76, 175, 80, 0.25) 0%, rgba(76, 175, 80, 0.08) 100%)',
                        border: '2px solid rgba(76, 175, 80, 0.4)'
                      }}>
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#4caf50' }} />
                            Planned Outages
                          </Typography>
                          <Typography variant="h3" sx={{ fontWeight: 700, color: '#4caf50', mb: 1 }}>
                            {allTotalPlanned.toLocaleString()}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {((allTotalPlanned / allGrandTotal) * 100).toFixed(1)}% of all outages
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card sx={{ 
                        background: 'linear-gradient(135deg, rgba(244, 67, 54, 0.25) 0%, rgba(244, 67, 54, 0.08) 100%)',
                        border: '2px solid rgba(244, 67, 54, 0.4)'
                      }}>
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#f44336' }} />
                            Unplanned Outages
                          </Typography>
                          <Typography variant="h3" sx={{ fontWeight: 700, color: '#f44336', mb: 1 }}>
                            {allTotalUnplanned.toLocaleString()}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {((allTotalUnplanned / allGrandTotal) * 100).toFixed(1)}% of all outages
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card sx={{ 
                        background: 'linear-gradient(135deg, rgba(158, 158, 158, 0.25) 0%, rgba(158, 158, 158, 0.08) 100%)',
                        border: '2px solid rgba(158, 158, 158, 0.4)'
                      }}>
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#9e9e9e' }} />
                            Unknown Status
                          </Typography>
                          <Typography variant="h3" sx={{ fontWeight: 700, color: '#9e9e9e', mb: 1 }}>
                            {allTotalUnknown.toLocaleString()}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {((allTotalUnknown / allGrandTotal) * 100).toFixed(1)}% of all outages
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card sx={{ 
                        background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.25) 0%, rgba(102, 126, 234, 0.08) 100%)',
                        border: '2px solid rgba(102, 126, 234, 0.4)'
                      }}>
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#667eea' }} />
                            Total Outages
                          </Typography>
                          <Typography variant="h3" sx={{ fontWeight: 700, color: '#667eea', mb: 1 }}>
                            {allGrandTotal.toLocaleString()}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Across all {totalAreas} areas
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  </Grid>

                  {/* Full Area Rankings Table */}
                  <Box sx={{ mt: 4 }}>
                    <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                      📊 Complete Area Rankings
                    </Typography>
                    <Box sx={{ maxHeight: 400, overflowY: 'auto', overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 2px' }}>
                        <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                          <tr style={{ 
                            backgroundColor: 'rgba(102, 126, 234, 0.2)',
                          }}>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'left',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#667eea',
                              backgroundColor: '#1a1232'
                            }}>
                              #
                            </th>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'left',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#667eea',
                              backgroundColor: '#1a1232'
                            }}>
                              AREA
                            </th>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'right',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#4caf50',
                              backgroundColor: '#1a1232'
                            }}>
                              PLANNED
                            </th>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'right',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#f44336',
                              backgroundColor: '#1a1232'
                            }}>
                              UNPLANNED
                            </th>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'right',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#9e9e9e',
                              backgroundColor: '#1a1232'
                            }}>
                              UNKNOWN
                            </th>
                            <th style={{ 
                              padding: '12px 16px', 
                              textAlign: 'right',
                              fontWeight: 600,
                              fontSize: '12px',
                              color: '#667eea',
                              backgroundColor: '#1a1232'
                            }}>
                              TOTAL
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(allAreasAggregates)
                            .sort((a, b) => b[1].total - a[1].total)
                            .map(([area, data], idx) => (
                              <tr key={idx} style={{ 
                                backgroundColor: idx < topN ? 'rgba(255, 152, 0, 0.08)' : (idx % 2 === 0 ? 'rgba(102, 126, 234, 0.03)' : 'transparent'),
                                borderLeft: idx < topN ? '3px solid #ff9800' : 'none'
                              }}>
                                <td style={{ 
                                  padding: '10px 16px',
                                  fontSize: '13px',
                                  color: idx < topN ? '#ff9800' : 'rgba(255,255,255,0.5)',
                                  fontWeight: idx < topN ? 700 : 400
                                }}>
                                  {idx + 1}
                                </td>
                                <td style={{ 
                                  padding: '10px 16px',
                                  fontWeight: 600,
                                  fontSize: '13px',
                                  color: '#fff'
                                }}>
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Box sx={{ 
                                      width: 6, 
                                      height: 6, 
                                      borderRadius: '50%', 
                                      bgcolor: idx < topN ? '#ff9800' : '#667eea'
                                    }} />
                                    {area}
                                    {idx < topN && (
                                      <Chip 
                                        label="TOP" 
                                        size="small" 
                                        sx={{ 
                                          height: 18,
                                          fontSize: '9px',
                                          bgcolor: 'rgba(255, 152, 0, 0.2)', 
                                          color: '#ff9800',
                                          fontWeight: 700,
                                          ml: 1
                                        }} 
                                      />
                                    )}
                                  </Box>
                                </td>
                                <td style={{ 
                                  padding: '10px 16px', 
                                  textAlign: 'right',
                                  fontSize: '13px',
                                  color: '#4caf50',
                                  fontWeight: 500
                                }}>
                                  {data.planned.toLocaleString()}
                                </td>
                                <td style={{ 
                                  padding: '10px 16px', 
                                  textAlign: 'right',
                                  fontSize: '13px',
                                  color: '#f44336',
                                  fontWeight: 500
                                }}>
                                  {data.unplanned.toLocaleString()}
                                </td>
                                <td style={{ 
                                  padding: '10px 16px', 
                                  textAlign: 'right',
                                  fontSize: '13px',
                                  color: '#9e9e9e',
                                  fontWeight: 500
                                }}>
                                  {data.unknown.toLocaleString()}
                                </td>
                                <td style={{ 
                                  padding: '10px 16px', 
                                  textAlign: 'right',
                                  fontWeight: 700,
                                  fontSize: '14px',
                                  color: idx < topN ? '#ff9800' : '#667eea'
                                }}>
                                  {data.total.toLocaleString()}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </Box>
                  </Box>
                </Card>

                {/* Divider */}
                <Box sx={{ my: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box sx={{ flex: 1, height: '2px', background: 'linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.5), transparent)' }} />
                  <Typography variant="h6" sx={{ color: '#667eea', fontWeight: 700 }}>
                    📍 TOP {topN} DETAILED ANALYSIS
                  </Typography>
                  <Box sx={{ flex: 1, height: '2px', background: 'linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.5), transparent)' }} />
                </Box>
              </>
            );
          })()}

          {/* Top N Stats Cards */}
          {summaryData && (() => {
            const areaAggregates = {};
            summaryData.summary
              .filter(row => summaryData.topAreas.includes(row.area))
              .forEach(row => {
                if (!areaAggregates[row.area]) {
                  areaAggregates[row.area] = { planned: 0, unplanned: 0, unknown: 0, total: 0 };
                }
                if (row.plannedStatus === 'Planned') areaAggregates[row.area].planned += row.count;
                else if (row.plannedStatus === 'Unplanned') areaAggregates[row.area].unplanned += row.count;
                else areaAggregates[row.area].unknown += row.count;
                areaAggregates[row.area].total += row.count;
              });
            
            const totalPlanned = Object.values(areaAggregates).reduce((sum, a) => sum + a.planned, 0);
            const totalUnplanned = Object.values(areaAggregates).reduce((sum, a) => sum + a.unplanned, 0);
            const totalUnknown = Object.values(areaAggregates).reduce((sum, a) => sum + a.unknown, 0);
            const grandTotal = totalPlanned + totalUnplanned + totalUnknown;

            return (
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <Card sx={{ 
                    background: 'linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(76, 175, 80, 0.05) 100%)',
                    border: '1px solid rgba(76, 175, 80, 0.3)'
                  }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#4caf50' }} />
                        Planned Outages
                      </Typography>
                      <Typography variant="h3" sx={{ fontWeight: 700, color: '#4caf50', mb: 1 }}>
                        {totalPlanned.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {((totalPlanned / grandTotal) * 100).toFixed(1)}% of total
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card sx={{ 
                    background: 'linear-gradient(135deg, rgba(244, 67, 54, 0.2) 0%, rgba(244, 67, 54, 0.05) 100%)',
                    border: '1px solid rgba(244, 67, 54, 0.3)'
                  }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#f44336' }} />
                        Unplanned Outages
                      </Typography>
                      <Typography variant="h3" sx={{ fontWeight: 700, color: '#f44336', mb: 1 }}>
                        {totalUnplanned.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {((totalUnplanned / grandTotal) * 100).toFixed(1)}% of total
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card sx={{ 
                    background: 'linear-gradient(135deg, rgba(158, 158, 158, 0.2) 0%, rgba(158, 158, 158, 0.05) 100%)',
                    border: '1px solid rgba(158, 158, 158, 0.3)'
                  }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#9e9e9e' }} />
                        Unknown Status
                      </Typography>
                      <Typography variant="h3" sx={{ fontWeight: 700, color: '#9e9e9e', mb: 1 }}>
                        {totalUnknown.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {((totalUnknown / grandTotal) * 100).toFixed(1)}% of total
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card sx={{ 
                    background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(102, 126, 234, 0.05) 100%)',
                    border: '1px solid rgba(102, 126, 234, 0.3)'
                  }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#667eea' }} />
                        Total Outages
                      </Typography>
                      <Typography variant="h3" sx={{ fontWeight: 700, color: '#667eea', mb: 1 }}>
                        {grandTotal.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Across {Object.keys(areaAggregates).length} areas
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            );
          })()}

          {/* Summary Chart */}
          {summaryData?.summary && summaryData.summary.length > 0 && (() => {
            // Aggregate data by area for chart
            const areaAggregates = {};
            summaryData.summary
              .filter(row => summaryData.topAreas.includes(row.area))
              .forEach(row => {
                if (!areaAggregates[row.area]) {
                  areaAggregates[row.area] = { planned: 0, unplanned: 0, unknown: 0, total: 0 };
                }
                if (row.plannedStatus === 'Planned') areaAggregates[row.area].planned += row.count;
                else if (row.plannedStatus === 'Unplanned') areaAggregates[row.area].unplanned += row.count;
                else areaAggregates[row.area].unknown += row.count;
                areaAggregates[row.area].total += row.count;
              });
            
            const sortedAreas = Object.entries(areaAggregates)
              .sort((a, b) => b[1].total - a[1].total)
              .slice(0, topN);

            return (
              <Card sx={{ mb: 4, p: 3, background: 'linear-gradient(145deg, #1a1f3a 0%, #151932 100%)' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
                      📊 Outage Status Distribution
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Stacked breakdown showing planned, unplanned, and unknown outages
                    </Typography>
                  </Box>
                  <Chip 
                    label={`Top ${topN} Areas`} 
                    size="small" 
                    sx={{ 
                      bgcolor: 'rgba(102, 126, 234, 0.2)', 
                      color: '#667eea',
                      fontWeight: 600
                    }} 
                  />
                </Box>
                <Box sx={{ height: 400 }}>
                  <Bar
                    data={{
                      labels: sortedAreas.map(([area]) => area),
                      datasets: [
                        {
                          label: 'Planned',
                          data: sortedAreas.map(([, data]) => data.planned),
                          backgroundColor: 'rgba(76, 175, 80, 0.8)',
                          borderColor: 'rgba(76, 175, 80, 1)',
                          borderWidth: 2,
                          borderRadius: 4,
                        },
                        {
                          label: 'Unplanned',
                          data: sortedAreas.map(([, data]) => data.unplanned),
                          backgroundColor: 'rgba(244, 67, 54, 0.8)',
                          borderColor: 'rgba(244, 67, 54, 1)',
                          borderWidth: 2,
                          borderRadius: 4,
                        },
                        {
                          label: 'Unknown',
                          data: sortedAreas.map(([, data]) => data.unknown),
                          backgroundColor: 'rgba(158, 158, 158, 0.8)',
                          borderColor: 'rgba(158, 158, 158, 1)',
                          borderWidth: 2,
                          borderRadius: 4,
                        }
                      ]
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: {
                          position: 'top',
                          labels: { 
                            color: '#fff',
                            font: { size: 12, weight: '600' },
                            padding: 15,
                            usePointStyle: true,
                            pointStyle: 'circle'
                          }
                        },
                        tooltip: {
                          backgroundColor: 'rgba(0, 0, 0, 0.8)',
                          padding: 12,
                          titleFont: { size: 13, weight: 'bold' },
                          bodyFont: { size: 12 },
                          borderColor: 'rgba(102, 126, 234, 0.5)',
                          borderWidth: 1
                        }
                      },
                      scales: {
                        x: {
                          stacked: true,
                          ticks: { color: '#fff', font: { size: 11 } },
                          grid: { display: false }
                        },
                        y: {
                          stacked: true,
                          ticks: { color: '#fff', font: { size: 11 } },
                          grid: { color: 'rgba(255, 255, 255, 0.1)' },
                          title: { display: true, text: 'Number of Events', color: '#fff', font: { size: 12, weight: '600' } }
                        }
                      }
                    }}
                  />
                </Box>
              </Card>
            );
          })()}

          {/* Summary Stats Table */}
          <Card sx={{ p: 3, background: 'linear-gradient(145deg, #1a1f3a 0%, #151932 100%)' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
                  📈 Area-by-Area Breakdown
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Detailed outage statistics for top {topN} affected areas
                </Typography>
              </Box>
            </Box>
            {summaryData?.summary && (() => {
              // Aggregate data by area
              const areaAggregates = {};
              summaryData.summary
                .filter(row => summaryData.topAreas.includes(row.area))
                .forEach(row => {
                  if (!areaAggregates[row.area]) {
                    areaAggregates[row.area] = { planned: 0, unplanned: 0, unknown: 0, total: 0 };
                  }
                  if (row.plannedStatus === 'Planned') areaAggregates[row.area].planned += row.count;
                  else if (row.plannedStatus === 'Unplanned') areaAggregates[row.area].unplanned += row.count;
                  else areaAggregates[row.area].unknown += row.count;
                  areaAggregates[row.area].total += row.count;
                });

              const sortedAreas = Object.entries(areaAggregates)
                .sort((a, b) => b[1].total - a[1].total)
                .slice(0, topN);

              return (
                <Box sx={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 4px' }}>
                    <thead>
                      <tr style={{ 
                        backgroundColor: 'rgba(102, 126, 234, 0.15)',
                        borderRadius: '8px'
                      }}>
                        <th style={{ 
                          padding: '14px 16px', 
                          textAlign: 'left',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: '#667eea',
                          borderTopLeftRadius: '8px',
                          borderBottomLeftRadius: '8px'
                        }}>
                          AREA
                        </th>
                        <th style={{ 
                          padding: '14px 16px', 
                          textAlign: 'right',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: '#4caf50'
                        }}>
                          PLANNED
                        </th>
                        <th style={{ 
                          padding: '14px 16px', 
                          textAlign: 'right',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: '#f44336'
                        }}>
                          UNPLANNED
                        </th>
                        <th style={{ 
                          padding: '14px 16px', 
                          textAlign: 'right',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: '#9e9e9e'
                        }}>
                          UNKNOWN
                        </th>
                        <th style={{ 
                          padding: '14px 16px', 
                          textAlign: 'right',
                          fontWeight: 600,
                          fontSize: '13px',
                          color: '#667eea',
                          borderTopRightRadius: '8px',
                          borderBottomRightRadius: '8px'
                        }}>
                          TOTAL
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedAreas.map(([area, data], idx) => (
                        <tr key={idx} style={{ 
                          backgroundColor: idx % 2 === 0 ? 'rgba(102, 126, 234, 0.03)' : 'transparent',
                          transition: 'background-color 0.2s'
                        }}>
                          <td style={{ 
                            padding: '14px 16px',
                            fontWeight: 600,
                            fontSize: '14px',
                            color: '#fff',
                            borderTopLeftRadius: '8px',
                            borderBottomLeftRadius: '8px'
                          }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Box sx={{ 
                                width: 6, 
                                height: 6, 
                                borderRadius: '50%', 
                                bgcolor: '#667eea' 
                              }} />
                              {area}
                            </Box>
                          </td>
                          <td style={{ 
                            padding: '14px 16px', 
                            textAlign: 'right',
                            fontSize: '14px',
                            color: '#4caf50',
                            fontWeight: 500
                          }}>
                            {data.planned.toLocaleString()}
                          </td>
                          <td style={{ 
                            padding: '14px 16px', 
                            textAlign: 'right',
                            fontSize: '14px',
                            color: '#f44336',
                            fontWeight: 500
                          }}>
                            {data.unplanned.toLocaleString()}
                          </td>
                          <td style={{ 
                            padding: '14px 16px', 
                            textAlign: 'right',
                            fontSize: '14px',
                            color: '#9e9e9e',
                            fontWeight: 500
                          }}>
                            {data.unknown.toLocaleString()}
                          </td>
                          <td style={{ 
                            padding: '14px 16px', 
                            textAlign: 'right',
                            fontWeight: 700,
                            fontSize: '15px',
                            color: '#667eea',
                            borderTopRightRadius: '8px',
                            borderBottomRightRadius: '8px'
                          }}>
                            {data.total.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Box>
              );
            })()}
          </Card>

          {/* Comprehensive Summary Table */}
          <Card sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              � Comprehensive Outage Breakdown
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              Detailed breakdown by Year, Area, Message Type, and Planned/Unplanned Status
            </Typography>
            {summaryData?.summary && summaryData.topAreas && (
              <Box sx={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.2)', backgroundColor: 'rgba(102, 126, 234, 0.1)' }}>
                      <th style={{ padding: '12px', textAlign: 'left', position: 'sticky', left: 0, backgroundColor: '#151932', zIndex: 1 }}>Area</th>
                      <th style={{ padding: '12px', textAlign: 'center' }}>Year</th>
                      <th style={{ padding: '12px', textAlign: 'left' }}>Message Type</th>
                      <th style={{ padding: '12px', textAlign: 'center' }}>Status</th>
                      <th style={{ padding: '12px', textAlign: 'right' }}>Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summaryData.summary
                      .filter(row => summaryData.topAreas.includes(row.area))
                      .sort((a, b) => {
                        // Sort by area, then year, then message type, then planned status
                        if (a.area !== b.area) return a.area.localeCompare(b.area);
                        if (a.year !== b.year) return b.year - a.year; // Newest first
                        if (a.messageType !== b.messageType) return a.messageType - b.messageType;
                        return a.plannedStatus.localeCompare(b.plannedStatus);
                      })
                      .map((row, idx, arr) => {
                        const prevRow = idx > 0 ? arr[idx - 1] : null;
                        const isNewArea = !prevRow || prevRow.area !== row.area;
                        const isNewYear = isNewArea || prevRow.year !== row.year;
                        
                        return (
                          <tr 
                            key={idx} 
                            style={{ 
                              borderBottom: '1px solid rgba(255,255,255,0.05)',
                              backgroundColor: isNewArea ? 'rgba(102, 126, 234, 0.03)' : 'transparent'
                            }}
                          >
                            <td style={{ 
                              padding: '10px 12px', 
                              fontWeight: isNewArea ? 'bold' : 'normal',
                              position: 'sticky',
                              left: 0,
                              backgroundColor: isNewArea ? 'rgba(102, 126, 234, 0.15)' : '#151932',
                              borderRight: '1px solid rgba(255,255,255,0.1)'
                            }}>
                              {isNewArea ? row.area : ''}
                            </td>
                            <td style={{ 
                              padding: '10px 12px', 
                              textAlign: 'center',
                              fontWeight: isNewYear ? '600' : 'normal',
                              color: isNewYear ? '#fff' : 'rgba(255,255,255,0.7)'
                            }}>
                              {isNewYear ? row.year : ''}
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '13px' }}>
                              {messageTypeLabels[row.messageType]}
                            </td>
                            <td style={{ 
                              padding: '10px 12px', 
                              textAlign: 'center'
                            }}>
                              <Chip
                                label={row.plannedStatus}
                                size="small"
                                sx={{
                                  backgroundColor: 
                                    row.plannedStatus === 'Planned' ? 'rgba(76, 175, 80, 0.2)' :
                                    row.plannedStatus === 'Unplanned' ? 'rgba(244, 67, 54, 0.2)' :
                                    'rgba(158, 158, 158, 0.2)',
                                  color:
                                    row.plannedStatus === 'Planned' ? '#4caf50' :
                                    row.plannedStatus === 'Unplanned' ? '#f44336' :
                                    '#9e9e9e',
                                  fontWeight: 600,
                                  fontSize: '11px'
                                }}
                              />
                            </td>
                            <td style={{ 
                              padding: '10px 12px', 
                              textAlign: 'right', 
                              fontWeight: 'bold',
                              color: '#fff'
                            }}>
                              {row.count}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </Box>
            )}
          </Card>
        </>
      )}
    </Box>
  );
}

export default OutagesView;
