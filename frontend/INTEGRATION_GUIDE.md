# Integration Guide

This guide explains how to integrate the frontend with backend services, AI agents, and GIS systems.

## Table of Contents

1. [Backend API Integration](#backend-api-integration)
2. [AI Agent Integration](#ai-agent-integration)
3. [GIS/Map Integration](#gismap-integration)
4. [Database Integration](#database-integration)

---

## Backend API Integration

### Step 1: Configure API Endpoint

Update `.env` file:
```env
VITE_API_URL=http://your-backend-url/api
```

### Step 2: Implement API Methods

Edit `src/utils/api.ts` and replace TODO comments with actual implementations:

```typescript
// Example: Fetch metrics from backend
async fetchMetrics(): Promise<Metrics> {
  const response = await fetch(`${this.baseUrl}/metrics`);
  if (!response.ok) throw new Error('Failed to fetch metrics');
  return response.json();
}
```

### Step 3: Update Components

Replace mock data with API calls:

```typescript
// In your component
import { apiClient } from '../utils/api';

useEffect(() => {
  apiClient.fetchMetrics()
    .then(setMetrics)
    .catch(console.error);
}, []);
```

### Expected API Endpoints

```
GET  /api/metrics              - Get current metrics
GET  /api/zones?region={name}  - Get zones for region
POST /api/optimize             - Run optimization
POST /api/agents/zoning        - Run zoning agent
POST /api/agents/environmental - Run environmental agent
POST /api/agents/population    - Run population agent
```

---

## AI Agent Integration

### Agent Architecture

Each agent should expose:
- Input schema
- Output schema
- Configuration parameters
- Real-time status updates

### Step 1: Define Agent Input/Output Types

Add to `src/types/index.ts`:

```typescript
export interface ZoningAgentInput {
  zones: LandUseZone[];
  constraints: Constraint[];
  regulations: ZoningRegulation[];
}

export interface ZoningAgentOutput {
  compliance: number;
  violations: Violation[];
  recommendations: Recommendation[];
}
```

### Step 2: Implement Agent API Calls

Update `src/utils/api.ts`:

```typescript
async runZoningAgent(input: ZoningAgentInput): Promise<ZoningAgentOutput> {
  const response = await fetch(`${this.baseUrl}/agents/zoning`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return response.json();
}
```

### Step 3: Connect to UI

Update agent detail panel to show real data:

```typescript
// In AgentDetailPanel.tsx
const [agentData, setAgentData] = useState(null);

useEffect(() => {
  if (agent === 'zoning') {
    apiClient.runZoningAgent({ zones, constraints, regulations })
      .then(setAgentData);
  }
}, [agent, zones]);
```

### WebSocket for Real-time Updates

```typescript
// Add to src/utils/api.ts
connectAgentWebSocket(agentId: string, onMessage: (data: any) => void) {
  const ws = new WebSocket(`${WS_URL}/agents/${agentId}`);
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  return ws;
}
```

---

## GIS/Map Integration

### Option 1: Mapbox Integration

#### Install Mapbox

```bash
npm install mapbox-gl @types/mapbox-gl
```

#### Replace MapCanvas Component

```typescript
// src/components/map/MapCanvas.tsx
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

export function MapCanvas({ zones, onZoneSelect }: MapCanvasProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [-74.5, 40],
      zoom: 9,
    });

    // Add zones as GeoJSON layer
    map.current.on('load', () => {
      map.current?.addSource('zones', {
        type: 'geojson',
        data: zonesToGeoJSON(zones, 'region'),
      });

      map.current?.addLayer({
        id: 'zones-layer',
        type: 'fill',
        source: 'zones',
        paint: {
          'fill-color': ['get', 'color'],
          'fill-opacity': 0.6,
        },
      });
    });

    return () => map.current?.remove();
  }, []);

  return <div ref={mapContainer} className="w-full h-full" />;
}
```

### Option 2: Leaflet Integration

```bash
npm install leaflet react-leaflet @types/leaflet
```

```typescript
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';

export function MapCanvas({ zones }: MapCanvasProps) {
  return (
    <MapContainer center={[40, -74]} zoom={10} className="w-full h-full">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <GeoJSON data={zonesToGeoJSON(zones, 'region')} />
    </MapContainer>
  );
}
```

### Loading GeoJSON Files

Implement in `src/utils/geojson.ts`:

```typescript
export async function loadGeoJSON(file: File): Promise<LandUseZone[]> {
  const text = await file.text();
  const geojson = JSON.parse(text) as GeoJSONExport;

  return geojson.features.map((feature, index) => ({
    id: feature.properties.id || `zone-${index}`,
    type: feature.properties.type,
    x: feature.geometry.coordinates[0][0][0],
    y: feature.geometry.coordinates[0][0][1],
    width: 100, // Calculate from coordinates
    height: 100,
    population: feature.properties.population,
    compliance: feature.properties.compliance || 100,
  }));
}
```

---

## Database Integration

### PostGIS Setup

#### Schema Example

```sql
CREATE TABLE zones (
  id SERIAL PRIMARY KEY,
  zone_id VARCHAR(50) UNIQUE,
  type VARCHAR(50),
  geometry GEOMETRY(Polygon, 4326),
  population INTEGER,
  compliance INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zones_geometry ON zones USING GIST(geometry);
```

#### Backend API (FastAPI Example)

```python
from fastapi import FastAPI
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String

class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(Integer, primary_key=True)
    zone_id = Column(String(50), unique=True)
    type = Column(String(50))
    geometry = Column(Geometry('POLYGON'))
    population = Column(Integer)
    compliance = Column(Integer)

@app.get("/api/zones")
async def get_zones(region: str):
    zones = db.query(Zone).filter_by(region=region).all()
    return [zone_to_geojson(z) for z in zones]
```

### MongoDB Setup

#### Schema Example

```javascript
{
  _id: ObjectId,
  zoneId: String,
  type: String,
  geometry: {
    type: "Polygon",
    coordinates: [[[lng, lat], ...]]
  },
  properties: {
    population: Number,
    compliance: Number
  },
  metadata: {
    region: String,
    createdAt: Date,
    updatedAt: Date
  }
}
```

---

## Testing Integration

### Unit Tests

```typescript
// src/utils/__tests__/api.test.ts
import { apiClient } from '../api';

describe('API Client', () => {
  it('should fetch metrics', async () => {
    const metrics = await apiClient.fetchMetrics();
    expect(metrics).toHaveProperty('population');
  });
});
```

### Integration Tests

```typescript
// src/__tests__/integration/agents.test.ts
describe('Agent Integration', () => {
  it('should run zoning agent and return results', async () => {
    const result = await apiClient.runZoningAgent(mockInput);
    expect(result.compliance).toBeGreaterThan(0);
  });
});
```

---

## Deployment Checklist

- [ ] Environment variables configured
- [ ] API endpoints tested
- [ ] Map API keys added
- [ ] Database connection verified
- [ ] AI agents responding
- [ ] WebSocket connections stable
- [ ] Error handling implemented
- [ ] Loading states added
- [ ] Authentication integrated
- [ ] CORS configured
- [ ] Rate limiting set up
- [ ] Monitoring enabled

---

## Troubleshooting

### Common Issues

**API Connection Failed**
- Check VITE_API_URL in .env
- Verify backend is running
- Check CORS configuration

**Map Not Loading**
- Verify map API key
- Check network requests
- Ensure map container has height

**Agent Timeout**
- Increase timeout in API client
- Check agent service status
- Verify input data format

**GeoJSON Import Error**
- Validate GeoJSON format
- Check coordinate system (should be WGS84)
- Verify property names match schema

---

## Support

For integration help:
1. Check PROJECT_STRUCTURE.md
2. Review code comments with TODO markers
3. Check console for error messages
4. Verify API responses in Network tab
