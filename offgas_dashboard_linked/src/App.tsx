import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  AlertTriangle,
  CheckCircle2,
  Activity,
  Map as MapIcon,
  LayoutGrid,
  Fan,
  Wind,
  ShieldCheck,
  Zap,
  Power,
  RefreshCw,
  Database,
  ChevronDown,
  Wifi,
  WifiOff,
  Send,
} from 'lucide-react';
import { Gauge } from './components/Gauge';
import { SensorChart } from './components/SensorChart';
import { SensorMap } from './components/Map';

type ManualMode = 'AUTO' | 'ON' | 'OFF';

interface DisplaySensor {
  garage_id: string;
  value: number;
  threshold: number;
  status: 'SAFE' | 'WARNING' | 'CRITICAL';
  source: 'LIVE' | 'DATASET';
  fan_active: boolean;
}

interface HistoryPoint {
  time: string;
  [key: string]: string | number;
}

interface DashboardState {
  mqtt_connected: boolean;
  broker_url: string;
  telemetry: {
    garage_id: string;
    gas: number;
    threshold: number;
    timestamp: string;
    fan_state: boolean;
  } | null;
  latest_auto_command: {
    mode: 'STD';
    anomaly: boolean;
    predicted_crossing: boolean;
    predicted_gas?: number;
  } | null;
  latest_manual_command: 'FAN_ON' | 'FAN_OFF' | 'AUTO' | 'AUTO_MODE' | null;
  latest_alert: {
    event?: string;
    command?: string;
    timestamp?: string;
  } | null;
  others_mean: number;
  threshold: number;
  anomaly_factor: number;
  mode: ManualMode;
  display_sensors: DisplaySensor[];
  updated_at: string;
  dataset_name: string | null;
  available_datasets: string[];
  selected_dataset: number;
  shutdown_active: boolean;
}

const MAX_POINTS = 20;

