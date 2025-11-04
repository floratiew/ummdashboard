import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Grid,
  Switch,
  FormControlLabel,
  Paper,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress
} from '@mui/material';
import { MapContainer, TileLayer, Marker, Popup, Circle, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Nordic price areas with approximate coordinates
const priceAreaLocations = {
  'NO1': { lat: 69.6492, lng: 18.9553, name: 'Oslo', color: '#667eea' },
  'NO2': { lat: 60.3913, lng: 5.3221, name: 'Kristiansand', color: '#f093fb' },
  'NO3': { lat: 63.4305, lng: 10.3951, name: 'Trondheim', color: '#4facfe' },
  'NO4': { lat: 69.6496, lng: 18.9560, name: 'Tromsø', color: '#ffd93d' },
  'NO5': { lat: 60.4720, lng: 8.4689, name: 'Bergen', color: '#6bcf7f' },
  'SE1': { lat: 65.5848, lng: 22.1547, name: 'Luleå', color: '#ff6b6b' },
  'SE2': { lat: 62.3908, lng: 17.3069, name: 'Sundsvall', color: '#a29bfe' },
  'SE3': { lat: 59.3293, lng: 18.0686, name: 'Stockholm', color: '#fd79a8' },
  'SE4': { lat: 55.6050, lng: 13.0038, name: 'Malmö', color: '#fdcb6e' },
  'FI': { lat: 60.1695, lng: 24.9354, name: 'Helsinki', color: '#74b9ff' },
  'DK1': { lat: 56.2639, lng: 9.5018, name: 'Jutland', color: '#55efc4' },
  'DK2': { lat: 55.6761, lng: 12.5683, name: 'Copenhagen', color: '#81ecec' },
  'EE': { lat: 59.4370, lng: 24.7536, name: 'Tallinn', color: '#fab1a0' },
  'LT': { lat: 54.6872, lng: 25.2797, name: 'Vilnius', color: '#a29bfe' },
  'LV': { lat: 56.9496, lng: 24.1052, name: 'Riga', color: '#fd79a8' }
};

// Custom icons for different types
const createCustomIcon = (color, type) => {
  const svgIcon = type === 'unit' 
    ? `<svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
         <circle cx="15" cy="15" r="12" fill="${color}" opacity="0.8" stroke="white" stroke-width="2"/>
         <text x="15" y="20" text-anchor="middle" fill="white" font-size="16" font-weight="bold">⚡</text>
       </svg>`
    : `<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
         <rect x="5" y="5" width="30" height="30" fill="${color}" opacity="0.6" stroke="white" stroke-width="2" rx="5"/>
         <text x="20" y="27" text-anchor="middle" fill="white" font-size="14" font-weight="bold">📍</text>
       </svg>`;
  
  return L.divIcon({
    html: svgIcon,
    className: 'custom-icon',
    iconSize: type === 'unit' ? [30, 30] : [40, 40],
    iconAnchor: type === 'unit' ? [15, 15] : [20, 20],
  });
};

function MapView() {
  const [units, setUnits] = useState([]);
  const [selectedUnit, setSelectedUnit] = useState('');
  const [showUnits, setShowUnits] = useState(true);
  const [showAreas, setShowAreas] = useState(true);
  const [loading, setLoading] = useState(true);
  const [unitData, setUnitData] = useState(null);

  useEffect(() => {
    fetchUnits();
  }, []);

  useEffect(() => {
    if (selectedUnit) {
      fetchUnitDetails(selectedUnit);
    }
  }, [selectedUnit]);

  const fetchUnits = async () => {
    try {
      const res = await axios.get('/api/filters');
      setUnits(res.data.units || []);
    } catch (error) {
      console.error('Error fetching units:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUnitDetails = async (unitName) => {
    try {
      const res = await axios.get(`/api/units/${encodeURIComponent(unitName)}`);
      setUnitData(res.data);
    } catch (error) {
      console.error('Error fetching unit details:', error);
    }
  };

  // Generate approximate coordinates for production units based on their areas
  const getUnitCoordinates = (unitName, areas) => {
    if (!areas || areas.length === 0) return null;
    
    const primaryArea = areas[0];
    const baseLocation = priceAreaLocations[primaryArea];
    
    if (!baseLocation) return null;
    
    // Add some random offset to spread units around the area
    const hash = unitName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const latOffset = (hash % 100) / 100 - 0.5;
    const lngOffset = ((hash * 7) % 100) / 100 - 0.5;
    
    return {
      lat: baseLocation.lat + latOffset,
      lng: baseLocation.lng + lngOffset,
      area: primaryArea
    };
  };

  // Create unit markers with coordinates
  const unitMarkers = units
    .map(unit => {
      // For demo purposes, assign random areas from Nordic countries
      // In production, this should come from your actual data
      const areaKeys = Object.keys(priceAreaLocations);
      const randomArea = areaKeys[unit.length % areaKeys.length];
      const coords = getUnitCoordinates(unit, [randomArea]);
      
      return coords ? { name: unit, ...coords } : null;
    })
    .filter(Boolean);

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>
          🗺️ Geographic Distribution
        </Typography>
        <Typography color="text.secondary">
          Interactive map of production units and price areas across the Nordic region
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Map Controls */}
        <Grid item xs={12} lg={3}>
          <Card sx={{ mb: 3, p: 2 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              🎛️ Map Controls
            </Typography>
            
            <FormControlLabel
              control={
                <Switch 
                  checked={showAreas} 
                  onChange={(e) => setShowAreas(e.target.checked)}
                  color="primary"
                />
              }
              label="Show Price Areas"
              sx={{ mb: 2 }}
            />
            
            <FormControlLabel
              control={
                <Switch 
                  checked={showUnits} 
                  onChange={(e) => setShowUnits(e.target.checked)}
                  color="primary"
                />
              }
              label="Show Production Units"
              sx={{ mb: 3 }}
            />

            <FormControl fullWidth size="small">
              <InputLabel>Select Unit</InputLabel>
              <Select
                value={selectedUnit}
                label="Select Unit"
                onChange={(e) => setSelectedUnit(e.target.value)}
              >
                <MenuItem value="">All Units</MenuItem>
                {units.slice(0, 50).map(unit => (
                  <MenuItem key={unit} value={unit}>{unit}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Card>

          {/* Legend */}
          <Card sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              📌 Legend
            </Typography>
            
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
              Price Areas:
            </Typography>
            <Box sx={{ mb: 2 }}>
              {Object.entries(priceAreaLocations).map(([code, { name, color }]) => (
                <Chip
                  key={code}
                  label={`${code} - ${name}`}
                  size="small"
                  sx={{ 
                    mr: 1, 
                    mb: 1,
                    bgcolor: `${color}30`,
                    color: color,
                    border: `1px solid ${color}`,
                    fontWeight: 600
                  }}
                />
              ))}
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
              Symbols:
            </Typography>
            <List dense>
              <ListItem>
                <Box sx={{ 
                  width: 24, 
                  height: 24, 
                  borderRadius: '50%', 
                  bgcolor: '#667eea',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mr: 2,
                  fontSize: 14
                }}>
                  ⚡
                </Box>
                <ListItemText primary="Production Unit" />
              </ListItem>
              <ListItem>
                <Box sx={{ 
                  width: 24, 
                  height: 24, 
                  borderRadius: 1, 
                  bgcolor: '#f093fb',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mr: 2,
                  fontSize: 12
                }}>
                  📍
                </Box>
                <ListItemText primary="Price Area" />
              </ListItem>
            </List>
          </Card>

          {/* Unit Details */}
          {unitData && selectedUnit && (
            <Card sx={{ mt: 3, p: 2 }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                📊 {unitData.unitName}
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText 
                    primary="Total Events" 
                    secondary={unitData.totalEvents?.toLocaleString()}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Capacity" 
                    secondary={unitData.capacity ? `${unitData.capacity.toLocaleString()} MW` : 'N/A'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Areas" 
                    secondary={unitData.areas?.join(', ') || 'N/A'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Owner" 
                    secondary={unitData.owner || 'Unknown'}
                  />
                </ListItem>
              </List>
            </Card>
          )}
        </Grid>

        {/* Map */}
        <Grid item xs={12} lg={9}>
          <Card sx={{ height: 800, overflow: 'hidden' }}>
            <MapContainer
              center={[62.0, 15.0]}
              zoom={4}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* Price Area Markers */}
              {showAreas && Object.entries(priceAreaLocations).map(([code, { lat, lng, name, color }]) => (
                <React.Fragment key={code}>
                  <Circle
                    center={[lat, lng]}
                    radius={100000}
                    pathOptions={{
                      color: color,
                      fillColor: color,
                      fillOpacity: 0.2,
                      weight: 2
                    }}
                  />
                  <Marker 
                    position={[lat, lng]}
                    icon={createCustomIcon(color, 'area')}
                  >
                    <Popup>
                      <Box sx={{ p: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700, color: color }}>
                          {code}
                        </Typography>
                        <Typography variant="body2">
                          {name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Price Area
                        </Typography>
                      </Box>
                    </Popup>
                    <Tooltip direction="top" offset={[0, -20]} opacity={0.9}>
                      <span style={{ fontWeight: 600 }}>{code} - {name}</span>
                    </Tooltip>
                  </Marker>
                </React.Fragment>
              ))}

              {/* Production Unit Markers */}
              {showUnits && unitMarkers.slice(0, 100).map((unit, idx) => {
                const color = priceAreaLocations[unit.area]?.color || '#667eea';
                return (
                  <Marker
                    key={idx}
                    position={[unit.lat, unit.lng]}
                    icon={createCustomIcon(color, 'unit')}
                    eventHandlers={{
                      click: () => setSelectedUnit(unit.name)
                    }}
                  >
                    <Popup>
                      <Box sx={{ p: 1, minWidth: 150 }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                          {unit.name}
                        </Typography>
                        <Chip 
                          label={unit.area}
                          size="small"
                          sx={{ 
                            mt: 1,
                            bgcolor: `${color}30`,
                            color: color,
                            fontWeight: 600
                          }}
                        />
                      </Box>
                    </Popup>
                    <Tooltip direction="top" offset={[0, -10]} opacity={0.9}>
                      <span>{unit.name}</span>
                    </Tooltip>
                  </Marker>
                );
              })}
            </MapContainer>
          </Card>

          {/* Map Statistics */}
          <Grid container spacing={2} sx={{ mt: 2 }}>
            <Grid item xs={12} sm={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Price Areas
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#667eea' }}>
                    {Object.keys(priceAreaLocations).length}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Production Units
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#f093fb' }}>
                    {units.length.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Displayed on Map
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#4facfe' }}>
                    {Math.min(100, unitMarkers.length)}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Box>
  );
}

export default MapView;
