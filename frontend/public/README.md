# Public Assets

This folder contains static assets served by Vite.

## Required GeoJSON Files

The following GeoJSON files should be placed in this directory:

- `parcels_env_risk_clipped.geojson` - Used by HomePage for environmental risk visualization
- `parcels_unified.geojson` - Used by LayersPage for unified parcel layer

These files are referenced in the application as:
- `/parcels_env_risk_clipped.geojson`
- `/parcels_unified.geojson`

## Note

If these files are missing, the map will display an error message. Place the GeoJSON files here to enable map functionality.

