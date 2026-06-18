import { Download } from 'lucide-react';
import { LandUseZone } from '../../types';
import { exportGeoJSON } from '../../utils/geojson';
import { toast } from 'sonner';

interface StatusBarProps {
  selectedRegion: string;
  zones: LandUseZone[];
}

export function StatusBar({
  selectedRegion,
  zones,
}: StatusBarProps) {
  const handleExport = () => {
    exportGeoJSON(zones, selectedRegion);
    toast.success('GeoJSON exported successfully!');
  };

  return (
    <div className="bg-[#0F1F3D] border-t border-[#1a2f4d] px-6 py-3 flex items-center justify-end gap-3">
      <button
        onClick={handleExport}
        className="flex items-center gap-2 px-4 py-2 bg-[#1a2f4d] hover:bg-[#3BC7F5]/20 hover:border-[#3BC7F5] border border-[#1a2f4d] rounded-xl text-[#D8E2F0] text-sm transition-all duration-300"
      >
        <Download className="w-4 h-4" />
        <span>Export GeoJSON</span>
      </button>
    </div>
  );
}
