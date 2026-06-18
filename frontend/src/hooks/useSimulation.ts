// Custom hook for simulation logic
import { useState, useEffect } from 'react';
import { Metrics, LandUseZone, SimulationSpeed } from '../types';
import { updateMetrics, updateZoneCompliance } from '../utils/simulation';
import { SIMULATION_SPEEDS } from '../config/constants';

export function useSimulation(
  initialMetrics: Metrics,
  initialZones: LandUseZone[]
) {
  const [metrics, setMetrics] = useState<Metrics>(initialMetrics);
  const [zones, setZones] = useState<LandUseZone[]>(initialZones);
  const [isPlaying, setIsPlaying] = useState(false);
  const [simulationSpeed, setSimulationSpeed] =
    useState<SimulationSpeed>('medium');
  const [simulationTime, setSimulationTime] = useState(0);

  useEffect(() => {
    if (!isPlaying) return;

    const speedMultiplier = SIMULATION_SPEEDS[simulationSpeed];

    const interval = setInterval(() => {
      setSimulationTime((prev) => prev + 1);
      setMetrics((prev) => updateMetrics(prev));
      setZones((prev) => updateZoneCompliance(prev));
    }, speedMultiplier);

    return () => clearInterval(interval);
  }, [isPlaying, simulationSpeed]);

  const resetSimulation = () => {
    setIsPlaying(false);
    setSimulationTime(0);
    setMetrics(initialMetrics);
    setZones(initialZones);
  };

  return {
    metrics,
    zones,
    isPlaying,
    simulationSpeed,
    simulationTime,
    setMetrics,
    setZones,
    setIsPlaying,
    setSimulationSpeed,
    resetSimulation,
  };
}
