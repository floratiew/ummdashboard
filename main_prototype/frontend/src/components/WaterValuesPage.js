import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
} from '@mui/material';
import {
  TrendingUp,
  ElectricBolt,
  Speed,
  AttachMoney,
} from '@mui/icons-material';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import axios from 'axios';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const StatCard = ({ title, value, unit, icon, color }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography color="text.secondary" gutterBottom variant="body2">
            {title}
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700, color }}>
            {value}
          </Typography>
          {unit && (
            <Typography variant="body2" color="text.secondary">
              {unit}
            </Typography>
          )}
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

function WaterValuesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [plants, setPlants] = useState([]);
  const [summary, setSummary] = useState({});
  const [prices, setPrices] = useState({});

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [plantsRes, summaryRes, pricesRes] = await Promise.all([
        axios.get('/api/watervalues/plants'),
        axios.get('/api/watervalues/summary'),
        axios.get('/api/watervalues/prices'),
      ]);

      setPlants(plantsRes.data.plants || []);
      setSummary(summaryRes.data.summary || {});
      setPrices(pricesRes.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load water values data');
    } finally {
      setLoading(false);
    }
  };

  const getAggregateStats = () => {
    const summaryValues = Object.values(summary);
    const totalProduction = summaryValues.reduce((sum, plant) => sum + (plant.currentProduction || 0), 0);
    const totalCapacity = summaryValues.reduce((sum, plant) => sum + (plant.maxInstalled || 0), 0);
    const avgWaterValue = summaryValues.length > 0
      ? summaryValues.reduce((sum, plant) => sum + (plant.waterValue || 0), 0) / summaryValues.length
      : 0;
    const avgEfficiency = summaryValues.length > 0
      ? summaryValues.reduce((sum, plant) => sum + (plant.efficiency || 0), 0) / summaryValues.length
      : 0;

    return {
      totalProduction: totalProduction.toFixed(1),
      totalCapacity: totalCapacity.toFixed(0),
      avgWaterValue: avgWaterValue.toFixed(1),
      avgEfficiency: avgEfficiency.toFixed(1),
    };
  };

  const getPriceChartData = (area) => {
    const areaData = prices[area];
    if (!areaData) return null;

    return {
      labels: areaData.dayAhead?.map(d => d.hour) || [],
      datasets: [
        {
          label: 'Day-Ahead Price',
          data: areaData.dayAhead?.map(d => d.price) || [],
          borderColor: '#667eea',
          backgroundColor: 'rgba(102, 126, 234, 0.1)',
          tension: 0.4,
        },
      ],
    };
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  const stats = getAggregateStats();

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Water Values & Production Overview
      </Typography>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Production"
            value={stats.totalProduction}
            unit="MW"
            icon={<ElectricBolt sx={{ fontSize: 32, color: '#667eea' }} />}
            color="#667eea"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Capacity"
            value={stats.totalCapacity}
            unit="MW"
            icon={<Speed sx={{ fontSize: 32, color: '#764ba2' }} />}
            color="#764ba2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Water Value"
            value={stats.avgWaterValue}
            unit="EUR/MWh"
            icon={<AttachMoney sx={{ fontSize: 32, color: '#48bb78' }} />}
            color="#48bb78"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Efficiency"
            value={stats.avgEfficiency}
            unit="%"
            icon={<TrendingUp sx={{ fontSize: 32, color: '#f6ad55' }} />}
            color="#f6ad55"
          />
        </Grid>
      </Grid>

      {/* Plants Table */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Power Plants
          </Typography>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Plant Name</TableCell>
                  <TableCell>Area</TableCell>
                  <TableCell align="right">Current Production (MW)</TableCell>
                  <TableCell align="right">Max Capacity (MW)</TableCell>
                  <TableCell align="right">Water Value (EUR/MWh)</TableCell>
                  <TableCell align="right">Production Interval</TableCell>
                  <TableCell align="right">Day-Ahead Price</TableCell>
                  <TableCell align="right">Intra-Day Price</TableCell>
                  <TableCell align="right">Efficiency (%)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.values(summary).map((plant) => (
                  <TableRow key={plant.plantId}>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {plant.plantName}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={plant.priceArea} size="small" color="primary" />
                    </TableCell>
                    <TableCell align="right">{plant.currentProduction?.toFixed(1)}</TableCell>
                    <TableCell align="right">{plant.maxInstalled}</TableCell>
                    <TableCell align="right">{plant.waterValue?.toFixed(2)}</TableCell>
                    <TableCell align="right">
                      {plant.productionInterval ? 
                        `${plant.productionInterval[0]} - ${plant.productionInterval[1]} MW` : 
                        'N/A'}
                    </TableCell>
                    <TableCell align="right">{plant.dayAheadPrice?.toFixed(2)}</TableCell>
                    <TableCell align="right">{plant.intraDayPrice?.toFixed(2)}</TableCell>
                    <TableCell align="right">{plant.efficiency?.toFixed(1)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Price Charts */}
      <Grid container spacing={3}>
        {['NO5', 'NO2'].map((area) => {
          const chartData = getPriceChartData(area);
          if (!chartData) return null;

          return (
            <Grid item xs={12} md={6} key={area}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {area} Day-Ahead Prices
                  </Typography>
                  <Box sx={{ height: 300 }}>
                    <Line
                      data={chartData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            display: true,
                            position: 'top',
                          },
                        },
                        scales: {
                          y: {
                            beginAtZero: false,
                            title: {
                              display: true,
                              text: 'EUR/MWh',
                            },
                          },
                        },
                      }}
                    />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

export default WaterValuesPage;
