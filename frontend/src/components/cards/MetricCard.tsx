import { LucideIcon } from 'lucide-react';
import { ReactNode } from 'react';

interface MetricCardProps {
  title: string;
  value: string;
  unit: string;
  icon: LucideIcon;
  trend: string;
  chart: ReactNode;
}

export function MetricCard({
  title,
  value,
  unit,
  icon: Icon,
  trend,
  chart,
}: MetricCardProps) {
  const isPositive = trend.startsWith('+');

  return (
    <div className="bg-[#0F1F3D] rounded-2xl p-4 border border-[#1a2f4d] hover:border-[#3BC7F5]/30 transition-all duration-300 hover:shadow-[0_0_20px_rgba(59,199,245,0.1)]">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#4FFFA7]/10 flex items-center justify-center">
            <Icon className="w-4 h-4 text-[#4FFFA7]" />
          </div>
          <span className="text-[#D8E2F0]/70 text-sm">{title}</span>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded-full ${
            isPositive
              ? 'bg-[#4FFFA7]/10 text-[#4FFFA7]'
              : 'bg-[#3BC7F5]/10 text-[#3BC7F5]'
          }`}
        >
          {trend}
        </span>
      </div>

      <div className="mb-3">
        <span className="text-[#4FFFA7] text-3xl">{value}</span>
        <span className="text-[#D8E2F0]/50 text-sm ml-2">{unit}</span>
      </div>

      <div className="h-[60px]">{chart}</div>
    </div>
  );
}
