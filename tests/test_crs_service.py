"""Unit tests for Coordinate Reference System (CRS) management and projection logic."""

import shapely
from app.services.crs_service import CRSService


def test_parse_crs_standard_and_fallbacks():
    assert CRSService.parse_crs("EPSG:4326") == "EPSG:4326"
    assert CRSService.parse_crs("4326") == "EPSG:4326"
    assert CRSService.parse_crs(None) == "EPSG:4326"
    assert CRSService.parse_crs("") == "EPSG:4326"
    assert CRSService.parse_crs("INVALID_CRS_XYZ") == "EPSG:4326"


def test_is_geographic():
    assert CRSService.is_geographic("EPSG:4326") is True
    assert CRSService.is_geographic("EPSG:32643") is False
    assert CRSService.is_geographic("EPSG:3857") is False


def test_determine_optimal_projected_crs_utm_zones():
    # Bangalore (lon: 77.59, lat: 12.97) -> UTM Zone 43 North -> EPSG:32643
    bengaluru_poly = shapely.Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98)])
    crs_bengaluru = CRSService.determine_optimal_projected_crs(bengaluru_poly, "EPSG:4326")
    assert crs_bengaluru == "EPSG:32643"

    # New York (lon: -74.00, lat: 40.71) -> UTM Zone 18 North -> EPSG:32618
    nyc_point = shapely.Point(-74.00, 40.71)
    crs_nyc = CRSService.determine_optimal_projected_crs(nyc_point, "EPSG:4326")
    assert crs_nyc == "EPSG:32618"

    # Sydney (lon: 151.20, lat: -33.86) -> UTM Zone 56 South -> EPSG:32756
    sydney_line = shapely.LineString([(151.20, -33.86), (151.21, -33.87)])
    crs_sydney = CRSService.determine_optimal_projected_crs(sydney_line, "EPSG:4326")
    assert crs_sydney == "EPSG:32756"


def test_polar_crs_selection():
    # Arctic North (> 84°N)
    arctic_poly = shapely.Polygon([(10.0, 85.0), (10.1, 85.0), (10.1, 85.1), (10.0, 85.1)])
    assert CRSService.determine_optimal_projected_crs(arctic_poly, "EPSG:4326") == "EPSG:32661"

    # Antarctic South (< -80°S)
    antarctic_poly = shapely.Polygon([(0.0, -85.0), (0.1, -85.0), (0.1, -85.1), (0.0, -85.1)])
    assert CRSService.determine_optimal_projected_crs(antarctic_poly, "EPSG:4326") == "EPSG:32761"


def test_transform_to_crs_metric_dimensions():
    # 0.001 deg approx ~111m
    poly_deg = shapely.Polygon([(77.590, 12.970), (77.591, 12.970), (77.591, 12.971), (77.590, 12.971)])
    projected = CRSService.transform_to_crs(poly_deg, "EPSG:4326", "EPSG:32643")

    # In UTM meters, area should be ~12,000 m² (not 0.000001 deg²)
    assert 11_000 < projected.area < 13_000
