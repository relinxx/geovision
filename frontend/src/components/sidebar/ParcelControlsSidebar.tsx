import { CheckSquare, Square, Hash } from 'lucide-react';

interface ParcelControlsSidebarProps {
  showPlanOverlays: boolean;
  onTogglePlanOverlays: (checked: boolean) => void;
  totalParcels: number;
  selectedParcels: string[];
}

export function ParcelControlsSidebar({
  showPlanOverlays,
  onTogglePlanOverlays,
  totalParcels,
  selectedParcels,
}: ParcelControlsSidebarProps) {
  return (
    <div className="w-72 bg-[#0B1E39] border-r border-[#1a2f4d] overflow-y-auto custom-scrollbar">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="pb-4 border-b border-[#1a2f4d]">
          <h2 className="text-lg font-semibold text-[#D8E2F0] flex items-center gap-2">
            <Hash className="w-5 h-5 text-[#4FFFA7]" />
            Parcel Controls
          </h2>
        </div>

        {/* Plan Overlays Toggle */}
        <div className="space-y-3">
          <label className="flex items-center gap-3 p-4 rounded-xl bg-[#0F1F3D] border border-[#1a2f4d] cursor-pointer hover:border-[#4FFFA7]/30 transition-all group">
            <div className="flex-shrink-0">
              {showPlanOverlays ? (
                <CheckSquare className="w-5 h-5 text-[#4FFFA7]" />
              ) : (
                <Square className="w-5 h-5 text-[#D8E2F0]/40 group-hover:text-[#D8E2F0]/60" />
              )}
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium text-[#D8E2F0]">Show Plan Overlays</div>
              <div className="text-xs text-[#D8E2F0]/50 mt-0.5">Display plan overlay visualization</div>
            </div>
            <input
              type="checkbox"
              checked={showPlanOverlays}
              onChange={(e) => onTogglePlanOverlays(e.target.checked)}
              className="sr-only"
            />
          </label>
        </div>

        {/* Statistics */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-[#4FFFA7] uppercase tracking-wider">Statistics</h3>
          
          {/* Total Parcels Tile */}
          <div className="rounded-xl bg-gradient-to-br from-[#0F1F3D] to-[#0A1630] border border-[#1a2f4d] p-4">
            <div className="text-xs font-medium text-[#D8E2F0]/60 mb-1">Total Parcels</div>
            <div className="text-2xl font-bold text-[#4FFFA7]">{totalParcels || 0}</div>
          </div>

          {/* Selected Parcels Tile */}
          <div className="rounded-xl bg-gradient-to-br from-[#0F1F3D] to-[#0A1630] border border-[#1a2f4d] p-4">
            <div className="text-xs font-medium text-[#D8E2F0]/60 mb-1">Selected</div>
            <div className="text-2xl font-bold text-[#3BC7F5]">{selectedParcels.length}</div>
          </div>
        </div>

        {/* Selected Parcel IDs */}
        {selectedParcels.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-[#4FFFA7] uppercase tracking-wider">Selected Parcels</h3>
            <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
              {selectedParcels.map((id) => (
                <div
                  key={id}
                  className="px-4 py-3 rounded-lg border border-[#4FFFA7]/30 bg-[#4FFFA7]/10 text-[#4FFFA7] font-mono text-sm font-medium hover:bg-[#4FFFA7]/20 transition-colors"
                >
                  {id}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

