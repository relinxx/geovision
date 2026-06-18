import { MetricCard } from '../cards/MetricCard';
import { Users, Building2, Trees, TrendingUp } from 'lucide-react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  ResponsiveContainer,
} from 'recharts';
import { useEffect, useState } from 'react';
import { Metrics } from '../../types';
import { APP_CONFIG } from '../../config/constants';

interface MetricsPanelProps {
  metrics: Metrics;
  simulationTime: number;
}

export function MetricsPanel({ metrics, simulationTime }: MetricsPanelProps) {
  const [populationHistory, setPopulationHistory] = useState([
    { name: 'T-4', value: 4200 },
    { name: 'T-3', value: 4800 },
    { name: 'T-2', value: 5200 },
    { name: 'T-1', value: 5600 },
    { name: 'Now', value: metrics.population },
  ]);

  const [zoningHistory, setZoningHistory] = useState([
    { name: 'T-4', value: 65 },
    { name: 'T-3', value: 72 },
    { name: 'T-2', value: 78 },
    { name: 'T-1', value: 85 },
    { name: 'Now', value: metrics.zoning },
  ]);

  useEffect(() => {
    setPopulationHistory((prev) => [
      ...prev.slice(1),
      { name: 'Now', value: metrics.population },
    ]);

    setZoningHistory((prev) => [
      ...prev.slice(1),
      { name: 'Now', value: metrics.zoning },
    ]);
  }, [simulationTime]);

  const environmentalData = Array.from({ length: 5 }, (_, i) => ({
    name: `Z${i + 1}`,
    value: Math.max(1, metrics.environmental + Math.random() * 2 - 1),
  }));

  const greenAreaData = [
    { name: 'Green', value: metrics.greenArea },
    { name: 'Built', value: 100 - metrics.greenArea },
  ];

  return (
    <div className="w-80 bg-[#0B1E39] border-r border-[#1a2f4d] overflow-y-auto p-6 space-y-4 custom-scrollbar">
      <div className="mb-6">
        <h2 className="text-[#4FFFA7] mb-1">
          {APP_CONFIG.name}
          <br />
          <span className="font-bold">{APP_CONFIG.description}</span>
        </h2>
        <p className="text-[#D8E2F0]/60 text-sm">Real-time Analytics Dashboard</p>
        {simulationTime > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-[#3BC7F5]" />
            <span className="text-xs text-[#3BC7F5]">
              Simulation time: {simulationTime}s
            </span>
          </div>
        )}
      </div>

      <MetricCard
        title="Zoning Compliance"
        value={metrics.zoning.toString()}
        unit="%"
        icon={Building2}
        trend="+8%"
        chart={
          <ResponsiveContainer width="100%" height={60}>
            <LineChart data={zoningHistory}>
              <Line
                type="monotone"
                dataKey="value"
                stroke="#3BC7F5"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        }
      />

      <MetricCard
        title="Environmental Constraints"
        value={metrics.environmental.toFixed(1)}
        unit="risk index"
        icon={Users}
        trend="-2%"
        chart={
          <ResponsiveContainer width="100%" height={60}>
            <BarChart data={environmentalData}>
              <Bar dataKey="value" fill="#3BC7F5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        }
      />

      <MetricCard
        title="Green Area Ratio"
        value={metrics.greenArea.toString()}
        unit="%"
        icon={Trees}
        trend="+15%"
        chart={
          <ResponsiveContainer width="100%" height={60}>
            <PieChart>
              <Pie data={greenAreaData} dataKey="value" cx="50%" cy="50%" outerRadius={30}>
                {greenAreaData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={index === 0 ? '#4FFFA7' : '#1a2f4d'}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        }
      />

      <div className="bg-[#0F1F3D] rounded-2xl p-4 border border-[#1a2f4d]">
        <h3 className="text-sm text-[#D8E2F0] mb-3">Activity Feed</h3>
        <div className="space-y-2">
          {simulationTime > 0 && (
            <div className="text-xs text-[#4FFFA7] animate-pulse">
              ● Simulation running...
            </div>
          )}
          <div className="text-xs text-[#D8E2F0]/60">
            ✓ Zoning compliance updated
          </div>
          <div className="text-xs text-[#D8E2F0]/60">
            ✓ Environmental data synced
          </div>
        </div>
      </div>
    </div>
  );
}