export default function App() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [sendingMode, setSendingMode] = useState<ManualMode | null>(null);
  const [changingDataset, setChangingDataset] = useState(false);
  const [changingEmergency, setChangingEmergency] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchState = async () => {
    try {
      const response = await fetch('/api/state');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const nextState: DashboardState = await response.json();
      setState(nextState);
      setError(null);

      const timeLabel = nextState.telemetry?.timestamp
        ? new Date(nextState.telemetry.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })
        : new Date(nextState.updated_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });

      const point: HistoryPoint = {
        time: timeLabel,
        threshold: Math.round(nextState.threshold),
        avg: nextState.shutdown_active ? 0 : Math.round(nextState.others_mean),
        stamp: nextState.updated_at,
      };

      nextState.display_sensors.forEach((sensor) => {
        point[sensor.garage_id] = nextState.shutdown_active ? 0 : sensor.value;
      });

      setHistory((prev) => {
        const alreadyLast = prev.length > 0 && prev[prev.length - 1].stamp === point.stamp;
        if (alreadyLast) return prev;
        return [...prev, point].slice(-MAX_POINTS);
      });
    } catch (err) {
      setState((prev) => (prev ? { ...prev, mqtt_connected: false } : prev));
      setError(null);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  const sendMode = async (mode: ManualMode) => {
    try {
      setSendingMode(mode);
      const response = await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }

      setState(payload as DashboardState);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Command publish failed');
      console.error(err);
    } finally {
      setSendingMode(null);
    }
  };

  const changeDataset = async (index: number) => {
    try {
      setChangingDataset(true);
      const response = await fetch('/api/dataset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }

      setState(payload as DashboardState);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dataset switch failed');
      console.error(err);
    } finally {
      setChangingDataset(false);
    }
  };

  const toggleEmergency = async () => {
    if (!state) return;

    try {
      setChangingEmergency(true);
      const response = await fetch('/api/emergency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !state.shutdown_active }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }

      setState(payload as DashboardState);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Emergency shutoff failed');
      console.error(err);
    } finally {
      setChangingEmergency(false);
    }
  };

  const sensors = state?.display_sensors ?? [];
  const currentThreshold = state?.threshold ?? 0;
  const othersMean = state?.others_mean ?? 0;
  const currentMode = state?.mode ?? 'AUTO';
  const g1 = sensors.find((sensor) => sensor.garage_id === 'G1');
  const autoDecision = state?.latest_auto_command;
  const isShutoff = Boolean(state?.shutdown_active);
  const othersMeanDisplay = isShutoff ? 0 : Math.round(othersMean);

  const status = useMemo<'SAFE' | 'WARNING' | 'CRITICAL'>(() => {
    if (isShutoff) return 'CRITICAL';
    if (autoDecision?.anomaly || (g1?.value ?? 0) >= currentThreshold) return 'CRITICAL';
    if (autoDecision?.predicted_crossing || (g1?.value ?? 0) >= currentThreshold * 0.85) return 'WARNING';
    return 'SAFE';
  }, [autoDecision, currentThreshold, g1?.value, isShutoff]);

  const banner = useMemo(() => {
    if (isShutoff) {
      return {
        title: 'EMERGENCY PROTOCOL ACTIVATED',
        text: 'MQTT bridge communications suspended. Manual resume is required to reconnect the dashboard.',
      };
    }

    if (status === 'CRITICAL') {
      return {
        title: 'CRITICAL: OFFGASSING DETECTED',
        text: 'G1 is above the live safety threshold and requires immediate ventilation.',
      };
    }

    if (status === 'WARNING') {
      return {
        title: 'PREDICTIVE WARNING',
        text: 'Node-RED indicates a likely threshold crossing for G1. Preventive ventilation may be required.',
      };
    }

    return {
      title: 'SYSTEM STATUS: NOMINAL',
      text: 'G1 remains below the current safety threshold relative to the selected comparison dataset.',
    };
  }, [isShutoff, status]);

  const activeFanIds = sensors.filter((sensor) => sensor.fan_active).map((sensor) => sensor.garage_id);
  const fansActive = !isShutoff && activeFanIds.length > 0;
  const activationReason = isShutoff
    ? 'Bridge communication suspended'
    : currentMode === 'ON'
    ? 'Manual Override (All ON)'
    : currentMode === 'OFF'
    ? 'Manual Override (All OFF)'
    : activeFanIds.length > 0
    ? 'Localized Response'
    : 'Standby';
  const lastUpdatedLabel = state?.telemetry?.timestamp
    ? new Date(state.telemetry.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '--:--:--';
  const chartIds = sensors.map((sensor) => sensor.garage_id);

  return (
    <div className={`min-h-screen p-4 md:p-8 space-y-6 transition-colors duration-500 ${isShutoff ? 'bg-[#0a0a0a]' : 'bg-[#E4E3E0]'}`}>
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-2">
        <div className="flex-shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-500 ${
                isShutoff
                  ? 'bg-red-600 shadow-[0_0_20px_rgba(220,38,38,0.4)]'
                  : status === 'CRITICAL'
                  ? 'bg-red-500 animate-pulse'
                  : status === 'WARNING'
                  ? 'bg-amber-500'
                  : 'bg-[#141414]'
              }`}
            >
              <Activity className="text-white w-6 h-6" />
            </div>
            <h1 className={`text-5xl font-black tracking-tighter uppercase transition-colors duration-500 ${isShutoff ? 'text-red-600' : 'text-[#141414]'}`}>
              OffGas
            </h1>
          </div>
          <p className={`text-[10px] opacity-40 font-bold uppercase tracking-[0.4em] ${isShutoff ? 'text-white/70' : 'text-[#141414]'}`}>
            EV Garage Safety Monitor v1.2
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 md:gap-8">
          <div className="flex flex-col gap-1.5">
            <span className={`text-[9px] font-black uppercase tracking-[0.2em] opacity-30 ml-1 ${isShutoff ? 'text-white' : 'text-black'}`}>
              System Control
            </span>
            <div className={`flex items-center p-1 rounded-2xl border transition-colors ${isShutoff ? 'bg-white/5 border-white/10' : 'bg-white/50 border-black/5 backdrop-blur-md'}`}>
              {(['OFF', 'AUTO', 'ON'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => sendMode(mode)}
                  disabled={sendingMode !== null || isShutoff}
                  className={`px-5 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all relative ${
                    currentMode === mode ? (isShutoff ? 'text-white' : 'text-black') : 'opacity-20 hover:opacity-40'
                  } ${sendingMode !== null || isShutoff ? 'cursor-not-allowed' : ''}`}
                >
                  {currentMode === mode && (
                    <motion.div
                      layoutId="activeMode"
                      className={`absolute inset-0 rounded-xl -z-10 ${isShutoff ? 'bg-white/20' : 'bg-black/10'}`}
                      transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                  {sendingMode === mode ? '...' : mode}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={`text-[9px] font-black uppercase tracking-[0.2em] opacity-30 ml-1 ${isShutoff ? 'text-white' : 'text-black'}`}>
              Safety Protocol
            </span>
            <button
              onClick={toggleEmergency}
              disabled={changingEmergency}
              className={`px-6 py-3 rounded-2xl font-black uppercase tracking-widest text-[10px] flex items-center gap-3 transition-all active:scale-95 shadow-xl ${
                isShutoff ? 'bg-emerald-500 text-white hover:bg-emerald-600' : 'bg-red-600 text-white hover:bg-red-700'
              } ${changingEmergency ? 'opacity-70 cursor-wait' : ''}`}
            >
              {isShutoff ? <RefreshCw size={16} className={changingEmergency ? 'animate-spin' : ''} /> : <Power size={16} />}
              {changingEmergency ? 'Applying...' : isShutoff ? 'Resume System' : 'Emergency Shutoff'}
            </button>
          </div>

          <div className={`text-right ${isShutoff ? 'text-white' : ''}`}>
            <p className="text-[9px] font-black opacity-30 uppercase tracking-[0.2em]">Bridge Link</p>
            <div className="flex items-center justify-end gap-2">
              {state?.mqtt_connected ? <Wifi size={14} className="text-emerald-500" /> : <WifiOff size={14} className="text-red-500" />}
              <span className="text-sm font-mono font-black">{state?.mqtt_connected ? 'MQTT CONNECTED' : 'MQTT DISCONNECTED'}</span>
            </div>
          </div>

          <div className={`text-right hidden xl:block ${isShutoff ? 'text-white' : ''}`}>
            <p className="text-[9px] font-black opacity-30 uppercase tracking-[0.2em]">Last Updated</p>
            <p className="text-sm font-mono font-black">{lastUpdatedLabel}</p>
          </div>
        </div>
      </header>

      <div className={`p-4 flex items-center justify-between overflow-hidden relative rounded-2xl border transition-colors ${isShutoff ? 'bg-white/5 border-white/10 text-white' : 'bg-white/50 border-black/5 backdrop-blur-md'}`}>
        <div className="flex items-center gap-4 z-10">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${fansActive ? 'bg-blue-500 text-white shadow-[0_0_20px_rgba(59,130,246,0.5)]' : isShutoff ? 'bg-white/10 text-white/30' : 'bg-black/5 text-black/30'}`}>
            <motion.div
              animate={fansActive ? { rotate: 360 } : { rotate: 0 }}
              transition={fansActive ? { repeat: Infinity, duration: 1, ease: 'linear' } : { duration: 0.5 }}
            >
              <Fan size={24} />
            </motion.div>
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-widest opacity-50">Ventilation System</h3>
            <div className="flex flex-col">
              <div className="flex items-center gap-3">
                <span className={`text-lg font-bold tracking-tight ${fansActive ? 'text-blue-600' : isShutoff ? 'text-white/60' : 'opacity-30'}`}>
                  {isShutoff ? 'SYSTEM ISOLATED' : fansActive ? 'LOCALIZED EXHAUST ACTIVE' : 'STANDBY MODE'}
                </span>
                {fansActive && (
                  <motion.div animate={{ x: [0, 10, 0], opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1.5 }}>
                    <Wind size={18} className="text-blue-400" />
                  </motion.div>
                )}
              </div>
              <AnimatePresence>
                {(isShutoff || fansActive) && (
                  <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="flex items-center gap-2 mt-1.5 flex-wrap">
                    {isShutoff ? (
                      <ShieldCheck size={12} className="text-red-400/70" />
                    ) : currentMode === 'ON' ? (
                      <Activity size={12} className="text-blue-500/60" />
                    ) : status === 'CRITICAL' ? (
                      <ShieldCheck size={12} className="text-red-500/60" />
                    ) : status === 'WARNING' ? (
                      <Zap size={12} className="text-amber-500/60" />
                    ) : (
                      <CheckCircle2 size={12} className="text-emerald-500/60" />
                    )}
                    <span className="text-[10px] font-bold uppercase tracking-widest text-current opacity-60">{activationReason}</span>
                    {!isShutoff && activeFanIds.length > 0 && (
                      <div className="flex gap-1">
                        {activeFanIds.map((id) => (
                          <span key={id} className="bg-blue-500 text-white text-[8px] font-black px-1.5 py-0.5 rounded-md shadow-sm">
                            {id}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="flex gap-8 z-10">
          <div className="text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest opacity-30">Fan Speed</p>
            <p className="text-sm font-mono font-bold">2800 RPM</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest opacity-30">Air Flow</p>
            <p className="text-sm font-mono font-bold">450 m³/h</p>
          </div>
        </div>

        {fansActive && (
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: '100%' }}
            transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
            className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500/5 to-transparent skew-x-12"
          />
        )}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={`${status}-${isShutoff}`}
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className={`p-6 rounded-3xl flex items-center gap-4 shadow-2xl ${
            status === 'CRITICAL' ? 'bg-red-600 text-white' : status === 'WARNING' ? 'bg-amber-500 text-white' : 'bg-emerald-500 text-white'
          }`}
        >
          {isShutoff ? (
            <Power className="w-10 h-10 animate-pulse" />
          ) : status === 'CRITICAL' ? (
            <AlertTriangle className="w-10 h-10 animate-pulse" />
          ) : status === 'WARNING' ? (
            <Send className="w-10 h-10" />
          ) : (
            <CheckCircle2 className="w-10 h-10" />
          )}
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{banner.title}</h2>
            <p className="opacity-80 text-sm font-medium">{banner.text}</p>
          </div>
        </motion.div>
      </AnimatePresence>

      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm font-semibold">
          {error}
        </div>
      )}

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <section>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <LayoutGrid size={18} className={`opacity-50 ${isShutoff ? 'text-white' : 'text-black'}`} />
                <h3 className={`text-xs font-bold uppercase tracking-[0.2em] opacity-50 ${isShutoff ? 'text-white' : 'text-black'}`}>Unit Monitoring</h3>
              </div>
              <div className="flex items-center gap-4">
                <div className={`px-4 py-2 rounded-xl border-2 transition-all shadow-lg ${isShutoff ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-500' : 'bg-white border-black/10 text-emerald-600'}`}>
                  <span className="text-[10px] font-black opacity-60 uppercase mr-3 tracking-tighter">Avg Concentration</span>
                  <span className="text-sm font-mono font-black">{othersMeanDisplay} VOC</span>
                </div>
                <div className={`px-4 py-2 rounded-xl border-2 transition-all shadow-lg ${isShutoff ? 'bg-red-950/30 border-red-500/50 text-red-500' : 'bg-white border-black/10 text-red-600'}`}>
                  <span className="text-[10px] font-black opacity-60 uppercase mr-3 tracking-tighter">Safety Threshold</span>
                  <span className="text-sm font-mono font-black">{Math.round(currentThreshold)} VOC</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-3 gap-4">
              {loading
                ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-48 rounded-2xl bg-white/60 animate-pulse" />)
                : sensors.map((sensor) => (
                    <Gauge
                      key={sensor.garage_id}
                      label={sensor.garage_id}
                      value={isShutoff ? 0 : sensor.value}
                      max={Math.max(400, Math.round(currentThreshold * 1.6))}
                      threshold={sensor.threshold}
                      isShutoff={isShutoff}
                      fanActive={sensor.fan_active}
                    />
                  ))}
            </div>
          </section>

          <section className="relative">
            <div className="flex items-center justify-between mb-4 px-2">
              <div className="flex items-center gap-2">
                <Activity size={16} className="opacity-50" />
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] opacity-50">Temporal Analysis</h3>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex flex-col items-end gap-1">
                  <span className={`text-[8px] font-black uppercase tracking-widest opacity-40 ${isShutoff ? 'text-white' : 'text-black'}`}>Dataset Source</span>
                  <div className="relative group">
                    <select
                      value={state?.selected_dataset ?? 0}
                      onChange={(e) => changeDataset(Number(e.target.value))}
                      disabled={changingDataset}
                      className={`appearance-none pl-4 pr-10 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer outline-none border-2 ${
                        isShutoff
                          ? 'bg-white/10 border-white/10 text-white hover:bg-white/20'
                          : 'bg-white border-black/5 text-black hover:border-black/20 shadow-sm'
                      } ${changingDataset ? 'opacity-70 cursor-wait' : ''}`}
                    >
                      {(state?.available_datasets ?? []).map((label, idx) => (
                        <option key={label} value={idx} className="bg-white text-black">
                          {label}
                        </option>
                      ))}
                    </select>
                    <div className={`absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none flex items-center gap-1 opacity-50 ${isShutoff ? 'text-white' : 'text-black'}`}>
                      <ChevronDown size={12} className="group-hover:translate-y-0.5 transition-transform" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <SensorChart history={history} sensorIds={chartIds} threshold={Math.round(currentThreshold)} isShutoff={isShutoff} />
          </section>
        </div>

        <div className="space-y-8">
          <section className={`p-6 space-y-6 rounded-2xl border transition-colors ${isShutoff ? 'bg-white/5 border-white/10 text-white' : 'bg-white/50 border-black/5 backdrop-blur-md'}`}>
            <div className="flex items-center gap-2 mb-2">
              <Database size={18} className="opacity-50" />
              <h3 className={`text-sm font-bold uppercase tracking-widest opacity-50 ${isShutoff ? 'text-white' : 'text-black'}`}>System Metrics</h3>
            </div>
            <div className="space-y-4">
              <div className={`flex justify-between items-end border-b pb-4 ${isShutoff ? 'border-white/10' : 'border-black/5'}`}>
                <span className="text-xs font-bold opacity-50 uppercase">Active Sensors</span>
                <span className="text-2xl font-mono font-bold">{sensors.length}</span>
              </div>
              <div className={`flex justify-between items-start border-b pb-4 ${isShutoff ? 'border-white/10' : 'border-black/5'}`}>
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-bold opacity-50 uppercase">Anomaly Factor</span>
                  <p className="text-[9px] leading-relaxed opacity-40 max-w-[180px]">
                    Multiplier used to calculate the dynamic safety threshold based on the current average concentration.
                  </p>
                </div>
                <span className="text-2xl font-mono font-bold">{state?.anomaly_factor.toFixed(1) ?? '1.5'}x</span>
              </div>
              <div className="flex justify-between items-end pb-2">
                <span className="text-xs font-bold opacity-50 uppercase">System Mode</span>
                <span className={`text-lg font-bold uppercase tracking-tighter ${currentMode === 'AUTO' ? 'text-emerald-600' : 'text-blue-600'}`}>
                  {currentMode === 'AUTO' ? 'Automatic' : currentMode === 'ON' ? 'Manual ON' : 'Manual OFF'}
                </span>
              </div>
            </div>
          </section>

          <section>
            <div className="flex items-center gap-2 mb-6">
              <MapIcon size={18} className="opacity-50" />
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] opacity-50">Spatial Context</h3>
            </div>
            <SensorMap />
          </section>
        </div>
      </main>

      <footer className={`pt-8 border-t border-black/5 flex flex-col md:flex-row justify-between items-center gap-6 text-[10px] font-bold opacity-30 uppercase tracking-[0.3em] ${isShutoff ? 'text-white' : ''}`}>
        <div className="flex flex-col items-center md:items-start gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="opacity-100">&copy; 2026 OffGas Systems</span>
            <span className="tracking-widest normal-case font-medium opacity-80">Created by: Elena Bernini, Filippo Giusti, Piergiorgio Signorino</span>
          </div>
          <div className="pt-2 border-t border-black/10 w-full">
            <p className="normal-case font-medium opacity-70">UniMORE - IoT Course (2025/2026)</p>
            <p className="normal-case font-medium opacity-70">Prof. Roberto Vezzani | Assistant: Vittorio Cuculo</p>
          </div>
        </div>
        <span className="text-right">Secured Industrial Protocol</span>
      </footer>
    </div>
  );
}
