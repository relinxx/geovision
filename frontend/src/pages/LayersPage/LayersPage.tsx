/**
 * LayersPage Component
 * ======================
 * Page for exploring map layers with integrated zoning chat assistant.
 * Features a split view with parcel map on the left and RAG chat on the right.
 * 
 * @component
 */
import { useState } from 'react';
import { DashboardLayout } from '../../layouts/DashboardLayout/DashboardLayout';
import { ParcelMap } from '../../components/map/ParcelMap';
import { DeckGLMap } from '../../components/map/DeckGLMap/DeckGLMap';
import { Metrics, LandUseZone } from '../../types';
import { ZoningChatPanel } from '../../components/chat/ZoningChatPanel/ZoningChatPanel';
import { toast } from 'sonner';
import { usePlannerSettings } from '../../context/PlannerSettingsContext';
import { usePlannerWorkspace } from '../../context/PlannerWorkspaceContext';
import './LayersPage.css';

/** Props for the LayersPage component */
interface LayersPageProps {
  metrics: Metrics;
  simulationTime: number;
  zones: LandUseZone[];
  selectedRegion: string;
}

/**
 * LayersPage component.
 * Provides a split-view interface with the parcel map and zoning chat assistant.
 */
export function LayersPage({
  metrics,
  simulationTime,
  zones,
  selectedRegion,
}: LayersPageProps) {
  const { settings } = usePlannerSettings();
  const {
    primarySelectedParcelId,
    primarySelectedParcelProps,
    selectedParcelIds,
    addToSelection,
    setPrimarySelectedParcel,
    registerLoadedParcelFeatures,
  } = usePlannerWorkspace();
  const [autoQueryTrigger, setAutoQueryTrigger] = useState<number>(0);
  const [use3D, setUse3D] = useState(false);

  const handleParcelSelect = (apn: string, props: any, feature: any) => {
    setPrimarySelectedParcel(apn, props, feature);
    addToSelection(apn ? [apn] : [], feature ? new Map([[apn, feature]]) : undefined);

    if (settings.regulatoryGuidance.showParcelTagNotifications) {
      toast.success(`Parcel ${apn} tagged`, {
        description: 'Regulatory guidance available in chat',
        duration: 2000,
      });
    }

    if (settings.regulatoryGuidance.autoFetchParcelGuidance) {
      setAutoQueryTrigger((prev) => prev + 1);
    }
  };

  return (
    <DashboardLayout
      metrics={metrics}
      simulationTime={simulationTime}
      zones={zones}
      selectedRegion={selectedRegion}
    >
      <div className="layers-page">
        <div className="layers-page__content">
          <header className="layers-page__header">
            <h1 className="layers-page__title">Layers & Zoning Assistant</h1>
            <p className="layers-page__description">
              Click parcels on the map to get instant zoning information in the chat.
            </p>
          </header>

          {/* Split View: 50% Map, 50% Chat */}
          <div className="layers-page__split-view">
            {/* Map Section */}
            <section className="layers-panel">
              <div className="layers-panel__header">
                <h2 className="layers-panel__title">
                  <span className="layers-panel__title-dot layers-panel__title-dot--green" />
                  Parcel Map
                </h2>
                <button
                  onClick={() => setUse3D(!use3D)}
                  className="px-3 py-1.5 bg-[#0B1E39]/80 border border-[#4FFFA7]/40 rounded text-xs text-[#4FFFA7] hover:bg-[#4FFFA7]/10 transition-colors"
                >
                  {use3D ? '🗺️ 2D' : '🧊 3D'}
                </button>
              </div>
              <div className="layers-panel__content">
                {use3D ? (
                  <DeckGLMap
                    geoJsonUrl="/parcels_env_risk_clipped.geojson"
                    scoresById={new Map()}
                    colorMode="environmental_risk"
                    selectedParcelIds={selectedParcelIds}
                    onParcelSelect={handleParcelSelect}
                    onFeaturesLoaded={registerLoadedParcelFeatures}
                  />
                ) : (
                  <ParcelMap
                    geoJsonUrl="/parcels_env_risk_clipped.geojson"
                    scoresById={new Map()}
                    colorMode="environmental_risk"
                    selectedParcelIds={selectedParcelIds}
                    onlyWithZoning={true}
                    zoningProperty="ZONING_CODE"
                    zoningExcludeValues={['', 'UNKNOWN', null, undefined]}
                    onParcelSelect={handleParcelSelect}
                    onFeaturesLoaded={registerLoadedParcelFeatures}
                  />
                )}
              </div>
            </section>

            {/* Chat Section */}
            <section className="layers-panel">
              <div className="layers-panel__header">
                <h2 className="layers-panel__title">
                  <span className="layers-panel__title-dot layers-panel__title-dot--cyan" />
                  Zoning RAG Assistant
                </h2>
              </div>
              <div className="layers-panel__content">
                <ZoningChatPanel
                  selectedApn={primarySelectedParcelId}
                  selectedProps={primarySelectedParcelProps}
                  autoQueryTrigger={autoQueryTrigger}
                />
              </div>
            </section>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
