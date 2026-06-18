import { motion } from 'motion/react';
import { LandUseZone } from '../../types';
import { ZONE_TYPES } from '../../config/constants';

interface MapCanvasProps {
  zones: LandUseZone[];
  onZoneSelect: (zoneId: string) => void;
  isPlaying: boolean;
  enabledLayers: string[];
}

export function MapCanvas({
  zones,
  onZoneSelect,
  isPlaying,
  enabledLayers,
}: MapCanvasProps) {
  const getZoneColor = (type: LandUseZone['type']) => {
    return ZONE_TYPES[type].color;
  };

  const getZoneLabel = (type: LandUseZone['type']) => {
    return ZONE_TYPES[type].label;
  };

  return (
    <div className="absolute inset-0">
      {/* Grid Background */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `
            linear-gradient(rgba(79, 255, 167, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(79, 255, 167, 0.05) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
      >
        {/* Animated particles during simulation */}
        {isPlaying && (
          <>
            {[...Array(20)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-1 h-1 bg-[#4FFFA7] rounded-full"
                initial={{
                  x: Math.random() * window.innerWidth,
                  y: Math.random() * window.innerHeight,
                  opacity: 0,
                }}
                animate={{
                  x: Math.random() * window.innerWidth,
                  y: Math.random() * window.innerHeight,
                  opacity: [0, 1, 0],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </>
        )}
      </div>

      {/* City Zones */}
      <div className="absolute inset-0 flex items-center justify-center p-8">
        <div className="relative w-full h-full max-w-4xl max-h-4xl">
          {zones.map((zone) => (
            <motion.div
              key={zone.id}
              className={`absolute rounded-xl border-2 backdrop-blur-sm cursor-pointer transition-all duration-300 group ${
                zone.selected
                  ? 'border-white shadow-[0_0_40px_rgba(255,255,255,0.4)]'
                  : 'hover:scale-105'
              }`}
              style={{
                left: `${zone.x}px`,
                top: `${zone.y}px`,
                width: `${zone.width}px`,
                height: `${zone.height}px`,
                backgroundColor: `${getZoneColor(zone.type)}${zone.selected ? '40' : '20'}`,
                borderColor: getZoneColor(zone.type),
                boxShadow: `0 0 30px ${getZoneColor(zone.type)}30`,
              }}
              onClick={() => onZoneSelect(zone.id)}
              animate={
                isPlaying
                  ? {
                      opacity: [0.7, 1, 0.7],
                      scale: [1, 1.02, 1],
                    }
                  : {}
              }
              transition={
                isPlaying
                  ? {
                      duration: 2,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }
                  : {}
              }
            >
              <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
                <span
                  className="text-sm mb-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ color: getZoneColor(zone.type) }}
                >
                  {getZoneLabel(zone.type)}
                </span>
                {zone.population && (
                  <span className="text-xs text-white/70 opacity-0 group-hover:opacity-100 transition-opacity">
                    Pop: {zone.population}
                  </span>
                )}
                <span className="text-xs text-white/70 opacity-0 group-hover:opacity-100 transition-opacity">
                  Compliance: {zone.compliance}%
                </span>
              </div>

              {/* Compliance indicator */}
              <div className="absolute bottom-2 left-2 right-2 h-1 bg-white/20 rounded-full overflow-hidden">
                <motion.div
                  className="h-full"
                  style={{ backgroundColor: getZoneColor(zone.type) }}
                  initial={{ width: 0 }}
                  animate={{ width: `${zone.compliance}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </motion.div>
          ))}

          {/* Layer Overlays */}
          {enabledLayers.includes('flood') && (
            <motion.div
              className="absolute top-20 right-20 w-40 h-40 bg-blue-500/10 rounded-full border-2 border-blue-400/30"
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xs text-blue-400">Flood Risk</span>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
