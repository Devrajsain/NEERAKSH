import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import { Plus, Minus } from 'lucide-react';
import { CurrentDashboardData, DashboardEntityState } from './types';
import { getShipImage } from './shipImages';

interface MapCanvasProps {
  currentData: CurrentDashboardData | null;
  layers: { spill: boolean; drift: boolean; ais: boolean; satTile: string };
  selectedEntity: DashboardEntityState;
  onSelectEntity: (entity: DashboardEntityState) => void;
  isLoading: boolean;
  onToggleLayers?: () => void;
}

export const MapCanvas: React.FC<MapCanvasProps> = ({
  currentData,
  layers,
  selectedEntity,
  onSelectEntity,
  isLoading,
  onToggleLayers,
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const mapLayersGroup = useRef<L.LayerGroup | null>(null);

  // Dynamic Scale state
  const [scaleInfo, setScaleInfo] = useState<{ widthPx: number; maxKm: number; halfKm: number; quarterKm: number }>({
    widthPx: 160,
    maxKm: 100,
    halfKm: 50,
    quarterKm: 25,
  });

  // Base map mode (satellite vs standard)
  const [isSatellite, setIsSatellite] = useState<boolean>(true);
  const satLayerRef = useRef<L.TileLayer | null>(null);
  const placesLayerRef = useRef<L.TileLayer | null>(null);
  const streetLayerRef = useRef<L.TileLayer | null>(null);
  const initialZoomRef = useRef<number | null>(null);

  // Inject SVG filter for matte charcoal oil texture
  useEffect(() => {
    if (!document.getElementById('spill-noise')) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.style.position = 'absolute';
      svg.style.width = '0';
      svg.style.height = '0';
      svg.innerHTML = `
        <filter id="spill-noise">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" result="noise" />
          <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.35 0" in="noise" result="coloredNoise" />
          <feComposite operator="in" in="coloredNoise" in2="SourceGraphic" result="composite" />
          <feBlend mode="multiply" in="composite" in2="SourceGraphic" />
        </filter>
      `;
      document.body.appendChild(svg);
    }
  }, []);

  // Cleanup map instances on unmount
  useEffect(() => {
    return () => {
      if (leafletMap.current) {
        try { leafletMap.current.remove(); } catch (e) { }
        leafletMap.current = null;
      }
    };
  }, []);

  // Handle container resizing
  useEffect(() => {
    if (!mapRef.current) return;
    const obs = new ResizeObserver(() => {
      leafletMap.current?.invalidateSize();
    });
    obs.observe(mapRef.current);
    return () => obs.disconnect();
  }, []);

  // Calculate dynamic scale bar values
  const updateScaleBar = useCallback(() => {
    if (!leafletMap.current) return;
    const map = leafletMap.current;
    const center = map.getCenter();
    const zoom = map.getZoom();

    // Meters per pixel at current latitude
    const metersPerPixel = (156543.03392 * Math.cos((center.lat * Math.PI) / 180)) / Math.pow(2, zoom);
    const targetPx = 170;
    const rawKm = (targetPx * metersPerPixel) / 1000;

    // Pick a neat round GIS milestone
    let niceKm = 100;
    const milestones = [1, 2, 5, 10, 20, 25, 50, 100, 150, 200, 250, 500, 1000];
    for (let i = milestones.length - 1; i >= 0; i--) {
      if (rawKm >= milestones[i] * 0.75) {
        niceKm = milestones[i];
        break;
      }
    }
    const widthPx = Math.round((niceKm * 1000) / metersPerPixel);

    setScaleInfo({
      widthPx: Math.max(90, Math.min(260, widthPx)),
      maxKm: niceKm,
      halfKm: Math.round(niceKm / 2),
      quarterKm: Math.round(niceKm / 4),
    });
  }, []);

  // Dynamic zoom coordination for vessels: scale down when zooming out, capped at standard size when zooming in
  const updateVesselZoomScale = useCallback(() => {
    if (!leafletMap.current) return;
    const z = leafletMap.current.getZoom();
    const Z_REF = initialZoomRef.current ?? 11;
    let scale = 1.0;
    if (z < Z_REF) {
      // Exponential zoom scaling so ships decrease in size proportionally as distance compresses:
      // 1 level out: 0.60
      // 2 levels out: 0.36
      // 3 levels out: 0.22
      // 4+ levels out: 0.16
      const diff = Z_REF - z;
      scale = Math.max(0.16, Math.min(1.0, Math.pow(0.60, diff)));
    } else {
      // Capped at 1.0 for normal and higher zoom levels (will not blow up on zoom-in)
      scale = 1.0;
    }

    const container = leafletMap.current.getContainer();
    if (container) {
      container.style.setProperty('--vessel-scale', scale.toFixed(3));
      container.setAttribute('data-zoom-level', String(Math.floor(z)));
    }

    // Direct DOM transform styling for guaranteed, immediate synchronization
    const vesselContainers = document.querySelectorAll<HTMLElement>('.gis-vessel-marker-container');
    vesselContainers.forEach((el) => {
      el.style.transform = `scale(${scale.toFixed(3)})`;
      el.style.transformOrigin = 'center center';
    });

    // Hide vessel name pills when zoomed out (z < Z_REF) to avoid text overlap unless selected
    const namePills = document.querySelectorAll<HTMLElement>('.gis-vessel-name-pill');
    namePills.forEach((pill) => {
      if (!pill.classList.contains('is-selected')) {
        pill.style.display = z < Z_REF ? 'none' : 'flex';
      }
    });

    // Collapse wide popup cards (origin, detected spill) when zoomed out (z < Z_REF - 1)
    const popupCards = document.querySelectorAll<HTMLElement>(
      '.gis-origin-marker-wrap .gis-popup-card, .gis-det-marker-wrap .gis-popup-card'
    );
    popupCards.forEach((card) => {
      card.style.display = z < Z_REF - 1 ? 'none' : '';
    });
  }, []);

  // Main Map & Layers Setup
  useEffect(() => {
    if (!mapRef.current || !currentData) return;

    // Ensure valid map instance
    if (leafletMap.current) {
      try {
        const c = leafletMap.current.getContainer();
        if (!c || c !== mapRef.current || !document.body.contains(c)) {
          leafletMap.current.remove();
          leafletMap.current = null;
        }
      } catch (e) {
        leafletMap.current = null;
      }
    }

    if (!leafletMap.current) {
      if ((mapRef.current as any)._leaflet_id) delete (mapRef.current as any)._leaflet_id;

      const map = L.map(mapRef.current, {
        center: currentData.center,
        zoom: currentData.zoom || 9,
        zoomControl: false,
        attributionControl: false,
      });
      leafletMap.current = map;

      // ── Create Custom Leaflet Panes for Strict Cartographic Hierarchy ──
      const paneConfigs = [
        { name: 'waterSurfacePane', zIndex: 250 },
        { name: 'uncertaintyPane', zIndex: 350 },
        { name: 'spillPane', zIndex: 370 },
        { name: 'spillOutlinePane', zIndex: 390 },
        { name: 'trajectoryPane', zIndex: 410 },
        { name: 'forecastMarkerPane', zIndex: 430 },
        { name: 'vesselPane', zIndex: 450 },
        { name: 'detectionMarkerPane', zIndex: 470 },
        { name: 'labelsPane', zIndex: 500 },
      ];

      paneConfigs.forEach(({ name, zIndex }) => {
        if (!map.getPane(name)) {
          const p = map.createPane(name);
          p.style.zIndex = String(zIndex);
        }
      });

      // ── High-Resolution Satellite & GIS Labels Base Map ──
      const satLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 19, attribution: 'Tiles &copy; Esri' }
      );
      satLayerRef.current = satLayer;
      satLayer.addTo(map);

      const placesLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 19, opacity: 0.95 }
      );
      placesLayerRef.current = placesLayer;
      placesLayer.addTo(map);

      const streetLayer = L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        { maxZoom: 19, attribution: '&copy; OpenStreetMap' }
      );
      streetLayerRef.current = streetLayer;

      mapLayersGroup.current = L.layerGroup().addTo(map);

      // Deselect when clicking empty water
      map.on('click', () => onSelectEntity({ type: null, id: null }));

      map.on('move', () => {
        updateScaleBar();
      });
      map.on('zoom', () => {
        updateScaleBar();
        updateVesselZoomScale();
      });
      map.on('zoomend', () => {
        updateScaleBar();
        updateVesselZoomScale();
      });

      updateScaleBar();
      updateVesselZoomScale();
    }

    if (!mapLayersGroup.current || !leafletMap.current) return;
    mapLayersGroup.current.clearLayers();

    // ── Derive Geometry & Drift Orientation ──
    const poly = currentData.spillPolygon || [];
    let cx = currentData.center[0];
    let cy = currentData.center[1];

    if (poly.length > 0) {
      let sumX = 0, sumY = 0;
      poly.forEach((p: number[]) => { sumX += p[0]; sumY += p[1]; });
      cx = sumX / poly.length;
      cy = sumY / poly.length;
    }

    const feature2 = currentData.feature2Data;
    const origLat = feature2?.origin_latitude || cx + 0.07;
    const origLng = feature2?.origin_longitude || cy - 0.08;

    const rawTimestamp =
      currentData.spillInfo?.detection_timestamp ||
      feature2?.origin_timestamp ||
      currentData.detectionTime ||
      '2026-09-22 06:45 UTC';

    const forecast = feature2?.forecast_json || {};
    const fc6 = forecast['6h'];
    const fc12 = forecast['12h'];
    const fc24 = forecast['24h'];
    const fc48 = forecast['48h'];

    // Target point to determine drift direction vector
    const targetLat = fc12?.centroid_latitude || fc6?.centroid_latitude || (cx - 0.12);
    const targetLng = fc12?.centroid_longitude || fc6?.centroid_longitude || (cy + 0.14);

    const dLat = targetLat - origLat;
    const dLng = targetLng - origLng;
    // Calculate angle in radians: negative latitude is South, positive longitude is East
    const driftAngleRad = Math.atan2(dLat, dLng);

    // Compute dimensions derived from spill polygon bounds
    let minLat = 999, maxLat = -999, minLng = 999, maxLng = -999;
    if (poly.length > 0) {
      poly.forEach(p => {
        if (p[0] < minLat) minLat = p[0];
        if (p[0] > maxLat) maxLat = p[0];
        if (p[1] < minLng) minLng = p[1];
        if (p[1] > maxLng) maxLng = p[1];
      });
    } else {
      minLat = cx - 0.06; maxLat = cx + 0.06;
      minLng = cy - 0.08; maxLng = cy + 0.08;
    }

    const rawSpan = Math.hypot(maxLat - minLat, maxLng - minLng);
    // Realistic dimensioning
    const lenDeg = Math.max(0.18, rawSpan * 0.95);
    const widDeg = lenDeg * 0.42;

    // Centroid of slick lies slightly downstream from origin
    const slickCenterLat = origLat + dLat * 0.38;
    const slickCenterLng = origLng + dLng * 0.38;

    // ══════════════════════════════════════════════════════
    // 1. DETECTED OIL SPILL AREA — Light Transparent Red Area
    // ══════════════════════════════════════════════════════
    let spillCoords: [number, number][] = [];
    if (poly && poly.length >= 3) {
      spillCoords = poly.map((p: number[]) => [p[0], p[1]] as [number, number]);
    } else {
      // Generate an organic slick footprint centered around [cx, cy]
      const numPts = 14;
      const rx = 0.045; // ~5 km radius
      const ry = 0.024; // ~2.6 km radius
      const rot = driftAngleRad;
      for (let i = 0; i < numPts; i++) {
        const theta = (i / numPts) * 2 * Math.PI;
        const wobble = 0.85 + Math.sin(theta * 3) * 0.15 + Math.cos(theta * 2) * 0.08;
        const ex = Math.cos(theta) * rx * wobble;
        const ey = Math.sin(theta) * ry * wobble;
        const px = ex * Math.cos(rot) - ey * Math.sin(rot);
        const py = ex * Math.sin(rot) + ey * Math.cos(rot);
        spillCoords.push([cx + px, cy + py]);
      }
    }

    // Dynamic camera centering & bounds fitting accumulator
    const allBoundsPts: [number, number][] = [
      [cx, cy],
      [origLat, origLng],
    ];
    if (spillCoords.length > 0) {
      spillCoords.forEach((p) => allBoundsPts.push([p[0], p[1]]));
    }

    if (layers.spill) {
      // Render the light transparent red polygon
      const spillPolygon = L.polygon(spillCoords, {
        color: '#ef4444',
        weight: 1.5,
        opacity: 0.85,
        fillColor: '#ef4444',
        fillOpacity: 0.22, // Light transparent red area
        pane: 'spillPane',
        className: 'gis-detected-spill-polygon',
      });

      spillPolygon.on('mouseover', () => {
        spillPolygon.setStyle({ fillOpacity: 0.35, weight: 2.2 });
      });
      spillPolygon.on('mouseout', () => {
        spillPolygon.setStyle({ fillOpacity: 0.22, weight: 1.5 });
      });
      spillPolygon.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        onSelectEntity({ type: 'spill', id: null });
      });
      mapLayersGroup.current.addLayer(spillPolygon);

      // Dynamic detection timestamp formatting
      const formatUtc = (ts: string) => {
        try {
          const d = new Date(ts);
          if (isNaN(d.getTime())) return ts;
          const yr = d.getUTCFullYear();
          const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
          const da = String(d.getUTCDate()).padStart(2, '0');
          const hr = String(d.getUTCHours()).padStart(2, '0');
          const mi = String(d.getUTCMinutes()).padStart(2, '0');
          return `${yr}-${mo}-${da} ${hr}:${mi} UTC`;
        } catch {
          return ts;
        }
      };

      const formattedTimestamp = formatUtc(rawTimestamp);

      // Pulsing detection point with "Detected" label at spill centroid [cx, cy]
      const detIcon = L.divIcon({
        className: '',
        html: `
          <div class="gis-det-marker-wrap" style="position: relative; display: flex; align-items: center; cursor: pointer;">
            <div class="det-marker-wrapper" style="flex-shrink: 0;">
              <div class="det-marker-pulse"></div>
              <div class="det-marker-core"></div>
            </div>
            <div class="gis-popup-card pointer-left" style="margin-left: 8px;">
              <div style="font-weight: 800; font-size: 11px; color: #dc2626; line-height: 1.2; text-transform: uppercase; letter-spacing: 0.04em;">Detected Spill</div>
              <div style="font-size: 9px; color: #475569; margin-top: 1.5px; font-family: 'Inter', monospace; font-weight: 600;">${formattedTimestamp}</div>
            </div>
          </div>
        `,
        iconSize: [200, 36],
        iconAnchor: [14, 18],
      });

      const detMarker = L.marker([cx, cy], {
        icon: detIcon,
        pane: 'detectionMarkerPane',
        zIndexOffset: 1000,
      });
      detMarker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        onSelectEntity({ type: 'spill', id: null });
      });
      mapLayersGroup.current.addLayer(detMarker);
    }

    // ══════════════════════════════════════════════════════
    // 2. DISCHARGE ORIGIN POINT (Hindcast Origin)
    // ══════════════════════════════════════════════════════
    if (layers.drift && (origLat !== cx || origLng !== cy)) {
      const origIcon = L.divIcon({
        className: '',
        html: `
          <div class="gis-origin-marker-wrap" style="position: relative; display: flex; align-items: center; flex-direction: row-reverse; cursor: pointer;">
            <div class="origin-marker-dot" style="flex-shrink: 0; width: 13px; height: 13px;"></div>
            <div class="gis-popup-card pointer-right" style="margin-right: 8px; text-align: right; white-space: nowrap; border-color: rgba(249,115,22,0.35);">
              <div style="font-weight: 800; font-size: 10px; color: #ea580c; line-height: 1.2; text-transform: uppercase; letter-spacing: 0.04em;">Origin Point</div>
              <div style="font-size: 9px; color: #475569; margin-top: 1.5px; font-family: 'Inter', monospace; font-weight: 600;">Discharge Source</div>
            </div>
          </div>
        `,
        iconSize: [160, 36],
        iconAnchor: [154, 18],
      });

      const origMarker = L.marker([origLat, origLng], {
        icon: origIcon,
        pane: 'detectionMarkerPane',
        zIndexOffset: 950,
      });
      origMarker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        onSelectEntity({ type: 'origin', id: null });
      });
      mapLayersGroup.current.addLayer(origMarker);
    }

    // ══════════════════════════════════════════════════════
    // 3. AIS VESSEL CANDIDATES (Ranked 1, 2, 3 by Probability)
    // ══════════════════════════════════════════════════════
    const renderedVesselCoords: [number, number][] = [];
    if (layers.ais && currentData.vessels && currentData.vessels.length > 0) {
      // Sort vessels by probability/score descending so Rank 1 is the highest probability
      const sortedVessels = [...currentData.vessels].sort((a, b) => {
        const scoreA = a.compositeScore ?? a.score ?? (a.posterior_probability ? a.posterior_probability * 100 : 0);
        const scoreB = b.compositeScore ?? b.score ?? (b.posterior_probability ? b.posterior_probability * 100 : 0);
        return scoreB - scoreA;
      });

      // Distinct vibrant tactical colors per rank (Blue is reserved exclusively for Hindcast/Forecast drift tracks)
      const RANK_COLORS = [
        '#EF4444', // Rank 1: Crimson Red (Highest Attribution / Primary Suspect)
        '#F59E0B', // Rank 2: Vivid Amber (Moderate Risk)
        '#8B5CF6', // Rank 3: Electric Purple (Low Risk)
        '#10B981', // Rank 4: Emerald Green
        '#EC4899', // Rank 5: Hot Pink / Magenta
        '#F97316', // Rank 6: Bright Orange
      ];

      // Default surrounding offsets in water around detected spill [cx, cy]
      const defaultOffsets = [
        { dLat: 0.038, dLng: -0.062, heading: 135 }, // Rank 1: In the corridor between origin & spill
        { dLat: -0.015, dLng: -0.075, heading: 70 },  // Rank 2: West of spill
        { dLat: -0.045, dLng: 0.055, heading: 315 },  // Rank 3: Southeast of spill
        { dLat: 0.065, dLng: 0.045, heading: 210 },   // Rank 4
        { dLat: -0.065, dLng: -0.025, heading: 45 },  // Rank 5
      ];

      // Default historical approach trajectories for vessels (from outer open waters toward spill area)
      const defaultTrajectories: [number, number][][] = [
        // Rank 1 (MT OCEAN VOYAGER): Approach from NW outer open sea past origin discharge point
        [
          [22.310, 68.640], // Farthest in open sea (~23 km NW of spill)
          [22.285, 68.670],
          [22.260, 68.698],
          [22.235, 68.730],
          [22.218, 68.748], // closest approach
        ],
        // Rank 2 (CAPE GUARDIAN): Approach from West outer open sea
        [
          [22.150, 68.595], // Farthest in open sea (~23 km W of spill)
          [22.155, 68.640],
          [22.160, 68.680],
          [22.165, 68.735], // closest approach
        ],
        // Rank 3 (FISHING VESSEL 7): Approach from Southeast coastal channel
        [
          [22.030, 68.980], // Farthest in open channel (~25 km SE of spill)
          [22.065, 68.945],
          [22.100, 68.905],
          [22.135, 68.865], // closest approach
        ],
      ];

      // Clean, crisp vector SVG generator for high-definition top-down ship model (no trailing waves/wakes)
      const getVesselSvg = (color: string, isSel: boolean) => `
        <svg width="28" height="66" viewBox="0 0 28 66" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0 4px 8px rgba(0,0,0,0.75));">
          <defs>
            <linearGradient id="hull-grad-${color.replace('#', '')}" x1="0" y1="0" x2="28" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#0f172a"/>
              <stop offset="25%" stop-color="#1e293b"/>
              <stop offset="50%" stop-color="#334155"/>
              <stop offset="75%" stop-color="#1e293b"/>
              <stop offset="100%" stop-color="#0f172a"/>
            </linearGradient>
            <linearGradient id="deck-grad-${color.replace('#', '')}" x1="14" y1="8" x2="14" y2="60" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#475569"/>
              <stop offset="100%" stop-color="#1e293b"/>
            </linearGradient>
          </defs>

          <!-- Outer Ship Hull with Hydrodynamic Pointed Bow and Transom Stern -->
          <path
            d="M 14 2 
               C 18 8, 26 18, 26 28 
               L 26 56 
               C 26 62, 21 64, 14 64 
               C 7 64, 2 62, 2 56 
               L 2 28 
               C 2 18, 10 8, 14 2 Z"
            fill="url(#hull-grad-${color.replace('#', '')})"
            stroke="${color}"
            stroke-width="${isSel ? 2.8 : 1.8}"
          />

          <!-- Weather Deck Inner Border -->
          <path
            d="M 14 6 
               C 17 11, 23 19, 23 28 
               L 23 54 
               C 23 58, 19 60, 14 60 
               C 9 60, 5 58, 5 54 
               L 5 28 
               C 5 19, 11 11, 14 6 Z"
            fill="url(#deck-grad-${color.replace('#', '')})"
            stroke="rgba(255,255,255,0.25)"
            stroke-width="0.8"
          />

          <!-- Cargo Holds / Tank Hatches -->
          <rect x="8.5" y="17" width="11" height="7" rx="1.5" fill="#1e293b" stroke="${color}" stroke-width="0.9" opacity="0.95" />
          <rect x="8.5" y="27" width="11" height="7" rx="1.5" fill="#1e293b" stroke="${color}" stroke-width="0.9" opacity="0.95" />
          <rect x="8.5" y="37" width="11" height="7" rx="1.5" fill="#1e293b" stroke="${color}" stroke-width="0.9" opacity="0.95" />

          <!-- Center Deck Pipeline / Catwalk -->
          <line x1="14" y1="14" x2="14" y2="45" stroke="#94a3b8" stroke-width="1.2" stroke-linecap="round" />

          <!-- Aft Bridge Superstructure (Wheelhouse) -->
          <rect x="7.5" y="46" width="13" height="10" rx="2" fill="#f8fafc" stroke="#64748b" stroke-width="1" />
          <!-- Bridge Windows -->
          <rect x="9" y="47.5" width="10" height="2.5" rx="0.5" fill="#334155" />

          <!-- Radar Mast & Exhaust Funnel in Vessel Color -->
          <circle cx="14" cy="58.5" r="2.2" fill="${color}" stroke="#ffffff" stroke-width="0.75" />

          <!-- Navigation Lights: Port Red (left side x=3.5), Starboard Green (right side x=24.5) -->
          <circle cx="4" cy="24" r="1.8" fill="#ef4444" stroke="#ffffff" stroke-width="0.6" />
          <circle cx="24" cy="24" r="1.8" fill="#22c55e" stroke="#ffffff" stroke-width="0.6" />

          <!-- Bow Masthead Running Light (White) -->
          <circle cx="14" cy="4.5" r="1.5" fill="#ffffff" stroke="rgba(0,0,0,0.5)" stroke-width="0.5" />
        </svg>
      `;

      sortedVessels.forEach((v, idx) => {
        const rank = idx + 1;
        const isBayesian = v.scoringMode === 'BAYESIAN_POSTERIOR';
        const vId = isBayesian && (v as any).candidate_id ? (v as any).candidate_id : v.mmsi;
        const isSelected = selectedEntity.type === 'vessel' && selectedEntity.id === vId;
        const vScore = v.compositeScore ?? v.score ?? (v.posterior_probability ? Math.round(v.posterior_probability * 100) : 0);

        const rankColor = RANK_COLORS[idx % RANK_COLORS.length];
        const fallback = defaultOffsets[idx % defaultOffsets.length];

        // ── 1. Dotted Historical Trajectory in Distinct Color ──
        let trajectoryPoints: [number, number][] = [];
        if (v.trajectoryGeojson && v.trajectoryGeojson.features) {
          v.trajectoryGeojson.features.forEach((feat: any) => {
            if (feat.geometry?.coordinates) {
              const pts = feat.geometry.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number]);
              if (pts.length > 1) trajectoryPoints = pts;
            }
          });
        }
        if (trajectoryPoints.length < 2) {
          trajectoryPoints = defaultTrajectories[idx % defaultTrajectories.length] || [
            [cx + fallback.dLat * 2.5, cy + fallback.dLng * 2.5],
            [cx + fallback.dLat, cy + fallback.dLng],
          ];
        }

        // ── 2. Position Ship at Farthest Trajectory Point from Oil Spill Centroid [cx, cy] ──
        // This keeps the ships out in open water and eliminates all congestion around the spill!
        let farthestPt = trajectoryPoints[0];
        let maxDistSq = -1;
        let farthestIdx = 0;
        trajectoryPoints.forEach((p, pIdx) => {
          const dLat = p[0] - cx;
          const dLng = p[1] - cy;
          const distSq = dLat * dLat + dLng * dLng;
          if (distSq > maxDistSq) {
            maxDistSq = distSq;
            farthestPt = p;
            farthestIdx = pIdx;
          }
        });

        const vLat = farthestPt[0];
        const vLng = farthestPt[1];
        renderedVesselCoords.push([vLat, vLng]);

        // Dynamic heading: orient ship along trajectory towards the adjacent waypoint (pointing toward the spill area)
        let vHeading = fallback.heading;
        const targetPt = farthestIdx === 0 ? trajectoryPoints[1] : trajectoryPoints[farthestIdx - 1];
        if (targetPt) {
          const dy = targetPt[0] - vLat;
          const dx = (targetPt[1] - vLng) * Math.cos((vLat * Math.PI) / 180);
          vHeading = Math.round((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
        }

        // Include trajectory points in bounds
        trajectoryPoints.forEach(p => allBoundsPts.push(p));

        if (isSelected) {
          const haloLine = L.polyline(trajectoryPoints, {
            color: '#FFFFFF',
            weight: 6,
            opacity: 0.9,
            lineCap: 'round',
            pane: 'trajectoryPane',
          });
          mapLayersGroup.current?.addLayer(haloLine);
        }

        // Render distinct dotted line for this ship
        const trackLine = L.polyline(trajectoryPoints, {
          color: rankColor,
          weight: isSelected ? 3.5 : 2.8,
          opacity: isSelected ? 1.0 : 0.9,
          dashArray: '4, 7', // Dotted line!
          lineCap: 'round',
          pane: 'trajectoryPane',
        });
        trackLine.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectEntity({ type: 'vessel', id: vId });
        });
        mapLayersGroup.current?.addLayer(trackLine);

        // Circular waypoint breadcrumbs
        trajectoryPoints.forEach((pt, pIdx) => {
          if (pIdx < trajectoryPoints.length - 1) {
            const waypoint = L.circleMarker(pt, {
              radius: isSelected ? 3.5 : 2.5,
              fillColor: rankColor,
              fillOpacity: 0.95,
              color: '#FFFFFF',
              weight: 1,
              pane: 'trajectoryPane',
            });
            waypoint.on('click', (e) => {
              L.DomEvent.stopPropagation(e);
              onSelectEntity({ type: 'vessel', id: vId });
            });
            mapLayersGroup.current?.addLayer(waypoint);
          }
        });

        // ── 3. Clean Vector Ship Graphic & Large Clear Confidence Badge ──
        const shipSvg = getVesselSvg(rankColor, isSelected);

        const vesselIcon = L.divIcon({
          className: '',
          html: `
            <div class="gis-vessel-marker-container" style="
              position: relative;
              display: flex;
              flex-direction: column;
              align-items: center;
              cursor: pointer;
              user-select: none;
              transform: scale(var(--vessel-scale, 1));
              transform-origin: center center;
              transition: transform 0.15s cubic-bezier(0.2, 0, 0, 1);
            ">
              <!-- Large Clear Ranking & Confidence % Badge -->
              <div class="gis-vessel-badge" style="
                display: flex;
                align-items: center;
                gap: 6px;
                background: ${rankColor};
                color: #ffffff;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1.5px solid #ffffff;
                box-shadow: 0 4px 14px rgba(0,0,0,0.55), 0 0 0 1px rgba(0,0,0,0.2);
                white-space: nowrap;
                letter-spacing: 0.02em;
                margin-bottom: 5px;
                ${isSelected ? 'box-shadow: 0 0 16px ' + rankColor + ', 0 4px 14px rgba(0,0,0,0.6); transform: scale(1.12);' : ''}
                transition: transform 0.2s ease;
              ">
                <span style="font-size: 11.5px; font-weight: 900; font-family: 'Inter', sans-serif;">#${rank}</span>
                <span style="width: 1.5px; height: 12px; background: rgba(255,255,255,0.4); display: inline-block;"></span>
                <span style="font-size: 13px; font-weight: 900; font-family: 'Inter', monospace; letter-spacing: -0.02em;">${vScore}%</span>
                <span style="font-size: 8px; font-weight: 800; text-transform: uppercase; opacity: 0.95; margin-left: 1px;">MATCH</span>
              </div>

              <!-- Crisp Vector Ship (28px x 66px, rotated to heading) -->
              <div style="
                width: 28px;
                height: 66px;
                display: flex;
                align-items: center;
                justify-content: center;
                transform: rotate(${vHeading}deg);
                transform-origin: center center;
                filter: ${isSelected ? 'drop-shadow(0 0 12px ' + rankColor + ')' : ''};
                transition: transform 0.2s ease;
              ">
                ${shipSvg}
              </div>

              <!-- Vessel Name & Telemetry Pill -->
              <div class="gis-vessel-name-pill ${isSelected ? 'is-selected' : ''}" style="
                margin-top: 5px;
                background: rgba(15, 23, 42, 0.94);
                backdrop-filter: blur(6px);
                color: #ffffff;
                font-size: 10px;
                font-weight: 800;
                font-family: 'Inter', sans-serif;
                padding: 3px 9px;
                border-radius: 5px;
                border: 1px solid ${rankColor};
                box-shadow: 0 2px 10px rgba(0,0,0,0.5);
                white-space: nowrap;
                display: flex;
                align-items: center;
                gap: 5px;
              ">
                <span>${v.name}</span>
                <span style="color: #94a3b8; font-size: 8.5px; font-family: monospace; font-weight: 600;">• ${v.speed} kn</span>
              </div>
            </div>
          `,
          iconSize: [160, 140],
          iconAnchor: [80, 68],
        });

        const vesselMarker = L.marker([vLat, vLng], {
          icon: vesselIcon,
          pane: 'vesselPane',
          zIndexOffset: 950 - rank * 10,
        });
        vesselMarker.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          onSelectEntity({ type: 'vessel', id: vId });
        });
        mapLayersGroup.current?.addLayer(vesselMarker);
      });
    }

    // ══════════════════════════════════════════════════════
    // 4. HINDCASTING & FORECASTING TRAJECTORIES WITH DIRECTIONAL ARROWS
    // ══════════════════════════════════════════════════════
    if (layers.drift) {
      // Helper function to render a dotted trajectory line with small directional arrows
      const renderTrackWithArrows = (
        points: [number, number][],
        color: string,
        dashArray: string = '5, 6'
      ) => {
        if (points.length < 2) return;

        // 1. Dotted Polyline
        const trackPolyline = L.polyline(points, {
          color,
          weight: 2.8,
          dashArray,
          opacity: 0.95,
          lineCap: 'round',
          pane: 'trajectoryPane',
        });
        mapLayersGroup.current?.addLayer(trackPolyline);

        // 2. Small Directional Arrows along Line Segments
        for (let i = 0; i < points.length - 1; i++) {
          const p1 = points[i];
          const p2 = points[i + 1];
          const dY = p2[0] - p1[0];
          const dX = (p2[1] - p1[1]) * Math.cos(((p1[0] + p2[0]) / 2 * Math.PI) / 180);
          const segmentDist = Math.hypot(dY, dX);
          if (segmentDist < 0.0001) continue;

          // Bearing angle from p1 to p2 (0° = North, 90° = East, 180° = South, 270° = West)
          const bearing = (Math.atan2(dX, dY) * 180 / Math.PI + 360) % 360;

          // Determine distribution of arrows along this segment
          const tFractions = segmentDist > 0.07 ? [0.28, 0.55, 0.82] : [0.5];

          tFractions.forEach((t) => {
            const arrowLat = p1[0] + (p2[0] - p1[0]) * t;
            const arrowLng = p1[1] + (p2[1] - p1[1]) * t;

            const arrowIcon = L.divIcon({
              className: '',
              html: `
                <div style="
                  width: 12px;
                  height: 12px;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  transform: rotate(${bearing}deg);
                  pointer-events: none;
                ">
                  <svg width="10" height="10" viewBox="0 0 10 10" style="overflow: visible;">
                    <polygon
                      points="5,0.5 9,8.5 5,6.5 1,8.5"
                      fill="${color}"
                      stroke="#ffffff"
                      stroke-width="0.8"
                      stroke-linejoin="round"
                    />
                  </svg>
                </div>
              `,
              iconSize: [12, 12],
              iconAnchor: [6, 6],
            });

            const arrowMarker = L.marker([arrowLat, arrowLng], {
              icon: arrowIcon,
              pane: 'trajectoryPane',
              interactive: false,
              zIndexOffset: 750,
            });
            mapLayersGroup.current?.addLayer(arrowMarker);
          });
        }
      };

      // Blue is exclusively reserved for Hindcasting & Forecasting drift trajectories and their arrows
      const DRIFT_TRAJECTORY_BLUE = '#0284c7';

      // ── A. HINDCASTING TRACK: From Detection Point [cx, cy] -> Origin Point [origLat, origLng] ──
      // Uses the same reserved Blue color with arrows pointing towards the discharge origin
      const distToOrigin = Math.hypot(origLat - cx, origLng - cy);
      if (distToOrigin > 0.002) {
        const hindcastPoints: [number, number][] = [
          [cx, cy],
          [origLat, origLng],
        ];
        renderTrackWithArrows(hindcastPoints, DRIFT_TRAJECTORY_BLUE, '5, 6');
      }

      // ── B. FORECASTING TRACK: From Detection Point [cx, cy] -> +6h -> +12h -> +24h -> +48h ──
      // Uses the same reserved Blue color with arrows pointing forward into future forecast
      const fcHorizons = ['6h', '12h', '24h', '48h'];
      const fcCoords: { key: string; lat: number; lng: number }[] = [];
      const forecastPoints: [number, number][] = [[cx, cy]];

      fcHorizons.forEach((hKey, idx) => {
        const fcObj = forecast[hKey];
        let pLat: number;
        let pLng: number;

        if (fcObj?.centroid_latitude && fcObj?.centroid_longitude) {
          pLat = fcObj.centroid_latitude;
          pLng = fcObj.centroid_longitude;
        } else {
          // Dynamic interpolation along drift vector
          const stepMultiplier = [1, 1.8, 3.2, 5.0][idx];
          pLat = origLat + dLat * (0.4 + stepMultiplier * 0.35);
          pLng = origLng + dLng * (0.4 + stepMultiplier * 0.35);
        }

        fcCoords.push({ key: hKey, lat: pLat, lng: pLng });
        forecastPoints.push([pLat, pLng]);
      });

      renderTrackWithArrows(forecastPoints, DRIFT_TRAJECTORY_BLUE, '5, 6');

      // Render Forecast Checkpoints & Floating GIS Labels (Revealed on hover)
      fcCoords.forEach((pt) => {
        const latStr = `${Math.abs(pt.lat).toFixed(2)}°${pt.lat >= 0 ? 'N' : 'S'}`;
        const lngStr = `${Math.abs(pt.lng).toFixed(2)}°${pt.lng >= 0 ? 'E' : 'W'}`;

        // Compute projected forecast date & time based on detection time
        const hoursOffset = parseInt(pt.key.replace('h', ''), 10) || 0;
        let fcTimeStr = '';
        try {
          const baseDate = new Date(rawTimestamp);
          if (!isNaN(baseDate.getTime())) {
            const projected = new Date(baseDate.getTime() + hoursOffset * 3600 * 1000);
            const yr = projected.getUTCFullYear();
            const mo = String(projected.getUTCMonth() + 1).padStart(2, '0');
            const da = String(projected.getUTCDate()).padStart(2, '0');
            const hr = String(projected.getUTCHours()).padStart(2, '0');
            const mi = String(projected.getUTCMinutes()).padStart(2, '0');
            fcTimeStr = `${yr}-${mo}-${da} ${hr}:${mi} UTC`;
          }
        } catch { }

        const fcIcon = L.divIcon({
          className: '',
          html: `
            <div class="gis-forecast-marker-wrap" style="
              position: relative;
              width: 24px;
              height: 24px;
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
            ">
              <div class="gis-fc-marker" style="flex-shrink: 0;"></div>
              <div class="gis-popup-card pointer-left" style="
                position: absolute;
                left: 100%;
                top: 50%;
                transform: translateY(-50%);
                margin-left: 8px;
                white-space: nowrap;
              ">
                <div style="font-weight: 800; font-size: 10.5px; color: #0284c7; line-height: 1.2; display: flex; align-items: center; gap: 5px;">
                  <span>+${pt.key}</span>
                  ${fcTimeStr ? `<span style="font-size: 9px; color: #64748b; font-weight: 600; font-family: 'Inter', monospace;">• ${fcTimeStr}</span>` : ''}
                </div>
                <div style="font-size: 9px; color: #334155; margin-top: 2px; font-family: 'Inter', monospace; font-weight: 600;">
                  ${latStr}, ${lngStr}
                </div>
              </div>
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        const fcMarker = L.marker([pt.lat, pt.lng], {
          icon: fcIcon,
          pane: 'forecastMarkerPane',
          zIndexOffset: 850,
        });
        mapLayersGroup.current?.addLayer(fcMarker);
      });
    }

    // Dynamic camera centering & bounds fitting - add forecast points & vessels
    if (fc6?.centroid_latitude) allBoundsPts.push([fc6.centroid_latitude, fc6.centroid_longitude]);
    if (fc12?.centroid_latitude) allBoundsPts.push([fc12.centroid_latitude, fc12.centroid_longitude]);
    if (fc24?.centroid_latitude) allBoundsPts.push([fc24.centroid_latitude, fc24.centroid_longitude]);
    if (fc48?.centroid_latitude) allBoundsPts.push([fc48.centroid_latitude, fc48.centroid_longitude]);

    // Push all rendered vessel positions
    renderedVesselCoords.forEach((p) => allBoundsPts.push(p));

    if (!selectedEntity.type && allBoundsPts.length > 0) {
      try {
        leafletMap.current.fitBounds(L.latLngBounds(allBoundsPts), {
          padding: [60, 60],
          maxZoom: 11,
          animate: false,
        });
        initialZoomRef.current = leafletMap.current.getZoom();
      } catch (e) { }
    }
    updateVesselZoomScale();

    setTimeout(() => {
      if (leafletMap.current) {
        if (initialZoomRef.current === null) {
          initialZoomRef.current = leafletMap.current.getZoom();
        }
        leafletMap.current.invalidateSize();
        updateScaleBar();
        updateVesselZoomScale();
      }
    }, 150);
  }, [currentData, layers, selectedEntity, onSelectEntity, updateScaleBar, updateVesselZoomScale]);

  const handleSetBasemap = (mode: 'satellite' | 'map') => {
    if (!leafletMap.current) return;
    const map = leafletMap.current;

    if (mode === 'satellite') {
      if (streetLayerRef.current && map.hasLayer(streetLayerRef.current)) {
        map.removeLayer(streetLayerRef.current);
      }
      if (satLayerRef.current && !map.hasLayer(satLayerRef.current)) {
        satLayerRef.current.addTo(map);
      }
      if (placesLayerRef.current && !map.hasLayer(placesLayerRef.current)) {
        placesLayerRef.current.addTo(map);
      }
      setIsSatellite(true);
    } else {
      if (satLayerRef.current && map.hasLayer(satLayerRef.current)) {
        map.removeLayer(satLayerRef.current);
      }
      if (placesLayerRef.current && map.hasLayer(placesLayerRef.current)) {
        map.removeLayer(placesLayerRef.current);
      }
      if (streetLayerRef.current && !map.hasLayer(streetLayerRef.current)) {
        streetLayerRef.current.addTo(map);
      }
      setIsSatellite(false);
    }
  };

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none">
      {/* ── Main Map Canvas Container ── */}
      <div ref={mapRef} className="absolute inset-0 w-full h-full z-0" style={{ cursor: 'crosshair' }} />

      {/* ── Bottom-Right Controls: Basemap Switcher & Zoom In/Out ── */}
      <div className="absolute bottom-4 right-4 z-[400] pointer-events-auto flex flex-col items-end gap-2 select-none">
        {/* Zoom In / Zoom Out Controls */}
        <div className="flex flex-col bg-white/95 backdrop-blur-xs rounded-md shadow-md border border-slate-300 overflow-hidden divide-y divide-slate-200">
          <button
            type="button"
            onClick={() => leafletMap.current?.zoomIn()}
            className="w-8 h-8 flex items-center justify-center text-slate-700 hover:text-navy-800 hover:bg-slate-100 transition-colors"
            title="Zoom in"
            aria-label="Zoom in"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
          </button>
          <button
            type="button"
            onClick={() => leafletMap.current?.zoomOut()}
            className="w-8 h-8 flex items-center justify-center text-slate-700 hover:text-navy-800 hover:bg-slate-100 transition-colors"
            title="Zoom out"
            aria-label="Zoom out"
          >
            <Minus className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>

        {/* Basemap Switcher: Map / Satellite */}
        <div className="flex bg-white/95 backdrop-blur-xs rounded-md shadow-md border border-slate-300 p-0.5 text-[11px] font-semibold">
          <button
            type="button"
            onClick={() => handleSetBasemap('map')}
            className={`px-2.5 py-1 rounded transition-colors ${
              !isSatellite
                ? 'bg-navy-800 text-white font-bold shadow-xs'
                : 'text-slate-600 hover:text-navy-800 hover:bg-slate-100'
            }`}
            title="Switch to Standard Map View"
          >
            Map
          </button>
          <button
            type="button"
            onClick={() => handleSetBasemap('satellite')}
            className={`px-2.5 py-1 rounded transition-colors ${
              isSatellite
                ? 'bg-navy-800 text-white font-bold shadow-xs'
                : 'text-slate-600 hover:text-navy-800 hover:bg-slate-100'
            }`}
            title="Switch to Satellite Imagery View"
          >
            Satellite
          </button>
        </div>
      </div>

      {/* ── 4. Professional GIS Scale Bar (Bottom-Left) ── */}
      <div className="absolute bottom-4 left-6 z-[400] pointer-events-auto select-none font-mono transition-all duration-300">
        <div
          className="flex justify-between text-[10px] font-bold text-white mb-1 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
          style={{ width: `${scaleInfo.widthPx}px` }}
        >
          <span>0</span>
          <span>{scaleInfo.quarterKm}</span>
          <span>{scaleInfo.halfKm}</span>
          <span>{scaleInfo.maxKm} km</span>
        </div>
        <div
          className="gis-scale-bar-line"
          style={{ width: `${scaleInfo.widthPx}px` }}
        >
          <div className="gis-scale-tick" style={{ left: '25%' }} />
          <div className="gis-scale-tick" style={{ left: '50%' }} />
        </div>
      </div>
    </div>
  );
};
