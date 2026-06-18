# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GeoVision AI                             │
│                   Land-Use Planning Dashboard                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Pages      │  │   Layouts    │  │  Components  │          │
│  │              │  │              │  │              │          │
│  │ - HomePage   │  │ - Main       │  │ - Map        │          │
│  │ - Placeholder│  │ - Dashboard  │  │ - Panels     │          │
│  └──────────────┘  └──────────────┘  │ - Cards      │          │
│                                       │ - Navigation │          │
│  ┌──────────────┐  ┌──────────────┐  └──────────────┘          │
│  │   Hooks      │  │    Utils     │                             │
│  │              │  │              │                             │
│  │ - Simulation │  │ - API        │  ┌──────────────┐          │
│  │ - MapControl │  │ - GeoJSON    │  │   Config     │          │
│  └──────────────┘  │ - Simulation │  │              │          │
│                    └──────────────┘  │ - Constants  │          │
│                                      │ - Types      │          │
│                                      └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (TODO)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    REST API / GraphQL                     │  │
│  │                                                            │  │
│  │  GET  /api/metrics                                        │  │
│  │  GET  /api/zones?region={name}                           │  │
│  │  POST /api/optimize                                       │  │
│  │  POST /api/agents/zoning                                  │  │
│  │  POST /api/agents/environmental                           │  │
│  │  POST /api/agents/population                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   AI Agents      │  │   GIS Services   │  │    Database      │
│   (TODO)         │  │   (TODO)         │  │    (TODO)        │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│                  │  │                  │  │                  │
│ - Zoning Agent   │  │ - Mapbox/Leaflet │  │ - PostGIS        │
│ - Environmental  │  │ - GeoJSON Parser │  │   or             │
│ - Population     │  │ - Coordinate     │  │ - MongoDB        │
│                  │  │   Conversion     │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Component Hierarchy

```
App
├── MainLayout
│   ├── Sidebar (Navigation)
│   └── [Active View]
│       ├── HomePage
│       │   └── DashboardLayout
│       │       ├── MetricsPanel
│       │       │   └── MetricCard (×3)
│       │       ├── MapPanel
│       │       │   ├── MapCanvas
│       │       │   ├── MapLegend
│       │       │   └── MapControls
│       │       ├── ToolsPanel
│       │       └── StatusBar
│       ├── LayersPage (Placeholder)
│       ├── AgentsPage (Placeholder)
│       ├── ConstraintsPage (Placeholder)
│       └── SettingsPage (Placeholder)
└── AgentDetailPanel (Modal)
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Actions                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      React Components                            │
│                                                                   │
│  User clicks button → Component handler → Custom hook           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Custom Hooks                               │
│                                                                   │
│  useSimulation → Updates metrics, zones                          │
│  useMapControls → Updates map state                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Utility Functions                           │
│                                                                   │
│  updateMetrics() → Calculate new values                          │
│  updateZoneCompliance() → Update zones                           │
│  exportGeoJSON() → Transform and export                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Client (TODO)                           │
│                                                                   │
│  apiClient.fetchMetrics() → Backend API                          │
│  apiClient.runZoningAgent() → AI Agent Service                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend Services (TODO)                       │
│                                                                   │
│  FastAPI → Database → AI Agents → GIS Services                   │
└─────────────────────────────────────────────────────────────────┘
```

## State Management

```
┌─────────────────────────────────────────────────────────────────┐
│                         App.tsx (Root)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  State:                                                           │
│  - activeView: ViewType                                          │
│  - selectedAgent: string | null                                  │
│  - selectedRegion: string                                        │
│                                                                   │
│  Custom Hooks:                                                    │
│  - useSimulation() → metrics, zones, isPlaying, etc.            │
│  - useMapControls() → mapStyle, zoomLevel, layers, etc.         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │   useSimulation  │    │  useMapControls  │
        ├──────────────────┤    ├──────────────────┤
        │                  │    │                  │
        │ - metrics        │    │ - mapStyle       │
        │ - zones          │    │ - zoomLevel      │
        │ - isPlaying      │    │ - enabledLayers  │
        │ - speed          │    │ - toggleLayer()  │
        │ - time           │    │ - selectZone()   │
        │                  │    │                  │
        └──────────────────┘    └──────────────────┘
```

## File Organization

