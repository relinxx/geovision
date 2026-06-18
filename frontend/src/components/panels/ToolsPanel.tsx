import { Leaf, Building, Users, Layers, Droplet, Mountain, Shield, Target } from 'lucide-react';
import { CONSTRAINT_LAYERS, AI_AGENTS } from '../../config/constants';

interface ToolsPanelProps {
  selectedAgent: string | null;
  setSelectedAgent: (agent: string | null) => void;
  enabledLayers: string[];
  toggleLayer: (layerId: string) => void;
}

export function ToolsPanel({
  selectedAgent,
  setSelectedAgent,
  enabledLayers,
  toggleLayer,
}: ToolsPanelProps) {
  const layerIcons: Record<string, typeof Droplet> = {
    flood: Droplet,
    soil: Mountain,
    zoning: Shield,
    population: Target,
  };

  const agentIcons: Record<string, typeof Leaf> = {
    environmental: Leaf,
    zoning: Building,
    population: Users,
  };

  return (
    <div className="w-80 bg-[#0B1E39] border-l border-[#1a2f4d] overflow-y-auto p-6 space-y-6 custom-scrollbar">
      {/* Constraint Layers Section */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Layers className="w-5 h-5 text-[#4FFFA7]" />
          <h3 className="text-[#D8E2F0]">Constraint Layers</h3>
        </div>
        <div className="space-y-2">
          {CONSTRAINT_LAYERS.map((layer) => {
            const Icon = layerIcons[layer.id];
            const isEnabled = enabledLayers.includes(layer.id);

            return (
              <label
                key={layer.id}
                className={`flex items-center gap-3 p-3 bg-[#0F1F3D] rounded-xl border cursor-pointer transition-all duration-300 ${
                  isEnabled
                    ? 'border-[#4FFFA7]/50 shadow-[0_0_15px_rgba(79,255,167,0.1)]'
                    : 'border-[#1a2f4d] hover:border-[#4FFFA7]/30'
                }`}
              >
                <input
                  type="checkbox"
                  checked={isEnabled}
                  onChange={() => toggleLayer(layer.id)}
                  className="w-4 h-4 rounded bg-[#1a2f4d] border-[#3BC7F5] text-[#4FFFA7] focus:ring-2 focus:ring-[#4FFFA7]/50 cursor-pointer"
                />
                <Icon
                  className={`w-4 h-4 ${isEnabled ? 'text-[#4FFFA7]' : 'text-[#3BC7F5]'}`}
                />
                <span className="text-sm text-[#D8E2F0]">{layer.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* AI Agents Section */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-5 h-5 text-[#3BC7F5]" />
          <h3 className="text-[#D8E2F0]">AI Agents</h3>
        </div>
        <div className="space-y-3">
          {AI_AGENTS.map((agent) => {
            const Icon = agentIcons[agent.id];
            const isSelected = selectedAgent === agent.id;

            return (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(isSelected ? null : agent.id)}
                className={`w-full p-4 bg-[#0F1F3D] rounded-xl border transition-all duration-300 text-left ${
                  isSelected
                    ? 'border-[#4FFFA7] shadow-[0_0_20px_rgba(79,255,167,0.2)]'
                    : 'border-[#1a2f4d] hover:border-[#3BC7F5]/30 hover:shadow-[0_0_15px_rgba(59,199,245,0.1)]'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300"
                    style={{
                      backgroundColor: `${agent.color}20`,
                      boxShadow: isSelected ? `0 0 15px ${agent.color}40` : 'none',
                    }}
                  >
                    <Icon className="w-5 h-5" style={{ color: agent.color }} />
                  </div>
                  <div className="flex-1">
                    <div className="text-sm text-[#D8E2F0] mb-1">{agent.name}</div>
                    <div className="text-xs text-[#D8E2F0]/60">
                      {agent.description}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Analysis Views Section */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Layers className="w-5 h-5 text-[#FFB86C]" />
          <h3 className="text-[#D8E2F0]">Analysis Views</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { name: 'Heatmap', color: 'from-red-500/20 to-orange-500/20' },
            { name: 'Density', color: 'from-[#4FFFA7]/20 to-[#3BC7F5]/20' },
            { name: 'Zoning', color: 'from-purple-500/20 to-pink-500/20' },
            { name: 'Risk', color: 'from-yellow-500/20 to-red-500/20' },
          ].map((preview) => (
            <button
              key={preview.name}
              className="relative aspect-square bg-[#0F1F3D] rounded-xl border border-[#1a2f4d] hover:border-[#3BC7F5]/30 cursor-pointer overflow-hidden group transition-all duration-300"
            >
              <div
                className={`absolute inset-0 bg-gradient-to-br ${preview.color} opacity-50`}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xs text-[#D8E2F0]/70 group-hover:text-[#D8E2F0] transition-colors">
                  {preview.name}
                </span>
              </div>
              <div className="absolute inset-0 bg-[#4FFFA7]/0 group-hover:bg-[#4FFFA7]/10 transition-all duration-300" />
            </button>
          ))}
        </div>
      </div>

      {/* Quick Metrics */}
      <div className="bg-[#0F1F3D] rounded-xl p-4 border border-[#1a2f4d]">
        <div className="text-sm text-[#D8E2F0] mb-3">Quick Metrics</div>
        <div className="space-y-3">
          {[
            { label: 'Compliance', value: 92, color: '#4FFFA7' },
            { label: 'Balance', value: 85, color: '#3BC7F5' },
            { label: 'Efficiency', value: 78, color: '#FFB86C' },
          ].map((metric) => (
            <div key={metric.label} className="flex justify-between items-center">
              <span className="text-xs text-[#D8E2F0]/60">{metric.label}</span>
              <div className="flex items-center gap-2">
                <div className="w-20 h-1.5 bg-[#1a2f4d] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${metric.value}%`,
                      backgroundColor: metric.color,
                    }}
                  />
                </div>
                <span className="text-xs" style={{ color: metric.color }}>
                  {metric.value}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Action Button */}
      <button className="w-full py-3 px-4 bg-[#0F1F3D] border border-[#1a2f4d] hover:border-[#4FFFA7]/30 hover:bg-[#4FFFA7]/10 rounded-xl text-sm text-[#D8E2F0] transition-all duration-300">
        Export Analysis
      </button>
    </div>
  );
}
