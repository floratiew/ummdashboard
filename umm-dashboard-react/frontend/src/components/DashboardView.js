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
  Paper,
  Chip,
  Stack,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  Message as MessageIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  ElectricBolt,
  TrendingUp,
  Refresh
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import axios from 'axios';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
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

function DashboardView() {
  const [messages, setMessages] = useState([]);
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

  const fetchData = async () => {
    try {
      setLoading(true);
      const [messagesRes, statsRes, filtersRes, yearlyRes] = await Promise.all([
        axios.get('/api/messages', {
          params: {
            area: selectedArea,
            publisher: selectedPublisher,
            messageType: selectedMessageType,
            search: searchTerm
          }
        }),
        axios.get('/api/stats'),
        axios.get('/api/filters'),
        axios.get('/api/charts/yearly')
      ]);

      setMessages(messagesRes.data.data || []);
      setStats(statsRes.data);
      setFilters(filtersRes.data);
      setYearlyData(yearlyRes.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load data. Make sure the backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedArea, selectedPublisher, selectedMessageType, searchTerm]);

  const messageTypeLabels = {
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
      valueFormatter: (params) => {
        return new Date(params.value).toLocaleString();
      },
    },
    {
      field: 'message_type',
      headerName: 'Type',
      width: 180,
      renderCell: (params) => (
        <Chip
          label={messageTypeLabels[params.value] || 'Unknown'}
          size="small"
          color={params.value === '1' ? 'warning' : params.value === '3' ? 'error' : 'default'}
        />
      ),
    },
    {
      field: 'area_names',
      headerName: 'Areas',
      width: 150,
      valueFormatter: (params) => params.value?.join(', ') || 'N/A',
    },
    {
      field: 'publisher_name',
      headerName: 'Publisher',
      width: 200,
    },
    {
      field: 'installedMW',
      headerName: 'Installed (MW)',
      width: 130,
      type: 'number',
      valueFormatter: (params) => params.value ? `${params.value.toFixed(0)} MW` : 'N/A',
    },
    {
      field: 'unavailableMW',
      headerName: 'Unavailable (MW)',
      width: 150,
      type: 'number',
      valueFormatter: (params) => params.value ? `${params.value.toFixed(0)} MW` : 'N/A',
    },
    {
      field: 'fuelType',
      headerName: 'Fuel Type',
      width: 150,
    },
    {
      field: 'duration',
      headerName: 'Duration',
      width: 100,
    },
    {
      field: 'remarks',
      headerName: 'Remarks',
      minWidth: 300,
      flex: 1,
      renderCell: (params) => (
        <Box
          sx={{
            whiteSpace: 'normal',
            wordWrap: 'break-word',
            lineHeight: '1.5',
            py: 1,
          }}
          title={params.value} // Tooltip on hover
        >
          {params.value}
        </Box>
      ),
    },
  ];

  const chartData = {
    labels: yearlyData.map(d => d.year),
    datasets: [
      {
        label: 'Messages per Year',
        data: yearlyData.map(d => d.count),
        backgroundColor: 'rgba(102, 126, 234, 0.8)',
        borderColor: 'rgba(102, 126, 234, 1)',
        borderWidth: 2,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#fff',
        },
      },
      title: {
        display: true,
        text: 'Market Messages Over Time',
        color: '#fff',
        font: {
          size: 16,
          weight: 'bold',
        },
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
  };

  if (loading && !stats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
          Dashboard Overview
        </Typography>
        <Typography color="text.secondary">
          Nord Pool UMM Market Messages Analysis
        </Typography>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Messages"
            value={stats?.totalMessages?.toLocaleString() || '0'}
            icon={<MessageIcon sx={{ color: '#667eea', fontSize: 32 }} />}
            color="#667eea"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Publishers"
            value={stats?.publishers?.toLocaleString() || '0'}
            icon={<BusinessIcon sx={{ color: '#764ba2', fontSize: 32 }} />}
            color="#764ba2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Price Areas"
            value={stats?.areas?.toLocaleString() || '0'}
            icon={<LocationIcon sx={{ color: '#f093fb', fontSize: 32 }} />}
            color="#f093fb"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Production Units"
            value={stats?.productionUnits?.toLocaleString() || '0'}
            icon={<ElectricBolt sx={{ color: '#4facfe', fontSize: 32 }} />}
            color="#4facfe"
          />
        </Grid>
      </Grid>

      {/* Chart */}
      <Card sx={{ mb: 4, p: 2 }}>
        <Bar data={chartData} options={chartOptions} />
      </Card>

      {/* Filters */}
      <Card sx={{ mb: 3, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Filters
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Area</InputLabel>
              <Select
                value={selectedArea}
                label="Area"
                onChange={(e) => setSelectedArea(e.target.value)}
              >
                <MenuItem value="">All Areas</MenuItem>
                {filters?.areas?.map((area) => (
                  <MenuItem key={area} value={area}>{area}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Message Type</InputLabel>
              <Select
                value={selectedMessageType}
                label="Message Type"
                onChange={(e) => setSelectedMessageType(e.target.value)}
              >
                <MenuItem value="">All Types</MenuItem>
                {Object.entries(messageTypeLabels).map(([key, label]) => (
                  <MenuItem key={key} value={key}>{label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Publisher</InputLabel>
              <Select
                value={selectedPublisher}
                label="Publisher"
                onChange={(e) => setSelectedPublisher(e.target.value)}
              >
                <MenuItem value="">All Publishers</MenuItem>
                {filters?.publishers?.slice(0, 50).map((pub) => (
                  <MenuItem key={pub} value={pub}>{pub}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search remarks..."
            />
          </Grid>
        </Grid>
        <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => {
              setSelectedArea('');
              setSelectedPublisher('');
              setSelectedMessageType('');
              setSearchTerm('');
            }}
          >
            Reset Filters
          </Button>
        </Box>
      </Card>

      {/* Data Table */}
      <Card sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          Market Messages ({messages.length})
        </Typography>
        <Box sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={messages.map((row, idx) => ({ id: idx, ...row }))}
            columns={columns}
            pageSize={10}
            rowsPerPageOptions={[10, 25, 50, 100]}
            disableSelectionOnClick
            getRowHeight={() => 'auto'}
            sx={{
              '& .MuiDataGrid-cell': {
                borderColor: 'rgba(255, 255, 255, 0.1)',
                display: 'flex',
                alignItems: 'center',
              },
              '& .MuiDataGrid-columnHeaders': {
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderColor: 'rgba(255, 255, 255, 0.1)',
              },
            }}
          />
        </Box>
      </Card>
    </Box>
  );
}

export default DashboardView;
