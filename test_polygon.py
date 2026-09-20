import shapely.geometry
from shapely.geometry import Point as ShapelyPoint

def test_polygon():
    coords = [
        [
            [1.5999, 40.7506],
            [2.9120, 40.7506],
            [2.9120, 42.2494],
            [1.5999, 42.2494],
            [1.5999, 40.7506]
        ]
    ]
    polygon = shapely.geometry.Polygon(coords[0])
    
    lon, lat = 2.7, 41.6
    pt = ShapelyPoint(lon, lat)
    
    inside = polygon.covers(pt)
    print(f"Point {lon}, {lat} inside polygon? {inside}")

if __name__ == "__main__":
    test_polygon()
