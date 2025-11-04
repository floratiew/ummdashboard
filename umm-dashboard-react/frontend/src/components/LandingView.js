import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Chip,
  Paper,
  Avatar,
  Divider
} from '@mui/material';
import {
  ElectricBolt,
  Factory,
  TrendingUp,
  Warning,
  CheckCircle,
  Info,
  ArrowForward,
  Schedule,
  ShowChart
} from '@mui/icons-material';
import axios from 'axios';

function LandingView({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: <ElectricBolt sx={{ fontSize: 40 }} />,
      title: 'Market Messages',
      description: 'Browse and filter 103K+ urgent market messages from Nord Pool',
      color: '#667eea',
      view: 'dashboard'
    },
    {
      icon: <Factory sx={{ fontSize: 40 }} />,
      title: 'Production Units',
      description: 'Analyze outage events by production and generation units',
      color: '#f093fb',
      view: 'units'
    },
    {
      icon: <TrendingUp sx={{ fontSize: 40 }} />,
      title: 'Outage Analysis',
      description: 'Comprehensive outage analysis with MW threshold filtering',
      color: '#4facfe',
      view: 'outages'
    }
  ];

  return (
    <Box>
      {/* Hero Section */}
      <Box 
        sx={{ 
          mb: 6,
          p: 6,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: 4,
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <Typography variant="h2" sx={{ fontWeight: 800, mb: 2, color: 'white' }}>
            ⚡ Nord Pool UMM Dashboard
          </Typography>
          <Typography variant="h5" sx={{ mb: 3, color: 'rgba(255,255,255,0.9)', fontWeight: 400 }}>
            Urgent Market Messages Analysis Platform
          </Typography>
          <Typography variant="body1" sx={{ mb: 4, color: 'rgba(255,255,255,0.8)', maxWidth: 800 }}>
            Explore comprehensive data on production unavailability, consumption constraints, 
            transmission outages, and market notices from the Nordic electricity market. 
            Analyze trends, track outages, and gain insights into market conditions.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button 
              variant="contained" 
              size="large"
              onClick={() => onNavigate('dashboard')}
              endIcon={<ArrowForward />}
              sx={{ 
                bgcolor: 'white', 
                color: '#667eea',
                fontWeight: 600,
                '&:hover': { bgcolor: 'rgba(255,255,255,0.9)' }
              }}
            >
              Explore Messages
            </Button>
            <Button 
              variant="outlined" 
              size="large"
              onClick={() => onNavigate('outages')}
              sx={{ 
                borderColor: 'white', 
                color: 'white',
                fontWeight: 600,
                '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.1)' }
              }}
            >
              View Outages
            </Button>
          </Box>
        </Box>
        
        {/* Decorative Elements */}
        <Box 
          sx={{ 
            position: 'absolute', 
            top: -50, 
            right: -50, 
            width: 300, 
            height: 300, 
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.1)',
            filter: 'blur(60px)'
          }} 
        />
        <Box 
          sx={{ 
            position: 'absolute', 
            bottom: -100, 
            left: -100, 
            width: 400, 
            height: 400, 
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.05)',
            filter: 'blur(80px)'
          }} 
        />
      </Box>

      {/* Quick Stats */}
      {stats && (
        <Grid container spacing={3} sx={{ mb: 6 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ 
              background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(102, 126, 234, 0.05) 100%)',
              border: '2px solid rgba(102, 126, 234, 0.3)',
              height: '100%'
            }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ bgcolor: '#667eea', mr: 2 }}>
                    <ElectricBolt />
                  </Avatar>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Total Messages
                  </Typography>
                </Box>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#667eea', mb: 1 }}>
                  {stats.totalMessages?.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Market messages tracked
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ 
              background: 'linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(76, 175, 80, 0.05) 100%)',
              border: '2px solid rgba(76, 175, 80, 0.3)',
              height: '100%'
            }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ bgcolor: '#4caf50', mr: 2 }}>
                    <CheckCircle />
                  </Avatar>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Production Units
                  </Typography>
                </Box>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#4caf50', mb: 1 }}>
                  {stats.uniqueUnits?.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Tracked production facilities
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ 
              background: 'linear-gradient(135deg, rgba(244, 67, 54, 0.2) 0%, rgba(244, 67, 54, 0.05) 100%)',
              border: '2px solid rgba(244, 67, 54, 0.3)',
              height: '100%'
            }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ bgcolor: '#f44336', mr: 2 }}>
                    <Warning />
                  </Avatar>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Outage Events
                  </Typography>
                </Box>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#f44336', mb: 1 }}>
                  {stats.totalOutages?.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Recorded outage incidents
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ 
              background: 'linear-gradient(135deg, rgba(255, 152, 0, 0.2) 0%, rgba(255, 152, 0, 0.05) 100%)',
              border: '2px solid rgba(255, 152, 0, 0.3)',
              height: '100%'
            }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ bgcolor: '#ff9800', mr: 2 }}>
                    <Schedule />
                  </Avatar>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Time Range
                  </Typography>
                </Box>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#ff9800', mb: 1 }}>
                  {stats.yearRange || '2013-2025'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Years of data coverage
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Features Section */}
      <Box sx={{ mb: 6 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
          🚀 Explore Features
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          Navigate through different analysis tools and insights
        </Typography>

        <Grid container spacing={3}>
          {features.map((feature, idx) => (
            <Grid item xs={12} md={4} key={idx}>
              <Card 
                sx={{ 
                  height: '100%',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    transform: 'translateY(-8px)',
                    boxShadow: `0 12px 40px rgba(${feature.color === '#667eea' ? '102, 126, 234' : feature.color === '#f093fb' ? '240, 147, 251' : '79, 172, 254'}, 0.3)`
                  }
                }}
                onClick={() => onNavigate(feature.view)}
              >
                <CardContent sx={{ p: 4 }}>
                  <Box 
                    sx={{ 
                      display: 'inline-flex',
                      p: 2,
                      borderRadius: 3,
                      bgcolor: `${feature.color}20`,
                      color: feature.color,
                      mb: 3
                    }}
                  >
                    {feature.icon}
                  </Box>
                  <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
                    {feature.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    {feature.description}
                  </Typography>
                  <Button 
                    endIcon={<ArrowForward />}
                    sx={{ color: feature.color, fontWeight: 600 }}
                  >
                    Explore
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Message Type Breakdown */}
      {stats && stats.messageTypeBreakdown && (
        <Box sx={{ mb: 6 }}>
          <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
            📊 Message Distribution
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Breakdown of market messages by type
          </Typography>

          <Grid container spacing={3}>
            {Object.entries(stats.messageTypeBreakdown).map(([type, count], idx) => {
              const colors = ['#667eea', '#f093fb', '#4facfe', '#ffd93d', '#6bcf7f'];
              const color = colors[idx % colors.length];
              const percentage = ((count / stats.totalMessages) * 100).toFixed(1);
              
              return (
                <Grid item xs={12} sm={6} md={4} key={type}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          {type}
                        </Typography>
                        <Chip 
                          label={`${percentage}%`} 
                          size="small"
                          sx={{ 
                            bgcolor: `${color}20`,
                            color: color,
                            fontWeight: 600
                          }}
                        />
                      </Box>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: color, mb: 2 }}>
                        {count.toLocaleString()}
                      </Typography>
                      <Box 
                        sx={{ 
                          height: 6,
                          borderRadius: 3,
                          bgcolor: 'rgba(255,255,255,0.1)',
                          overflow: 'hidden'
                        }}
                      >
                        <Box 
                          sx={{ 
                            height: '100%',
                            width: `${percentage}%`,
                            bgcolor: color,
                            transition: 'width 1s ease'
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
      )}

      {/* About Section */}
      <Card sx={{ p: 4, background: 'linear-gradient(145deg, #2a1a4a 0%, #1a1232 100%)', border: '2px solid rgba(102, 126, 234, 0.2)' }}>
        <Grid container spacing={4}>
          <Grid item xs={12} md={6}>
            <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>
              About this dashboard
            </Typography>
            <Typography variant="body1" color="text.secondary">
              This dashboard provides comprehensive analysis tools to explore historical UMM data, 
              track outage patterns, and gain insights into Nordic electricity market dynamics.
            </Typography>
          </Grid> 
          <Grid item xs={12} md={6}>
            <Typography variant="h5" sx={{ mb: 2, fontWeight: 700 }}>
              Data Categories
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#ff6b6b' }} />
                <Typography variant="body1">
                  <strong>Production Unavailability</strong> - Power plant outages and capacity reductions
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#6bcf7f' }} />
                <Typography variant="body1">
                  <strong>Consumption Unavailability</strong> - Demand-side constraints and reductions
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#ffd93d' }} />
                <Typography variant="body1">
                  <strong>Transmission Outages</strong> - Grid infrastructure unavailability
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#667eea' }} />
                <Typography variant="body1">
                  <strong>Market Notices</strong> - General market information and updates
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </Card>
    </Box>
  );
}

export default LandingView;
