import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Chip,
  Stack,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Message as MessageIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  ElectricBolt,
  TrendingUp,
  Refresh,
} from '@mui/icons-material';
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

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const StatCard = ({ title, value, icon, color }) => (
  <Card sx={{ height: '100%', position: 'relative', overflow: 'visible' }}>
    <CardContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography color="text.secondary" gutterBottom variant="body2">
            {title}
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700, color }}>
            {value}
          </Typography>
        </Box>
        <Box
          sx={{
            backgroundColor: `${color}20`,
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

function UMMPage() {
  const [messages, setMessages] = useState([]);
  const [totalMessages, setTotalMessages] = useState(0);
  const [stats, setStats] = useState(null);
  const [filters, setFilters] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [yearlyData, setYearlyData] = useState([]);
  
  // Filter state
  const [selectedArea, setSelectedArea] = useState('');
  const [selectedPublisher, setSelectedPublisher] = useState('');
  const [selectedMessageType, setSelectedMessageType] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  useEffect(() => {
    fetchData();
  }, [paginationModel.page, paginationModel.pageSize]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const params = {
        limit: paginationModel.pageSize,
        offset: paginationModel.page * paginationModel.pageSize,
      };
      
      if (selectedArea) params.area = selectedArea;
      if (selectedPublisher) params.publisher = selectedPublisher;
      if (selectedMessageType) params.messageType = selectedMessageType;
      if (searchTerm) params.search = searchTerm;

      const [messagesRes, statsRes, filtersRes, yearlyRes] = await Promise.all([
        axios.get('/api/umm/messages', { params }),
        axios.get('/api/umm/stats'),
        axios.get('/api/umm/filters'),
        axios.get('/api/umm/yearly-stats'),
      ]);

      setMessages(messagesRes.data.messages || []);
      setTotalMessages(messagesRes.data.total || 0);
      setStats(statsRes.data);
      setFilters(filtersRes.data);
      setYearlyData(yearlyRes.data || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching UMM data:', err);
      setError('Failed to load UMM data');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilters = () => {
    setPaginationModel({ ...paginationModel, page: 0 });
    fetchData();
  };

  const handleResetFilters = () => {
    setSelectedArea('');
    setSelectedPublisher('');
    setSelectedMessageType('');
    setSearchTerm('');
    setPaginationModel({ ...paginationModel, page: 0 });
    setTimeout(() => fetchData(), 100);
  };

  const columns = [
    {
      field: 'publication_date',
      headerName: 'Publication Date',
      width: 180,
      valueFormatter: (params) => {
        if (!params.value) return '';
        return new Date(params.value).toLocaleString();
      },
    },
    {
      field: 'message_type_name',
      headerName: 'Type',
      width: 150,
      renderCell: (params) => (
        <Chip label={params.value} size="small" color="primary" />
      ),
    },
    {
      field: 'event_status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'Active' ? 'error' : 'success'}
        />
      ),
    },
    {
      field: 'publisher_name',
      headerName: 'Publisher',
      width: 200,
    },
    {
      field: 'area_names',
      headerName: 'Areas',
      width: 150,
      renderCell: (params) => (
        <Stack direction="row" spacing={0.5}>
          {(params.value || []).slice(0, 2).map((area, idx) => (
            <Chip key={idx} label={area} size="small" />
          ))}
          {params.value?.length > 2 && (
            <Chip label={`+${params.value.length - 2}`} size="small" />
          )}
        </Stack>
      ),
    },
    {
      field: 'unavailableMW',
      headerName: 'Unavailable (MW)',
      width: 150,
      type: 'number',
      valueFormatter: (params) => params.value ? params.value.toFixed(1) : 'N/A',
    },
    {
      field: 'message_text',
      headerName: 'Message',
      flex: 1,
      minWidth: 300,
    },
  ];

  const yearlyChartData = {
    labels: yearlyData.map(d => d.year),
    datasets: [
      {
        label: 'Total Messages',
        data: yearlyData.map(d => d.count),
        backgroundColor: 'rgba(102, 126, 234, 0.8)',
      },
      {
        label: 'Outages',
        data: yearlyData.map(d => d.outages),
        backgroundColor: 'rgba(244, 63, 94, 0.8)',
      },
    ],
  };

  if (loading && !stats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        UMM Messages & Outages
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      {stats && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Total Messages"
              value={stats.totalMessages?.toLocaleString() || '0'}
              icon={<MessageIcon sx={{ fontSize: 32, color: '#667eea' }} />}
              color="#667eea"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Active Outages"
              value={stats.activeOutages || '0'}
              icon={<TrendingUp sx={{ fontSize: 32, color: '#f43f5e' }} />}
              color="#f43f5e"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Total Capacity"
              value={`${(stats.totalCapacity || 0).toFixed(0)} MW`}
              icon={<ElectricBolt sx={{ fontSize: 32, color: '#764ba2' }} />}
              color="#764ba2"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Unavailable Capacity"
              value={`${(stats.unavailableCapacity || 0).toFixed(0)} MW`}
              icon={<BusinessIcon sx={{ fontSize: 32, color: '#f6ad55' }} />}
              color="#f6ad55"
            />
          </Grid>
        </Grid>
      )}

      {/* Yearly Chart */}
      {yearlyData.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Messages by Year
            </Typography>
            <Box sx={{ height: 300 }}>
              <Bar
                data={yearlyChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      display: true,
                      position: 'top',
                    },
                  },
                }}
              />
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      {filters && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Filters
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}>
                <TextField
                  fullWidth
                  label="Search"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  size="small"
                />
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Area</InputLabel>
                  <Select
                    value={selectedArea}
                    label="Area"
                    onChange={(e) => setSelectedArea(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    {filters.areas?.map((area) => (
                      <MenuItem key={area} value={area}>
                        {area}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Publisher</InputLabel>
                  <Select
                    value={selectedPublisher}
                    label="Publisher"
                    onChange={(e) => setSelectedPublisher(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    {filters.publishers?.map((publisher) => (
                      <MenuItem key={publisher} value={publisher}>
                        {publisher}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Message Type</InputLabel>
                  <Select
                    value={selectedMessageType}
                    label="Message Type"
                    onChange={(e) => setSelectedMessageType(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    {filters.messageTypes?.map((type) => (
                      <MenuItem key={type.id} value={type.id}>
                        {type.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={handleApplyFilters}
              >
                Apply Filters
              </Button>
              <Button variant="outlined" onClick={handleResetFilters}>
                Reset
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Messages Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Messages
          </Typography>
          <Box sx={{ height: 600, width: '100%' }}>
            <DataGrid
              rows={messages}
              columns={columns}
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
              pageSizeOptions={[10, 25, 50, 100]}
              rowCount={totalMessages}
              paginationMode="server"
              loading={loading}
              getRowId={(row) => row.message_id}
              disableRowSelectionOnClick
            />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

export default UMMPage;
