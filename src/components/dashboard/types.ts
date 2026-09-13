export interface DashboardEntityState {
  type: 'origin' | 'spill' | 'vessel' | null;
  id: string | null;
}

export interface VesselCandidate {
  raw: any;
  name: string;
  mmsi: string;
  type: string;
  flag: string;
  score: number;
  compositeScore: number;
  riskClass: string;
  scoringMode: string;
  originPresence: number;
  behaviorAnomaly: number;
  dwellTime: number;
  aisGap: number;
  approachDeparture: number | null;
  proximity: number;
  trajectory: number;
  behavioral: number;
  flags: string[];
  qualityFlags: string[];
  evidence: any;
  explanation: string;
  trajectoryGeojson: any;
  color: string;
  lat: number;
  lng: number;
  heading: number;
  speed: number;
}

export interface CurrentDashboardData {
  title: string;
  location: string;
  confidence: string;
  area: string;
  length: string;
  width: string;
  estVolume: string;
  estAge: string;
  originTime: string;
  detectionTime: string;
  source: string;
  center: [number, number];
  zoom: number;
  spillPolygon: [number, number][];
  driftPath: { label: string; lat: number; lng: number; text: string }[];
  vessels: VesselCandidate[];
  feature2Data?: any;
  spillInfo?: any;
  activeCase?: string;
}
