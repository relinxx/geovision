# Quick Start Guide

Get the GeoVision AI dashboard running in 5 minutes.

## Prerequisites

- Node.js 18 or higher
- npm or yarn

## Installation

```bash
# 1. Install dependencies
npm install

# 2. Copy environment file
cp .env.example .env

# 3. Start development server
npm run dev
```

The application will open at `http://localhost:3000`

## First Steps

### 1. Explore the Dashboard

- **Left Panel**: Real-time metrics and analytics
- **Center**: Interactive map with land-use zones
- **Right Panel**: AI agents and constraint layers
- **Bottom**: Export and optimization controls

### 2. Run a Simulation

1. Click the **Play** button in the top control bar
2. Adjust simulation speed (Slow/Medium/Fast)
3. Watch metrics update in real-time
4. Click **Reset** to restart

### 3. Interact with Zones

- Click any zone on the map to select it
- View zone details in the info panel
- Check compliance indicators

### 4. Enable Constraint Layers

In the right panel:
- Toggle **Flood Zones**
- Toggle **Zoning Laws**
- Toggle **Population Targets**

### 5. Explore AI Agents

Click on any agent card:
- **Environmental Agent**: Risk analysis
- **Zoning Agent**: Compliance checking
- **Population Agent**: Density optimization

### 6. Export Data

Click **Export GeoJSON** to download current zone data

### 7. Run Optimization

Click **Run Optimization** to improve compliance scores

## Project Structure

```
src/
├── components/     # UI components
├── pages/          # Page views
├── hooks/          # Custom hooks
├── utils/          # Utilities
├── config/         # Configuration
└── types/          # TypeScript types
```

## Key Features

### Current (Working)
✅ Real-time simulation
✅ Interactive map visualization
✅ Metrics dashboard
✅ AI agent panels
✅ GeoJSON export
✅ Zone selection
✅ Layer toggles

### Future (TODO)
🔲 Backend API integration
🔲 Real map service (Mapbox/Leaflet)
🔲 GeoJSON import
🔲 Database persistence
🔲 AI agent execution
🔲 User authentication
🔲 Multi-user collaboration

## Development

### Available Scripts

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Adding Features

See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for architecture details.

### Integration

See [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) for backend/API integration.

## Customization

### Change Colors

Edit `src/config/constants.ts`:

```typescript
export const COLORS = {
  primary: '#4FFFA7',    // Change primary color
  secondary: '#3BC7F5',  // Change secondary color
  // ...
}
```

### Add New Zone Type

1. Update `ZONE_TYPES` in `src/config/constants.ts`
2. Add type to `ZoneType` in `src/types/index.ts`
3. Update zone rendering logic

### Add New Metric

1. Add to `Metrics` interface in `src/types/index.ts`
2. Update `updateMetrics` in `src/utils/simulation.ts`
3. Add MetricCard in `MetricsPanel.tsx`

## Troubleshooting

### Port Already in Use

```bash
# Change port in vite.config.ts
server: {
  port: 3001,  // Use different port
}
```

### Build Errors

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

### TypeScript Errors

```bash
# Check for type errors
npx tsc --noEmit
```

## Next Steps

1. **Explore the Code**: Start with `src/App.tsx`
2. **Read Architecture**: Check `PROJECT_STRUCTURE.md`
3. **Plan Integration**: Review `INTEGRATION_GUIDE.md`
4. **Customize**: Modify colors, add features
5. **Deploy**: Build and deploy to your platform

## Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Vite Guide](https://vitejs.dev/guide/)

## Support

- Check console for errors
- Review TODO comments in code
- See integration guide for API setup
- Check project structure for architecture

Happy coding! 🚀
