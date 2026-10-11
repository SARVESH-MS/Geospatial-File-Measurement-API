"""Unit tests for Shapefile and KML parsers, including corrupted file and security testing."""

import io
from pathlib import Path
import zipfile
import pytest

from app.core.exceptions import CorruptedFileError, SecurityViolationError
from app.services.kml_parser import KMLParser
from app.services.shapefile_parser import ShapefileParser


def test_parse_sample_shapefile(sample_shapefile_path: Path):
    assert sample_shapefile_path.exists()
    crs, features = ShapefileParser.parse_zip(sample_shapefile_path)

    assert crs == "EPSG:4326"
    assert len(features) == 2
    assert features[0]["geometry_type"] == "Polygon"
    assert "properties" in features[0]
    assert features[0]["properties"]["name"] == "Alpha Sector Parcel"


def test_parse_sample_kml(sample_kml_path: Path):
    assert sample_kml_path.exists()
    crs, features = KMLParser.parse_file(sample_kml_path)

    assert crs == "EPSG:4326"
    assert len(features) == 3

    geom_types = [f["geometry_type"] for f in features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types


def test_shapefile_missing_shp(tmp_path: Path):
    bad_zip = tmp_path / "missing_shp.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("test.txt", "not a shapefile")

    with pytest.raises(CorruptedFileError):
        ShapefileParser.parse_zip(bad_zip)


def test_shapefile_corrupted_archive(tmp_path: Path):
    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"not a real zip file header content")

    with pytest.raises(CorruptedFileError):
        ShapefileParser.parse_zip(corrupt_zip)


def test_shapefile_zip_slip_rejection(tmp_path: Path):
    malicious_zip = tmp_path / "zip_slip.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../evil.shp", "malicious payload")

    with pytest.raises(SecurityViolationError):
        ShapefileParser.parse_zip(malicious_zip)


def test_kml_malformed_xml(tmp_path: Path):
    bad_kml = tmp_path / "bad.kml"
    bad_kml.write_text("<kml><Document><unclosed_tag></kml>", encoding="utf-8")

    with pytest.raises(CorruptedFileError):
        KMLParser.parse_file(bad_kml)
