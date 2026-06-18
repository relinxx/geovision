# Project Structure

This document outlines the clean, production-ready architecture of the GeoVision AI Land-Use Planning Dashboard.

## Directory Structure

```
src/
├── components/          # Reusable UI components
│   ├── cards/          # Card components (MetricCard, etc.)
│   ├── map/            # Map-related components
│   ├── navigation/     # Navigation components (Sidebar, StatusBar)
│   ├── panels/         # Panel components (MetricsPanel, ToolsPanel)
│   └── ui/             # shadcn/ui components
├── config/             # Configuration and constants
│   └── constants.ts    # App-wide constants
├── hooks/              # Custom React hooks
│   ├── useMapControls.ts
│   └── useSimulation.ts
├── layouts/            # Layout components
│   ├── DashboardLayout.tsx
│   └── MainLayout.tsx
├── pages/              # Page components
│   ├── HomePage.tsx
│   └── PlaceholderPage.tsx
├── types/              # TypeScript type definitions
│   └── index.ts
├── utils/              # Utility functions
│   ├── api.ts          # API service layer
│   ├── geojson.ts      # GeoJSON utilities
│   └── simulation.ts   # Simulation logic
├── styles/             # Global styles
│   └── globals.css
├── App.tsx             # Main application component
└── main.tsx            # Application entry point
```

## Architecture Principles

### 1. Separation of Concerns
- **Components**: Pure UI components with minimal logic
- **Hooks**: Reusable stateful logic
- **Utils**: Pure functions for data transformation
- **Types**: Centralized type definitions

### 2. Component Organization
- **Atomic Design**: Components organized by complexity
- **Feature-based**: Related components grouped together
- **Reusability**: Components designed for maximum reuse

### 3. State Management
- React hooks for local state
- Custom hooks for shared logic
- Props drilling minimized through composition

### 4. Future Integration Points

#### Backend API Integration
- `src/utils/api.ts` - API client ready for FastAPI integration
- All API calls centralized in one place
- Easy to swap mock data with real endpoints

#### AI Agents
- Agent configuration in `src/config/constants.ts`
- Agent detail panel ready for real-time data
- Placeholder functions in API client

#### GIS/Map Integration
- `src/utils/geojson.ts` - GeoJSON import/export utilities
- Map components separated for easy replacement
- Support for multiple map styles

#### Database Integration
- Type definitions ready for backend models
- Data transformation utilities in place
- Easy to connect to PostGIS or MongoDB

## Key Files

### Configuration
- `src/config/constants.ts` - All app constants, colors, and configuration
- `vite.config.ts` - Build configuration

### Types
- `src/types/index.ts` - All TypeScript interfaces and types

### API Layer
- `src/utils/api.ts` - Backend communication (TODO: implement)

### State Management
- `src/hooks/useSimulation.ts` - Simulation state and logic
- `src/hooks/useMapControls.ts` - Map interaction state

### Main Components
- `src/App.tsx` - Main application orchestration
- `src/pages/HomePage.tsx` - Dashboard view
- `src/components/map/MapPanel.tsx` - Map visualization

## Adding New Features

### Adding a New Page
1. Create component in `src/pages/`
2. Add route in `src/App.tsx`
3. Update `ViewType` in `src/types/index.ts`

### Adding a New AI Agent
1. Add configuration to `src/config/constants.ts`
2. Add API method in `src/utils/api.ts`
3. Update agent detail panel logic

### Adding a New Map Layer
1. Add layer config to `src/config/constants.ts`
2. Update map canvas rendering
3. Add layer toggle in tools panel

## Environment Variables

Create a `.env` file in the root directory:

```env
VITE_API_URL=http://localhost:8000/api
VITE_MAP_API_KEY=your_map_api_key
```

## Next Steps

1. **Backend Integration**
   - Implement API client methods
   - Connect to FastAPI endpoints
   - Add authentication

2. **Map Integration**
   - Replace mock map with real GIS library (Mapbox, Leaflet)
   - Implement GeoJSON loading
   - Add coordinate system support

3. **AI Agents**
   - Connect to agent endpoints
   - Implement real-time updates
   - Add agent configuration UI

4. **Database**
   - Set up PostGIS or MongoDB
   - Implement data persistence
   - Add caching layer

5. **Testing**
   - Add unit tests
   - Add integration tests
   - Add E2E tests
