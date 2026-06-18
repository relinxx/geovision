import { ParcelMap } from '../map/ParcelMap';

interface PlanningAreaOverviewCardProps {
  selectedParcelIds: string[];
  totalLoadedParcels: number;
  primaryConstraint: string;
  constrainedParcels: string;
  protectedParcels: string;
  multiConstraintParcels: string;
  onParcelSelect: (parcelId: string, properties: any, feature: any) => void;
  onBulkParcelSelect: (parcelIds: string[], featureById: Map<string, any>) => void;
  onFeaturesLoaded: (features: any[]) => void;
}

const EMPTY_SCORES = new Map();

export function PlanningAreaOverviewCard({
  selectedParcelIds,
  totalLoadedParcels,
  primaryConstraint,
  constrainedParcels,
  protectedParcels,
  multiConstraintParcels,
  onParcelSelect,
  onBulkParcelSelect,
  onFeaturesLoaded,
}: PlanningAreaOverviewCardProps) {
  return (
    <section className="workbench-card workbench-map-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">Planning Area Overview</h2>
          <p className="workbench-section-description">
            Neutral parcel workspace for selection, scoping, and workflow handoff.
          </p>
        </div>
      </header>

      {/* Pill group with consistent 28px height sizing */}
      <div className="workbench-map-meta">
        <span className="pill pill--default">Dataset: parcels_env_risk_clipped.geojson</span>
        <span className="pill pill--secondary">Source: Static GeoJSON</span>
        <span className="pill pill--primary">Loaded Parcels: {totalLoadedParcels || '—'}</span>
        <span className="pill pill--default">Primary Constraint: {primaryConstraint}</span>
        <span className="pill pill--warning">Constrained Parcels: {constrainedParcels}</span>
        <span className="pill pill--primary">Protected Parcels: {protectedParcels}</span>
        <span className="pill pill--warning">
          Multi-Constraint Parcels: {multiConstraintParcels}
        </span>
      </div>

      <div className="workbench-map-frame">
        <ParcelMap
          geoJsonUrl="/parcels_env_risk_clipped.geojson"
          scoresById={EMPTY_SCORES}
          colorMode="neutral"
          selectedParcelIds={selectedParcelIds}
          onParcelSelect={onParcelSelect}
          onBulkParcelSelect={onBulkParcelSelect}
          onFeaturesLoaded={onFeaturesLoaded}
          enableRightDragBulkSelect
          autoFitToData
          lockViewportToData
        />
      </div>
    </section>
  );
}
