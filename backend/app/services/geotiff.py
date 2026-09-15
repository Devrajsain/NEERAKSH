"""
GeoTIFF Geospatial Metadata Inspection & Coordinate Transformation Service.

Inspects raster files to check for valid CRS and geotransform metadata.
Converts detected pixel coordinates (from Feature 1 spill detection)
into real-world WGS84 (EPSG:4326) latitude and longitude.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np

logger = logging.getLogger(__name__)

# Cache availability of rasterio & pyproj
_RASTERIO_AVAILABLE = False
_PYPROJ_AVAILABLE = False

try:
    import rasterio
    from rasterio.transform import xy
    _RASTERIO_AVAILABLE = True
except Exception as e:
    logger.warning(f"rasterio not available: {e}")

try:
    import pyproj
    from pyproj import Transformer
    _PYPROJ_AVAILABLE = True
except Exception as e:
    logger.warning(f"pyproj not available: {e}")


def _parse_timestamp_string(ts_str: str) -> Optional[str]:
    """Parses various satellite metadata timestamp formats into strict ISO-8601 UTC string."""
    from datetime import datetime, timezone
    import re
    from dateutil import parser as dateutil_parser

    if not ts_str or not isinstance(ts_str, str):
        return None

    cleaned = ts_str.strip().strip("'\"")
    if not cleaned:
        return None

    # Common format 1: TIFFTAG_DATETIME "YYYY:MM:DD HH:MM:SS"
    m = re.match(r"^(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$", cleaned)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
                tzinfo=timezone.utc
            )
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    # Common format 2: Sentinel-1 DIMAP "03-AUG-2018 17:25:57.581481"
    try:
        if "-" in cleaned and any(mo in cleaned.upper() for mo in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]):
            main_part = cleaned.split(".")[0]
            dt = datetime.strptime(main_part, "%d-%b-%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    # Common format 3: Compact YYYYMMDDTHHMMSS
    m_compact = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$", cleaned)
    if m_compact:
        try:
            dt = datetime(
                int(m_compact.group(1)), int(m_compact.group(2)), int(m_compact.group(3)),
                int(m_compact.group(4)), int(m_compact.group(5)), int(m_compact.group(6)),
                tzinfo=timezone.utc
            )
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    # General parser
    try:
        dt = dateutil_parser.parse(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def extract_sentinel1_acquisition_metadata(image_path: Optional[str], rasterio_tags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extracts Sentinel-1 acquisition timestamp and granule metadata from GeoTIFF tags,
    DIMAP XML (tag 65000), TIFF DateTime tags, sidecars, or Sentinel-1 naming conventions.
    Never invents or returns server/processing time.
    """
    meta_result: Dict[str, Any] = {
        "acquisition_timestamp": None,
        "observation_time_source": None,
        "granule_id": None,
    }

    if not image_path or not os.path.exists(image_path):
        return meta_result

    # 1. Check rasterio tags dictionary if passed or inspectable
    tags_to_check = dict(rasterio_tags or {})

    # Check key metadata tag names
    date_tag_keys = [
        "ACQUISITION_START_TIME",
        "PRODUCT_SCENE_RASTER_START_TIME",
        "SCENE_START_TIME",
        "START_TIME",
        "PRODUCT_START_TIME",
        "TIFFTAG_DATETIME",
        "DateTime",
        "acquisition_time",
        "ACQUISITION_DATETIME",
        "INGESTION_DATE",
        "DATE_ACQUIRED",
        "TIME_START",
    ]
    for k in date_tag_keys:
        for tag_k, tag_v in tags_to_check.items():
            if k.lower() == str(tag_k).lower() and tag_v:
                parsed_ts = _parse_timestamp_string(str(tag_v))
                if parsed_ts:
                    meta_result["acquisition_timestamp"] = parsed_ts
                    meta_result["observation_time_source"] = "sentinel_metadata"
                    break
        if meta_result["acquisition_timestamp"]:
            break

    # 2. Check XML / DIMAP metadata in tag 65000 or tifffile tags
    try:
        import tifffile
        with tifffile.TiffFile(image_path) as tif:
            page = tif.pages[0]
            if 65000 in page.tags:
                xml_text = str(page.tags[65000].value)
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(xml_text)
                    doc_name = root.attrib.get("name", "")
                    if doc_name and not meta_result["granule_id"]:
                        meta_result["granule_id"] = doc_name.replace("subset_0_of_", "").replace(".dim", "")
                    prod = root.find("Production")
                    if prod is not None:
                        for tag_name in ["PRODUCT_SCENE_RASTER_START_TIME", "PRODUCT_START_TIME", "SCENE_RASTER_START_TIME"]:
                            elem = prod.find(tag_name)
                            if elem is not None and elem.text:
                                parsed = _parse_timestamp_string(elem.text)
                                if parsed and not meta_result["acquisition_timestamp"]:
                                    meta_result["acquisition_timestamp"] = parsed
                                    meta_result["observation_time_source"] = "sentinel_metadata"
                                    break
                except Exception as xml_err:
                    logger.debug(f"DIMAP XML parse notice: {xml_err}")

            # Check tag 306 (DateTime)
            if not meta_result["acquisition_timestamp"] and 306 in page.tags:
                parsed = _parse_timestamp_string(str(page.tags[306].value))
                if parsed:
                    meta_result["acquisition_timestamp"] = parsed
                    meta_result["observation_time_source"] = "sentinel_metadata"
    except Exception as tiff_err:
        logger.debug(f"tifffile inspection notice for {image_path}: {tiff_err}")

    # 3. Check sidecar .dim or .xml files
    if not meta_result["acquisition_timestamp"]:
        base_no_ext, _ = os.path.splitext(image_path)
        for sidecar_ext in [".dim", ".xml", ".DIM", ".XML"]:
            sidecar_path = base_no_ext + sidecar_ext
            if os.path.exists(sidecar_path):
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(sidecar_path)
                    root = tree.getroot()
                    prod = root.find("Production")
                    if prod is not None:
                        t_start = prod.find("PRODUCT_SCENE_RASTER_START_TIME")
                        if t_start is not None and t_start.text:
                            parsed = _parse_timestamp_string(t_start.text)
                            if parsed:
                                meta_result["acquisition_timestamp"] = parsed
                                meta_result["observation_time_source"] = "sentinel_metadata"
                                break
                except Exception:
                    pass

    # 4. Check filename / path for Sentinel-1 naming convention
    # e.g. S1A_IW_GRDH_1SDV_20180803T172551_20180803T172608_023085_0281B1_DB30
    import re
    fn = os.path.basename(image_path)
    s1_match = re.search(r"S1[AB]_[A-Z0-9]{2}_[A-Z0-9]{4}_[A-Z0-9]{4}_(\d{8}T\d{6})_(\d{8}T\d{6})", fn)
    if s1_match:
        if not meta_result["granule_id"]:
            meta_result["granule_id"] = s1_match.group(0)
        if not meta_result["acquisition_timestamp"]:
            start_str = s1_match.group(1)
            parsed = _parse_timestamp_string(start_str)
            if parsed:
                meta_result["acquisition_timestamp"] = parsed
                meta_result["observation_time_source"] = "sentinel_metadata"

    return meta_result


