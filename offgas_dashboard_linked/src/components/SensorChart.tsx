import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from 'recharts';

interface HistoryPoint {
  time: string;
  [key: string]: string | number;
}

interface SensorChartProps {
  history: HistoryPoint[];
  sensorIds: string[];
  threshold: number;
  isShutoff?: boolean;
}

const COLORS = ['#141414', '#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#06b6d4'];
const SHUTOFF_COLORS = ['#ef4444', '#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#06b6d4'];

export const SensorChart: React.FC<SensorChartProps> = ({ history, sensorIds, threshold, isShutoff }) => {
  const currentAvg = history.length > 0 ? (history[history.length - 1].avg as number) : 0;

  return (
    <div className={`w-full h-[400px] p-6 rounded-2xl border transition-colors ${isShutoff ? 'bg-white/5 border-white/10 text-white' : 'bg-white/50 border-black/5 backdrop-blur-md'}`}>
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h2 className="text-lg font-bold italic serif tracking-tight">Real-time Analysis</h2>
          <p className={`text-xs opacity-50 uppercase tracking-widest font-bold ${isShutoff ? 'text-white' : 'text-black'}`}>Time-series VOC concentration</p>
        </div>
        <div className="text-right">
          <span className={`text-[10px] font-bold uppercase tracking-widest opacity-50 ${isShutoff ? 'text-white' : 'text-black'}`}>Current Threshold</span>
          <p className="text-xl font-mono font-bold text-red-600">{threshold} VOC</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={history} margin={{ top: 10, right: 80, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isShutoff ? '#ffffff' : '#141414'} strokeOpacity={0.05} />
          <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 600, fill: isShutoff ? '#ffffff' : '#141414', opacity: 0.5 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 600, fill: isShutoff ? '#ffffff' : '#141414', opacity: 0.5 }} domain={[0, (dataMax: number) => Math.max(dataMax + 50, threshold + 50)]} />
          <Tooltip
            contentStyle={{
              borderRadius: '12px',
              border: 'none',
              boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
              backgroundColor: isShutoff ? '#1a1a1a' : '#ffffff',
              color: isShutoff ? '#ffffff' : '#141414',
            }}
          />
          <Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', paddingBottom: '20px' }} />
          <ReferenceLine y={threshold} stroke="#ef4444" strokeWidth={1} strokeDasharray="3 3" label={{ position: 'right', value: `THR: ${threshold}`, fill: '#ef4444', fontSize: 10, fontWeight: 900 }} opacity={0.3} />
          <ReferenceLine y={currentAvg} stroke="#10b981" strokeWidth={1} strokeDasharray="3 3" label={{ position: 'right', value: `AVG: ${currentAvg}`, fill: '#10b981', fontSize: 10, fontWeight: 900 }} opacity={0.3} />
          <Line type="stepAfter" dataKey="threshold" stroke="#ef4444" strokeWidth={3} strokeDasharray="5 5" dot={false} name="THRESHOLD" animationDuration={300} />
          <Line type="monotone" dataKey="avg" stroke="#10b981" strokeWidth={4} strokeDasharray="5 5" dot={false} name="AVG CONC" animationDuration={300} />
          {sensorIds.map((id, index) => (
            <Line key={id} type="monotone" dataKey={id} stroke={isShutoff ? SHUTOFF_COLORS[index % SHUTOFF_COLORS.length] : COLORS[index % COLORS.length]} strokeWidth={id === 'G1' ? 4 : 2} dot={false} animationDuration={300} name={id} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