```
src/
│
├── components/              # UI Components
│   ├── cards/              # Reusable card components
│   │   └── MetricCard.tsx
│   ├── map/                # Map-related components
│   │   ├── MapCanvas.tsx   # Map rendering
│   │   ├── MapControls.tsx # Zoom, info controls
│   │   ├── MapLegend.tsx   # Legend display
│   │   └── MapPanel.tsx    # Main map container
│   ├── navigation/         # Navigation components
│   │   ├── Sidebar.tsx     # Main sidebar
│   │   └── StatusBar.tsx   # Bottom status bar
│   ├── panels/             # Panel components
│   │   ├── MetricsPanel.tsx
│   │   └── ToolsPanel.tsx
│   ├── ui/                 # shadcn/ui components
│   └── AgentDetailPanel.tsx
│
├── config/                 # Configuration
│   └── constants.ts        # App constants, colors, configs
│
├── hooks/                  # Custom React hooks
│   ├── useMapControls.ts   # Map interaction logic
│   └── useSimulation.ts    # Simulation logic
│
├── layouts/                # Layout components
│   ├── DashboardLayout.tsx # Dashboard with panels
│   └── MainLayout.tsx      # App shell with sidebar
│
├── pages/                  # Page components
│   ├── HomePage.tsx        # Main dashboard
│   └── PlaceholderPage.tsx # Placeholder for future pages
│
├── types/                  # TypeScript definitions
│   └── index.ts            # All type definitions
│
├── utils/                  # Utility functions
│   ├── api.ts              # API client (TODO: implement)
│   ├── geojson.ts          # GeoJSON utilities
│   └── simulation.ts       # Simulation algorithms
│
├── styles/                 # Global styles
│   └── globals.css
│
├── App.tsx                 # Main app component
└── main.tsx                # Entry point
```

## Integration Points

### 1. Backend API (`src/utils/api.ts`)
```typescript
class ApiClient {
  // TODO: Implement these methods
  async fetchMetrics(): Promise<Metrics>
  async fetchZones(region: string): Promise<LandUseZone[]>
  async runOptimization(zones: LandUseZone[]): Promise<LandUseZone[]>
  async runZoningAgent(input: unknown): Promise<unknown>
  async runEnvironmentalAgent(input: unknown): Promise<unknown>
  async runPopulationAgent(input: unknown): Promise<unknown>
}
```

### 2. GIS Services (`src/utils/geojson.ts`)
```typescript
// TODO: Implement coordinate conversion
function zonesToGeoJSON(zones: LandUseZone[], region: string): GeoJSONExport

// TODO: Implement GeoJSON parsing
async function loadGeoJSON(file: File): Promise<LandUseZone[]>

function exportGeoJSON(zones: LandUseZone[], region: string): void
```

### 3. AI Agents (API endpoints)
```
POST /api/agents/zoning
POST /api/agents/environmental
POST /api/agents/population
```

### 4. Database (Backend)
```
- PostGIS for spatial data
- MongoDB for document storage
- Redis for caching
```

## Technology Stack

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui + Radix UI
- **Charts**: Recharts
- **Animation**: Framer Motion
- **State**: React Hooks (useState, useEffect, custom hooks)

### Backend (TODO)
- **API**: FastAPI or Node.js/Express
- **Database**: PostGIS or MongoDB
- **Cache**: Redis
- **Queue**: Celery or Bull

### AI Agents (TODO)
- **Framework**: Python (scikit-learn, TensorFlow)
- **Deployment**: Docker containers
- **Communication**: REST API or gRPC

### GIS (TODO)
- **Map Library**: Mapbox GL JS or Leaflet
- **Spatial Database**: PostGIS
- **Format**: GeoJSON

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Frontend       │  │   API Server     │  │   AI Agents      │
│   (Static)       │  │   (FastAPI)      │  │   (Python)       │
│                  │  │                  │  │                  │
│ - React App      │  │ - REST API       │  │ - Zoning         │
│ - Nginx/CDN      │  │ - WebSocket      │  │ - Environmental  │
│                  │  │ - Auth           │  │ - Population     │
└──────────────────┘  └──────────────────┘  └──────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Database       │  │   Cache          │  │   Storage        │
│   (PostGIS)      │  │   (Redis)        │  │   (S3/Blob)      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Security Considerations

- [ ] API authentication (JWT tokens)
- [ ] CORS configuration
- [ ] Rate limiting
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] HTTPS only
- [ ] Environment variable security

## Performance Optimizations

- [ ] Code splitting
- [ ] Lazy loading
- [ ] Image optimization
- [ ] Bundle size optimization
- [ ] Caching strategy
- [ ] Database indexing
- [ ] API response compression
- [ ] CDN for static assets

## Monitoring & Logging

- [ ] Error tracking (Sentry)
- [ ] Analytics (Google Analytics)
- [ ] Performance monitoring (Lighthouse)
- [ ] API logging
- [ ] User activity tracking
- [ ] System health checks

## Scalability

### Horizontal Scaling
- Load balancer for multiple frontend instances
- Multiple API server instances
- Distributed AI agent workers
- Database replication

### Vertical Scaling
- Optimize database queries
- Implement caching
- Use CDN for static assets
- Optimize bundle size

## Future Enhancements

1. **Real-time Collaboration**
   - WebSocket for live updates
   - Operational transformation
   - User presence indicators

2. **Advanced Analytics**
   - Time-series analysis
   - Predictive modeling
   - Scenario comparison

3. **Mobile Support**
   - Responsive design
   - Touch gestures
   - Offline mode

4. **Export Options**
   - PDF reports
   - CAD formats
   - 3D models

5. **Integration APIs**
   - Third-party GIS systems
   - Government databases
   - Planning tools