def inspect_image_geospatial(image_path: Optional[str]) -> Dict[str, Any]:
    """
    Inspects an image file to determine if it is a GeoTIFF with valid geospatial metadata.
    Also extracts Sentinel-1 acquisition timestamp and granule identification.

    Returns:
        Dict with keys:
            is_geotiff (bool): True if file has a TIFF extension and is readable by rasterio.
            has_crs (bool): True if valid, non-identity geospatial CRS and transform exist.
            crs (Optional[str]): Source CRS string (e.g. 'EPSG:4326', 'EPSG:32643').
            transform: rasterio Affine transform object if available.
            bounds: Tuple of (left, bottom, right, top) in source CRS.
            width: Image width in pixels.
            height: Image height in pixels.
            acquisition_timestamp: Normalized UTC ISO-8601 acquisition time if available.
            observation_time_source: "sentinel_metadata" if found, else None.
            granule_id: Sentinel-1 product ID if present.
            reason: Explanatory string.
    """
    result: Dict[str, Any] = {
        "is_geotiff": False,
        "has_crs": False,
        "crs": None,
        "transform": None,
        "bounds": None,
        "width": 0,
        "height": 0,
        "acquisition_timestamp": None,
        "observation_time_source": None,
        "granule_id": None,
        "reason": "no_image_provided",
    }

    if not image_path or not os.path.exists(image_path):
        return result

    ext = os.path.splitext(image_path)[1].lower()
    if ext not in (".tif", ".tiff"):
        result["reason"] = "non_tiff_format"
        return result

    if not _RASTERIO_AVAILABLE or not _PYPROJ_AVAILABLE:
        result["is_geotiff"] = True
        result["reason"] = "geospatial_libraries_unavailable"
        return result

    try:
        with rasterio.open(image_path) as src:
            result["is_geotiff"] = True
            result["width"] = src.width
            result["height"] = src.height

            # Extract acquisition timestamp from rasterio tags + metadata
            tags = src.tags()
            s1_meta = extract_sentinel1_acquisition_metadata(image_path, rasterio_tags=tags)
            result["acquisition_timestamp"] = s1_meta["acquisition_timestamp"]
            result["observation_time_source"] = s1_meta["observation_time_source"]
            result["granule_id"] = s1_meta["granule_id"]

            # Check if CRS is defined
            if src.crs is None:
                result["has_crs"] = False
                result["reason"] = "tiff_missing_crs"
                return result

            # Check if transform is merely the default unreferenced identity matrix
            t = src.transform
            if t.a == 1.0 and t.b == 0.0 and t.c == 0.0 and t.d == 0.0 and t.e == 1.0 and t.f == 0.0:
                result["has_crs"] = False
                result["reason"] = "tiff_identity_transform"
                return result

            result["has_crs"] = True
            result["crs"] = str(src.crs)
            result["transform"] = t
            result["bounds"] = src.bounds
            result["reason"] = "valid_geotiff"
            return result

    except Exception as exc:
        logger.warning(f"Failed to inspect GeoTIFF metadata for {image_path}: {exc}")
        result["is_geotiff"] = True
        result["has_crs"] = False
        result["reason"] = f"read_error: {str(exc)}"
        # Attempt metadata extraction even if rasterio failed
        s1_meta = extract_sentinel1_acquisition_metadata(image_path)
        result["acquisition_timestamp"] = s1_meta["acquisition_timestamp"]
        result["observation_time_source"] = s1_meta["observation_time_source"]
        result["granule_id"] = s1_meta["granule_id"]
        return result


