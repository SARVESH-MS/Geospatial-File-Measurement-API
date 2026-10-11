"""Unit tests for geometry measurement calculation across all types."""

import shapely
from app.services.measurement_service import MeasurementService


def test_polygon_area_calculation():
    # Polygon in WGS84
    poly = shapely.Polygon([(77.590, 12.970), (77.595, 12.970), (77.595, 12.974), (77.590, 12.974)])
    meas, proj_crs = MeasurementService.calculate_measurement(poly, "EPSG:4326")

    assert meas.supported is True
    assert meas.type == "area"
    assert meas.unit == "square_meters"
    assert meas.status == "CALCULATED"
    assert meas.value is not None
    assert meas.area == meas.value
    assert meas.geodesic_value is not None and meas.geodesic_value > 0
    assert meas.value > 100_000  # Physically realistic parcel area in m²
    assert "m²" in (meas.display or "")
    assert proj_crs == "EPSG:32643"


def test_multipolygon_area_calculation():
    p1 = shapely.Polygon([(77.590, 12.970), (77.592, 12.970), (77.592, 12.972), (77.590, 12.972)])
    p2 = shapely.Polygon([(77.595, 12.970), (77.597, 12.970), (77.597, 12.972), (77.595, 12.972)])
    mp = shapely.MultiPolygon([p1, p2])

    meas, proj_crs = MeasurementService.calculate_measurement(mp, "EPSG:4326")
    assert meas.supported is True
    assert meas.type == "area"
    assert meas.status == "CALCULATED"
    assert meas.value is not None and meas.value > 0


def test_linestring_length_calculation():
    # ~500m LineString
    line = shapely.LineString([(77.590, 12.970), (77.595, 12.974)])
    meas, proj_crs = MeasurementService.calculate_measurement(line, "EPSG:4326")

    assert meas.supported is True
    assert meas.type == "length"
    assert meas.unit == "meters"
    assert meas.status == "CALCULATED"
    assert meas.value is not None
    assert meas.length == meas.value
    assert meas.geodesic_value is not None and meas.geodesic_value > 0
    assert 500 < meas.value < 800  # meters
    assert "m" in (meas.display or "")


def test_multilinestring_length_calculation():
    l1 = shapely.LineString([(77.590, 12.970), (77.591, 12.970)])
    l2 = shapely.LineString([(77.592, 12.970), (77.593, 12.970)])
    ml = shapely.MultiLineString([l1, l2])

    meas, proj_crs = MeasurementService.calculate_measurement(ml, "EPSG:4326")
    assert meas.supported is True
    assert meas.type == "length"
    assert meas.status == "CALCULATED"
    assert meas.value is not None and meas.value > 0


def test_point_handling_graceful():
    # Per requirement: "Point: No measurement is required."
    point = shapely.Point(77.592, 12.971)
    meas, proj_crs = MeasurementService.calculate_measurement(point, "EPSG:4326")

    assert meas.supported is False
    assert meas.type is None
    assert meas.value is None
    assert meas.status == "NOT_APPLICABLE"
    assert proj_crs is None


def test_unsupported_geometry_graceful():
    # GeometryCollection or empty geometry should not crash
    p = shapely.Point(77.592, 12.971)
    l = shapely.LineString([(77.590, 12.970), (77.591, 12.971)])
    gc = shapely.GeometryCollection([p, l])

    meas, proj_crs = MeasurementService.calculate_measurement(gc, "EPSG:4326")
    assert meas.supported is False
    assert meas.status == "UNSUPPORTED"
    assert meas.value is None


def test_empty_geometry_graceful():
    empty_poly = shapely.Polygon()
    meas, proj_crs = MeasurementService.calculate_measurement(empty_poly, "EPSG:4326")
    assert meas.supported is False
    assert meas.status == "NOT_APPLICABLE"
