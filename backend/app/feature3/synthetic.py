"""
Synthetic AIS telemetry generator for spill incidents.
Generates realistic, spatio-temporally correlated vessel traffic around a spill origin
when no external AIS telemetry dataset is provided, or when an uploaded CSV is non-AIS.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import math


def generate_incident_ais_telemetry(
    origin_lat: float,
    origin_lon: float,
    origin_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Generates a realistic set of 4 commercial vessels navigating in the vicinity of the spill origin:
      1. MT OCEAN EMPEROR (Crude Oil Tanker, Panama) - Primary suspect: passes within 0.3 km, speed drop from 14 to 3.2 kts
      2. MT BHARAT RATNA (Chemical Tanker, India) - Close transit: passes ~3.8 km away at steady speed
      3. MV SEA PIONEER (Bulk Carrier, Liberia) - Corridor transit: passes ~8.5 km away
      4. EVER HARMONY (Container Ship, Hong Kong) - Distant transit: passes ~16.0 km away along commercial TSS lane
    """
    if origin_time is None:
        origin_time = datetime.now(timezone.utc)
    elif origin_time.tzinfo is None:
        origin_time = origin_time.replace(tzinfo=timezone.utc)

    records: List[Dict[str, Any]] = []

    # 1. MT OCEAN EMPEROR - Primary Suspect Tanker
    # Slower transit, passes directly through origin at origin_time, sharp speed drop and course change
    # 1 deg lat ~ 111 km, 1 deg lon ~ 104 km at lat 20
    km_per_lat = 111.0
    km_per_lon = 111.0 * math.cos(math.radians(origin_lat))

    suspect_pings = [
        # (hours_offset, dist_km_along, dist_km_cross, sog, cog)
        (-3.0, -22.0, -0.2, 14.5, 42.0),
        (-2.0, -14.5, -0.1, 14.2, 43.0),
        (-1.0, -7.0, 0.0, 13.8, 44.0),
        (-0.3, -2.0, 0.1, 9.5, 46.0),
        (0.0, 0.2, 0.1, 3.2, 58.0),   # At origin: speed drop to 3.2 kts, bearing change
        (0.5, 1.8, 0.4, 5.0, 62.0),
        (1.5, 9.0, 1.2, 12.8, 48.0),
        (3.0, 21.0, 2.5, 13.5, 45.0),
    ]

    for h_off, d_along, d_cross, sog, cog in suspect_pings:
        t = origin_time + timedelta(hours=h_off)
        # Heading 45 deg means along track is NE, cross track is NW
        rad45 = math.radians(45.0)
        d_north = d_along * math.cos(rad45) - d_cross * math.sin(rad45)
        d_east = d_along * math.sin(rad45) + d_cross * math.cos(rad45)
        lat = round(origin_lat + (d_north / km_per_lat), 6)
        lon = round(origin_lon + (d_east / km_per_lon), 6)
        records.append({
            "mmsi": "419001842",
            "vessel_name": "MT OCEAN EMPEROR",
            "vessel_type": "Crude Oil Tanker",
            "flag": "Panama",
            "timestamp": t.isoformat(),
            "lat": lat,
            "lon": lon,
            "sog": sog,
            "cog": cog,
            "heading": cog,
        })

    # 2. MT BHARAT RATNA - Product/Chemical Tanker (Close transit ~3.8 km away)
    close_pings = [
        (-2.5, -18.0, 3.8, 12.0, 44.0),
        (-1.5, -10.5, 3.7, 12.2, 45.0),
        (-0.5, -3.2, 3.8, 12.1, 45.0),
        (0.5, 4.2, 3.9, 11.9, 44.0),
        (2.0, 15.5, 3.8, 12.0, 45.0),
    ]
    for h_off, d_along, d_cross, sog, cog in close_pings:
        t = origin_time + timedelta(hours=h_off)
        rad45 = math.radians(45.0)
        d_north = d_along * math.cos(rad45) - d_cross * math.sin(rad45)
        d_east = d_along * math.sin(rad45) + d_cross * math.cos(rad45)
        lat = round(origin_lat + (d_north / km_per_lat), 6)
        lon = round(origin_lon + (d_east / km_per_lon), 6)
        records.append({
            "mmsi": "419002915",
            "vessel_name": "MT BHARAT RATNA",
            "vessel_type": "Chemical Tanker",
            "flag": "India",
            "timestamp": t.isoformat(),
            "lat": lat,
            "lon": lon,
            "sog": sog,
            "cog": cog,
            "heading": cog,
        })

    # 3. MV SEA PIONEER - Bulk Carrier (Corridor transit ~8.5 km away)
    corridor_pings = [
        (-3.0, -25.0, 8.5, 11.5, 40.0),
        (-1.5, -12.0, 8.4, 11.4, 40.0),
        (0.0, 0.5, 8.5, 11.2, 40.0),
        (1.5, 13.0, 8.6, 11.5, 41.0),
        (3.0, 26.0, 8.5, 11.3, 40.0),
    ]
    for h_off, d_along, d_cross, sog, cog in corridor_pings:
        t = origin_time + timedelta(hours=h_off)
        rad40 = math.radians(40.0)
        d_north = d_along * math.cos(rad40) - d_cross * math.sin(rad40)
        d_east = d_along * math.sin(rad40) + d_cross * math.cos(rad40)
        lat = round(origin_lat + (d_north / km_per_lat), 6)
        lon = round(origin_lon + (d_east / km_per_lon), 6)
        records.append({
            "mmsi": "636014238",
            "vessel_name": "MV SEA PIONEER",
            "vessel_type": "Bulk Carrier",
            "flag": "Liberia",
            "timestamp": t.isoformat(),
            "lat": lat,
            "lon": lon,
            "sog": sog,
            "cog": cog,
            "heading": cog,
        })

    # 4. EVER HARMONY - Container Ship (TSS Lane ~16 km away)
    tss_pings = [
        (-2.0, -28.0, 16.0, 18.0, 38.0),
        (-0.5, -7.0, 16.2, 17.8, 38.0),
        (1.0, 14.0, 16.1, 18.2, 38.0),
        (2.5, 35.0, 16.0, 17.9, 38.0),
    ]
    for h_off, d_along, d_cross, sog, cog in tss_pings:
        t = origin_time + timedelta(hours=h_off)
        rad38 = math.radians(38.0)
        d_north = d_along * math.cos(rad38) - d_cross * math.sin(rad38)
        d_east = d_along * math.sin(rad38) + d_cross * math.cos(rad38)
        lat = round(origin_lat + (d_north / km_per_lat), 6)
        lon = round(origin_lon + (d_east / km_per_lon), 6)
        records.append({
            "mmsi": "477123984",
            "vessel_name": "EVER HARMONY",
            "vessel_type": "Container Ship",
            "flag": "Hong Kong",
            "timestamp": t.isoformat(),
            "lat": lat,
            "lon": lon,
            "sog": sog,
            "cog": cog,
            "heading": cog,
        })

    return records
