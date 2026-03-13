import React from 'react';
import { motion } from 'motion/react';
import { AlertOctagon, Fan } from 'lucide-react';

interface GaugeProps {
  value: number;
  max: number;
  threshold: number;
  label: string;
  isShutoff?: boolean;
  fanActive?: boolean;
}

export const Gauge: React.FC<GaugeProps> = ({ value, max, threshold, label, isShutoff, fanActive }) => {
  const radius = 80;
  const strokeWidth = 12;
  const normalizedValue = Math.min(Math.max(value, 0), max);
  const percentage = normalizedValue / max;
  const circumference = Math.PI * radius;
  const isDanger = value >= threshold;

  return (
    <div className={`flex flex-col items-center justify-center p-6 rounded-2xl border transition-colors ${isShutoff ? 'bg-white/5 border-white/10 text-white' : 'bg-white/50 border-black/5 backdrop-blur-md'}`}>
      <div className="relative w-48 h-32 overflow-hidden">
        <svg className="w-full h-full" viewBox="0 0 200 120">
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={isShutoff ? 'rgba(255,255,255,0.1)' : '#d1d1d1'}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          <motion.path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={isDanger ? '#ef4444' : '#10b981'}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 ${circumference}` }}
            animate={{ strokeDasharray: `${circumference * percentage} ${circumference}` }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute bottom-0 left-0 right-0 flex flex-col items-center justify-end h-full pb-2">
          <span className="text-3xl font-bold font-mono tracking-tighter">{value}</span>
          <span className="text-[10px] uppercase tracking-widest opacity-50 font-bold">VOC</span>
        </div>
      </div>
      <div className="mt-4 text-center w-full">
        <div className="flex items-center justify-center mb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider opacity-70">{label}</h3>
        </div>
        <div className="flex flex-col gap-1.5 h-16 justify-start">
          <div className={`text-[10px] font-black px-2 py-0.5 rounded-full flex items-center justify-center gap-1 ${isDanger ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'}`}>
            {isDanger && <AlertOctagon size={10} />}
            {isDanger ? 'CRITICAL' : 'SAFE'}
          </div>
          <div className="h-9 flex items-center justify-center">
            {fanActive ? (
              <div className="bg-blue-100 text-blue-600 text-[10px] font-black px-4 py-1.5 rounded-full flex items-center justify-center gap-2 shadow-sm border border-blue-200 w-full">
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                  <Fan size={18} />
                </motion.div>
                FAN ACTIVE
              </div>
            ) : (
              <div className="h-full" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
