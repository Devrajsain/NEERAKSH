import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { CurrentDashboardData, DashboardEntityState } from './types';
import { getShipImage } from './shipImages';
import './forecastTooltip.css';

// ── Haversine distance in km ─────────────────────────────────────────
function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── Compass bearing ────────────────────────────────────────────────────
function bearingDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
  const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
    Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

// ── Convert degrees to cardinal ────────────────────────────────────────
function toCardinal(deg: number): string {
  const cards = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return cards[Math.round(deg / 22.5) % 16];
}

// ── Format lat/lon with hemisphere ─────────────────────────────────────
function fmtLat(v: number): string { return `${Math.abs(v).toFixed(4)}° ${v >= 0 ? 'N' : 'S'}`; }
function fmtLon(v: number): string { return `${Math.abs(v).toFixed(4)}° ${v >= 0 ? 'E' : 'W'}`; }

interface MapCanvasProps {
  currentData: CurrentDashboardData | null;
  layers: { spill: boolean; drift: boolean; ais: boolean; satTile: string };
  selectedEntity: DashboardEntityState;
  onSelectEntity: (entity: DashboardEntityState) => void;
  isLoading: boolean;
}

export const MapCanvas: React.FC<MapCanvasProps> = ({
  currentData,
  layers,
  selectedEntity,
  onSelectEntity,
  isLoading
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const mapLayersGroup = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    return () => {
      if (leafletMap.current) {
        try {
          leafletMap.current.remove();
        } catch (e) { }
        leafletMap.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;
    const observer = new ResizeObserver(() => {
      if (leafletMap.current) {
        leafletMap.current.invalidateSize();
      }
    });
    observer.observe(mapRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!mapRef.current || !currentData) return;

    if (leafletMap.current) {
      try {
        const container = leafletMap.current.getContainer();
        if (!container || container !== mapRef.current || !document.body.contains(container)) {
          leafletMap.current.remove();
          leafletMap.current = null;
        }
      } catch (e) {
        leafletMap.current = null;
      }
    }

    if (!leafletMap.current) {
      if ((mapRef.current as any)._leaflet_id) {
        delete (mapRef.current as any)._leaflet_id;
      }
      try {
        console.log(`[MapCanvas] Initializing map. Container size: ${mapRef.current.clientWidth}x${mapRef.current.clientHeight}`);
        leafletMap.current = L.map(mapRef.current, {
          center: currentData.center,
          zoom: currentData.zoom,
          zoomControl: false,
          attributionControl: false
        });

        // Use standard tile layer
        const baseTileLayer = L.tileLayer(
          'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
          }
        );
        baseTileLayer.on('tileerror', (event: any) => {
          console.warn('[MapCanvas] Tile load error:', event.error, event.tile);
        });
        baseTileLayer.addTo(leafletMap.current);
        L.control.zoom({ position: 'bottomright' }).addTo(leafletMap.current);
        mapLayersGroup.current = L.layerGroup().addTo(leafletMap.current);

        // Deselect when clicking empty map area
        leafletMap.current.on('click', () => {
          onSelectEntity({ type: null, id: null });
        });
      } catch (err) {
        console.error("Leaflet map initialization error:", err);
      }
    } else {
      leafletMap.current.setView(currentData.center, currentData.zoom);
    }

    if (mapLayersGroup.current) {
      mapLayersGroup.current.clearLayers();

      const { feature2Data } = currentData;

      const isMuted = (type: string, id: string | null = null) => {
        if (!selectedEntity.type) return false;
        if (selectedEntity.type === type && selectedEntity.id === id) return false;
        if (selectedEntity.type === type && !id && !selectedEntity.id) return false;
        return true;
      };

      // 1. Spill Polygon Layer
      if (layers.spill && currentData.spillPolygon.length > 0) {
        const muted = isMuted('spill');
        const polygon = L.polygon(currentData.spillPolygon, {
          color: selectedEntity.type === 'spill' ? '#FF0000' : '#DC2626',
          weight: selectedEntity.type === 'spill' ? 4 : 2,
          fillColor: '#EF4444',
          fillOpacity: muted ? 0.15 : (selectedEntity.type === 'spill' ? 0.6 : 0.45),
          dashArray: '4, 4'
        });

        polygon.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectEntity({ type: 'spill', id: null });
        });

        mapLayersGroup.current.addLayer(polygon);
      }

      // 2. Drift Trajectory Path Layer
      if (layers.drift && currentData.driftPath.length > 0) {
        const latLngs = currentData.driftPath.map((p: any) => [p.lat, p.lng]);
        const polyline = L.polyline(latLngs, {
          color: '#1A3C6E',
          weight: 3,
          dashArray: '6, 6',
          opacity: selectedEntity.type ? 0.3 : 1
        });
        mapLayersGroup.current.addLayer(polyline);

        currentData.driftPath.forEach((pt: any) => {
          const isOrigin = pt.label?.includes('origin') || pt.label?.includes('Origin');
          const isOriginSelected = selectedEntity.type === 'origin';

          if (!isOrigin) {
            const marker = L.circleMarker([pt.lat, pt.lng], {
              radius: 4,
              color: '#1A3C6E',
              fillColor: '#FFFFFF',
              fillOpacity: selectedEntity.type ? 0.3 : 1,
              opacity: selectedEntity.type ? 0.3 : 1,
              weight: 2
            });
            marker.bindTooltip(pt.text, { permanent: true, direction: 'top', className: 'bg-white border border-gov-border px-1 text-[10px] text-gov-text font-mono shadow-xs' });
            mapLayersGroup.current?.addLayer(marker);
          } else {
            // Render origin point from drift path
            const marker = L.circleMarker([pt.lat, pt.lng], {
              radius: isOriginSelected ? 11 : 7,
              color: isOriginSelected ? '#FF0000' : '#B91C1C',
              fillColor: '#EF4444',
              fillOpacity: selectedEntity.type && !isOriginSelected ? 0.3 : 1,
              opacity: selectedEntity.type && !isOriginSelected ? 0.3 : 1,
              weight: isOriginSelected ? 3 : 2,
              className: isOriginSelected ? 'origin-glow' : ''
            });
            marker.bindTooltip(pt.text, { permanent: true, direction: 'top', className: 'bg-white border border-gov-border px-1 text-[10px] text-gov-text font-mono shadow-xs' });

            marker.on('click', (e) => {
              L.DomEvent.stopPropagation(e);
              onSelectEntity({ type: 'origin', id: null });
            });

            mapLayersGroup.current?.addLayer(marker);
          }
        });
      }

      // 3. Feature 2 GeoJSON & Forecast Overlay (Origin)
      if (layers.drift && feature2Data?.origin_latitude && feature2Data?.origin_longitude) {
        const origLat = feature2Data.origin_latitude;
        const origLon = feature2Data.origin_longitude;
        const uncertaintyMeters = (feature2Data.origin_uncertainty_radius_km || 2.5) * 1000;
        const muted = isMuted('origin');

        // Origin uncertainty radius circle
        const origCircle = L.circle([origLat, origLon], {
          radius: uncertaintyMeters,
          color: '#B91C1C',
          fillColor: '#F87171',
          fillOpacity: muted ? 0.05 : 0.2,
          opacity: muted ? 0.3 : 1,
          weight: 1.5,
          dashArray: '4, 4'
        });
        origCircle.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectEntity({ type: 'origin', id: null });
        });
        mapLayersGroup.current?.addLayer(origCircle);

        // Origin point marker
        const isOriginSelected = selectedEntity.type === 'origin';
        const origMarker = L.circleMarker([origLat, origLon], {
          radius: isOriginSelected ? 12 : 8,
          color: isOriginSelected ? '#FF0000' : '#7F1D1D',
          fillColor: '#EF4444',
          fillOpacity: muted ? 0.4 : 1,
          opacity: muted ? 0.4 : 1,
          weight: isOriginSelected ? 3 : 2,
          className: isOriginSelected ? 'origin-glow' : ''
        });

        origMarker.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectEntity({ type: 'origin', id: null });
        });

        mapLayersGroup.current?.addLayer(origMarker);
      }

      // Feature 2 Forecast Horizons (+6h, +12h, +24h, +48h)
      if (layers.drift && feature2Data?.forecast_json) {
        const fcHorizons = ['6h', '12h', '24h', '48h'];
        const forecastLatLngs: [number, number][] = [];
        forecastLatLngs.push(currentData.center);

        fcHorizons.forEach(hKey => {
          const fc = feature2Data.forecast_json[hKey];
          if (fc && fc.centroid_latitude && fc.centroid_longitude) {
            forecastLatLngs.push([fc.centroid_latitude, fc.centroid_longitude]);
            const spreadMeters = (fc.spread_radius_km || 3.0) * 1000;
            const spreadCircle = L.circle([fc.centroid_latitude, fc.centroid_longitude], {
              radius: spreadMeters,
              color: '#2563EB',
              fillColor: '#60A5FA',
              fillOpacity: 0.15,
              weight: 1,
              dashArray: '3, 3',
              interactive: false
            });
            mapLayersGroup.current?.addLayer(spreadCircle);

            // ── Rich hover tooltip ──────────────────────────────────────
            const origLat2 = feature2Data.origin_latitude;
            const origLon2 = feature2Data.origin_longitude;
            const distKm = haversineKm(origLat2, origLon2, fc.centroid_latitude, fc.centroid_longitude);
            const hoursNum = parseInt(hKey);
            const speedKn = hoursNum > 0 ? (distKm / 1.852 / hoursNum).toFixed(1) : '—';
            const bearDeg = Math.round(bearingDeg(origLat2, origLon2, fc.centroid_latitude, fc.centroid_longitude));
            const cardinal = toCardinal(bearDeg);
            const confidence = fc.confidence_pct ?? Math.round(90 - hoursNum * 0.9);
            const spreadKm = (fc.spread_radius_km || 3.0).toFixed(1);

            // Build tooltip HTML
            const ttHtml = `
              <div class="fc-tooltip-card" id="fctt-${hKey}">
                <div class="fc-tooltip-header">
                  <span class="fc-tooltip-badge">+${hKey}</span>
                  <span class="fc-tooltip-source">Drift Forecast</span>
                </div>
                <div class="fc-tooltip-rows">
                  <span class="fc-tooltip-label">Latitude</span>
                  <span class="fc-tooltip-value">${fmtLat(fc.centroid_latitude)}</span>
                  <span class="fc-tooltip-label">Longitude</span>
                  <span class="fc-tooltip-value">${fmtLon(fc.centroid_longitude)}</span>
                  <div class="fc-tooltip-divider"></div>
                  <span class="fc-tooltip-label">Distance</span>
                  <span class="fc-tooltip-value accent">${distKm.toFixed(1)} km</span>
                  <span class="fc-tooltip-label">Drift Speed</span>
                  <span class="fc-tooltip-value">${speedKn} kn</span>
                  <span class="fc-tooltip-label">Direction</span>
                  <span class="fc-tooltip-value">${cardinal} / ${String(bearDeg).padStart(3, '0')}°</span>
                  <div class="fc-tooltip-divider"></div>
                  <span class="fc-tooltip-label">Confidence</span>
                  <span class="fc-tooltip-value accent">${confidence}%</span>
                  <span class="fc-tooltip-label">Uncertainty</span>
                  <span class="fc-tooltip-value">±${spreadKm} km</span>
                </div>
              </div>
            `;

            const fcMarker = L.circleMarker([fc.centroid_latitude, fc.centroid_longitude], {
              radius: 6,
              color: '#1D4ED8',
              fillColor: '#38BDF8',
              fillOpacity: 1,
              weight: 2
            });

            // Hover popup (rich tooltip) — no permanent label here; driftPath loop already labels this coordinate
            const popup = L.popup({
              className: 'fc-tooltip',
              closeButton: false,
              autoClose: false,
              closeOnClick: false,
              offset: [0, -10],
              autoPan: true,
              autoPanPadding: [20, 20]
            }).setContent(ttHtml);

            fcMarker.on('mouseover', function (this: L.CircleMarker) {
              if (!leafletMap.current) return;
              popup.setLatLng(this.getLatLng()).openOn(leafletMap.current);
              // Trigger fade-in after DOM is painted
              requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                  const el = document.getElementById(`fctt-${hKey}`);
                  if (el) el.classList.add('visible');
                });
              });
            });

            fcMarker.on('mouseout', function () {
              const el = document.getElementById(`fctt-${hKey}`);
              if (el) {
                el.classList.remove('visible');
                setTimeout(() => {
                  if (leafletMap.current) leafletMap.current.closePopup(popup);
                }, 180);
              } else {
                if (leafletMap.current) leafletMap.current.closePopup(popup);
              }
            });

            mapLayersGroup.current?.addLayer(fcMarker);
          }
        });

        if (forecastLatLngs.length > 1) {
          const forecastLine = L.polyline(forecastLatLngs, {
            color: '#2563EB',
            weight: 2.5,
            dashArray: '5, 5'
          });
          mapLayersGroup.current?.addLayer(forecastLine);
        }
      }

      // 4. AIS Vessel Trajectories, Gaps & Markers
      if (layers.ais && currentData.vessels.length > 0) {
        currentData.vessels.forEach((v: any, idx: number) => {
          const isBayesian = v.scoringMode === 'BAYESIAN_POSTERIOR';
          const vesselId = isBayesian && v.candidate_id ? v.candidate_id : v.mmsi;
          const isSelected = selectedEntity.type === 'vessel' && selectedEntity.id === vesselId;
          const muted = isMuted('vessel', vesselId);
          const trackColor = v.color;
          const opacity = muted ? 0.35 : 1;
          const shipImgSrc = `/ships/ship_${(idx % 5) + 1}.png`;
          const headingDeg = v.heading || 0;

          if (v.trajectoryGeojson && v.trajectoryGeojson.features) {
            v.trajectoryGeojson.features.forEach((feat: any) => {
              const featType = feat.properties?.feature_type;
              if ((featType === 'trajectory' || featType === 'ais_gap') && feat.geometry?.coordinates) {
                const latLngs = feat.geometry.coordinates.map((c: number[]) => [c[1], c[0]]);
                if (latLngs.length > 1) {
                  const isGap = featType === 'ais_gap';
                  if (isSelected) {
                    const halo = L.polyline(latLngs, {
                      color: '#FFFFFF',
                      weight: 7,
                      opacity: 0.9,
                      lineCap: 'round',
                    });
                    mapLayersGroup.current?.addLayer(halo);
                  }

                  const trackLine = L.polyline(latLngs, {
                    color: isGap ? '#DC2626' : trackColor,
                    weight: isSelected ? 4 : (isGap ? 3 : 2.5),
                    opacity: isSelected ? 1.0 : (muted ? 0.2 : (isGap ? 0.8 : 0.65)),
                    lineCap: 'round',
                    dashArray: isGap ? '6, 6' : undefined,
                  });

                  trackLine.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    onSelectEntity({ type: 'vessel', id: vesselId });
                  });
                  mapLayersGroup.current?.addLayer(trackLine);
                }
              } else if (featType === 'closest_approach' && feat.geometry?.coordinates) {
                const latLng = [feat.geometry.coordinates[1], feat.geometry.coordinates[0]] as [number, number];
                const marker = L.circleMarker(latLng, {
                  radius: 4,
                  fillColor: '#F59E0B',
                  color: '#FFFFFF',
                  weight: 1.5,
                  opacity: isSelected ? 1.0 : (muted ? 0.2 : 0.8),
                  fillOpacity: isSelected ? 1.0 : (muted ? 0.2 : 0.8),
                });
                mapLayersGroup.current?.addLayer(marker);
              }
            });
          }

          // Vessel Position Marker with real small ship image from public folder
          const sz = isSelected ? 30 : 22; // total height in px
          const imgW = isSelected ? 12 : 9;  // ship image width px
          const imgH = isSelected ? 28 : 20; // ship image height px

          const vesselIcon = L.divIcon({
            className: 'custom-vessel-icon',
            html: `
              <div style="
                position: relative;
                width: ${imgW}px;
                height: ${sz}px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                opacity: ${opacity};
                cursor: pointer;
                overflow: visible;
              ">
                <!-- Rank tag above ship -->
                ${!isBayesian ? `
                <div style="
                  position: absolute;
                  top: -8px;
                  left: 50%;
                  transform: translateX(-50%);
                  background: ${trackColor};
                  color: #FFFFFF;
                  font-size: 6.5px;
                  font-weight: 900;
                  font-family: monospace;
                  padding: 0 2px;
                  border-radius: 2px;
                  border: 0.5px solid rgba(255,255,255,0.8);
                  box-shadow: 0 1px 2px rgba(0,0,0,0.5);
                  white-space: nowrap;
                  z-index: 20;
                  pointer-events: none;
                  line-height: 9px;
                ">#${idx + 1}</div>
                ` : ''}

                <!-- Ship image, explicitly constrained to icon px -->
                <img
                  src="${shipImgSrc}"
                  alt="${v.name}"
                  width="${imgW}"
                  height="${imgH}"
                  style="
                    width: ${imgW}px;
                    height: ${imgH}px;
                    object-fit: contain;
                    display: block;
                    user-select: none;
                    pointer-events: none;
                    transform: rotate(${headingDeg}deg);
                    transform-origin: center center;
                    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.45)) ${isSelected ? 'drop-shadow(0 0 3px ' + trackColor + ')' : ''};
                  "
                />
              </div>
            `,
            iconSize: [imgW, sz],
            iconAnchor: [Math.round(imgW / 2), Math.round(sz / 2)]
          });

          const marker = L.marker([v.lat, v.lng], { icon: vesselIcon });
          marker.on('click', (e) => {
            L.DomEvent.stopPropagation(e);
            onSelectEntity({ type: 'vessel', id: vesselId });
          });

          mapLayersGroup.current?.addLayer(marker);
        });
      }

      // Auto-fit bounds logic
      const allPoints: [number, number][] = [];
      if (layers.spill && currentData.spillPolygon.length > 0) {
        allPoints.push(...currentData.spillPolygon);
      }
      if (layers.drift && currentData.driftPath.length > 0) {
        currentData.driftPath.forEach((p: any) => allPoints.push([p.lat, p.lng]));
      }
      if (layers.drift && feature2Data?.origin_latitude && feature2Data?.origin_longitude) {
        allPoints.push([feature2Data.origin_latitude, feature2Data.origin_longitude]);
      }
      if (layers.drift && feature2Data?.forecast_json) {
        ['6h', '12h', '24h', '48h'].forEach(h => {
          const fc = feature2Data.forecast_json[h];
          if (fc?.centroid_latitude && fc?.centroid_longitude) {
            allPoints.push([fc.centroid_latitude, fc.centroid_longitude]);
          }
        });
      }
      if (layers.ais && currentData.vessels.length > 0) {
        currentData.vessels.forEach(v => allPoints.push([v.lat, v.lng]));
      }

      if (allPoints.length > 0 && leafletMap.current && !selectedEntity.type) {
        try {
          const bounds = L.latLngBounds(allPoints);
          leafletMap.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
        } catch (e) { }
      }
    }

    const timer = setTimeout(() => {
      try {
        leafletMap.current?.invalidateSize();
      } catch (e) { }
    }, 150);

    return () => clearTimeout(timer);
  }, [currentData, layers, isLoading, selectedEntity]);

  return <div ref={mapRef} className="absolute inset-0 w-full h-full z-0 cursor-crosshair"></div>;
};
