import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';

interface LeadIntentCardProps {
  buyersCount: number;
  sellersCount: number;
}

export default function LeadIntentCard({ buyersCount = 0, sellersCount = 0 }: LeadIntentCardProps) {
  const total = buyersCount + sellersCount;
  
  // Dynamic percentage calculation with safe divide-by-zero fallback
  const buyerPercent = total > 0 ? Math.round((buyersCount / total) * 100) : 0;
  const sellerPercent = total > 0 ? 100 - buyerPercent : 0;

  // Recharts pie data array
  const pieData = [
    { name: 'BUYERS', value: buyersCount || 1, color: '#046A38' }, // Emerald Green
    { name: 'SELLERS', value: sellersCount || (buyersCount === 0 ? 1 : 0), color: '#111827' }, // Dark Navy/Slate
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between h-full min-h-[380px]">
      {/* Header */}
      <div>
        <div className="flex justify-between items-center pb-3 border-b border-slate-100">
          <h3 className="font-extrabold text-slate-900 text-lg tracking-tight">Lead Intent</h3>
          <PieChartIcon className="w-5 h-5 text-slate-900 stroke-[1.75]" />
        </div>
      </div>

      {/* Diamond / Square Donut Chart Container */}
      <div className="relative h-48 my-4 flex items-center justify-center">
        <div className="w-40 h-40 relative flex items-center justify-center">
          {/* Rotated Chart wrapper to achieve the diamond look */}
          <div className="absolute inset-0 rotate-45 transform">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={46}
                  outerRadius={62}
                  paddingAngle={2}
                  dataKey="value"
                  startAngle={90}
                  endAngle={-270}
                  stroke="none"
                  cornerRadius={4}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Center Text (Unrotated) */}
          <div className="z-10 flex flex-col items-center justify-center text-center">
            <span className="text-3xl font-black text-slate-900 tracking-tight leading-none">
              {buyerPercent}%
            </span>
            <span className="text-[11px] font-extrabold text-slate-800 tracking-wider uppercase mt-1">
              BUYERS
            </span>
          </div>
        </div>
      </div>

      {/* Legend Footer */}
      <div className="flex justify-center items-center gap-6 pt-2 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3.5 h-3.5 bg-[#046A38] rounded-xs" />
          <span className="font-bold text-slate-900 text-[11px] tracking-wide">
            BUYERS ({buyerPercent}%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3.5 h-3.5 bg-[#111827] rounded-xs" />
          <span className="font-bold text-slate-900 text-[11px] tracking-wide">
            SELLERS ({sellerPercent}%)
          </span>
        </div>
      </div>
    </div>
  );
}