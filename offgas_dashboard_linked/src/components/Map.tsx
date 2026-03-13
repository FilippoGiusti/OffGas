import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icon in Leaflet + React
const icon = 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png';
const iconShadow = 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

export const SensorMap: React.FC = () => {
  // Center on Modena
  const position: [number, number] = [44.6471, 10.9252];

  // Sensor positions around Modena
  const sensors = [
    { id: 'G1', pos: [44.6471, 10.9252] as [number, number], label: 'Prototype G1' },
    { id: 'G2', pos: [44.6485, 10.9280] as [number, number], label: 'Unit G2' },
    { id: 'G3', pos: [44.6460, 10.9295] as [number, number], label: 'Unit G3' },
    { id: 'G4', pos: [44.6445, 10.9240] as [number, number], label: 'Unit G4' },
    { id: 'G5', pos: [44.6490, 10.9220] as [number, number], label: 'Unit G5' },
    { id: 'G6', pos: [44.6510, 10.9265] as [number, number], label: 'Unit G6' },
  ];

  return (
    <div className="w-full h-[400px] glass-panel overflow-hidden relative">
      <div className="absolute bottom-4 left-4 z-[1000] bg-white/80 backdrop-blur px-3 py-1 rounded-full border border-black/5">
        <span className="text-[10px] font-bold uppercase tracking-widest">Geospatial Overview</span>
      </div>
      <MapContainer center={position} zoom={15} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {sensors.map(s => (
          <Marker key={s.id} position={s.pos}>
            <Popup>
              <div className="font-bold">{s.id}</div>
              <div className="text-xs">{s.label}</div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};