def pixel_to_wgs84(
    transform: Any,
    source_crs: Any,
    pixel_x: float,
    pixel_y: float
) -> Tuple[float, float]:
    """
    Converts a pixel coordinate (col=x, row=y) into WGS84 (latitude, longitude)
    using the raster's affine transform and projecting from source CRS to EPSG:4326.

    Returns:
        (latitude, longitude) rounded to 6 decimal places.
    """
    # rasterio.transform.xy takes (transform, row, col) -> (x, y in source CRS)
    proj_x, proj_y = xy(transform, pixel_y, pixel_x)

    crs_str = str(source_crs).upper()
    if crs_str in ("EPSG:4326", "WGS84", "OGC:CRS84"):
        # Already geographic WGS84: proj_x is longitude, proj_y is latitude
        return round(float(proj_y), 6), round(float(proj_x), 6)

    # Transform to EPSG:4326
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(proj_x, proj_y)
    return round(float(lat), 6), round(float(lon), 6)


def contour_to_wgs84_polygon(
    transform: Any,
    source_crs: Any,
    approx_contour: np.ndarray
) -> Dict[str, Any]:
    """
    Converts a 2D contour array of pixel coordinates into a valid GeoJSON Polygon
    with coordinates in WGS84 [longitude, latitude].
    """
    geo_coords = []
    for pt in approx_contour:
        px = float(pt[0][0])
        py = float(pt[0][1])
        lat, lon = pixel_to_wgs84(transform, source_crs, px, py)
        geo_coords.append([lon, lat])

    # Ensure polygon ring is closed
    if geo_coords and geo_coords[0] != geo_coords[-1]:
        geo_coords.append(geo_coords[0])

    return {
        "type": "Polygon",
        "coordinates": [geo_coords]
    }
