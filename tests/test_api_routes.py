"""Integration tests for all FastAPI REST endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "docs_url" in data
    assert "upload_endpoint" in data


def test_upload_and_measure_kml_flow(client: TestClient, sample_kml_path: Path):
    with open(sample_kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("survey.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert "id" in upload_data
    assert upload_data["filename"] == "survey.kml"
    assert upload_data["feature_count"] == 3
    assert upload_data["crs"] == "EPSG:4326"
    assert upload_data["status"] == "COMPLETED"

    file_id = upload_data["id"]

    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["filename"] == "survey.kml"
    assert info_data["feature_count"] == 3
    assert info_data["crs"] == "EPSG:4326"
    assert info_data["status"] == "COMPLETED"

    info_no_slash = client.get(f"/api/files/{file_id}")
    assert info_no_slash.status_code == 200
    assert info_no_slash.json()["id"] == file_id

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()

    assert meas_data["id"] == file_id
    assert meas_data["filename"] == "survey.kml"
    assert meas_data["crs"] == "EPSG:4326"
    assert len(meas_data["features"]) == 3

    summary = meas_data["summary"]
    assert summary["total_features"] == 3
    assert summary["polygon_count"] == 1
    assert summary["linestring_count"] == 1
    assert summary["point_count"] == 1
    assert summary["total_area_sq_meters"] > 0
    assert summary["total_length_meters"] > 0
    assert summary["total_area"] == summary["total_area_sq_meters"]
    assert summary["total_length"] == summary["total_length_meters"]

    features_by_type = {f["geometry_type"]: f for f in meas_data["features"]}

    poly_feat = features_by_type["Polygon"]
    assert poly_feat["feature_id"] is not None
    assert poly_feat["id"] is not None
    assert poly_feat["measurement"]["supported"] is True
    assert poly_feat["measurement"]["type"] == "area"
    assert poly_feat["measurement"]["unit"] == "square_meters"
    assert poly_feat["measurement"]["value"] > 0
    assert poly_feat["measurement"]["area"] == poly_feat["measurement"]["value"]
    assert poly_feat["projected_crs"] == "EPSG:32643"

    line_feat = features_by_type["LineString"]
    assert line_feat["feature_id"] is not None
    assert line_feat["id"] is not None
    assert line_feat["measurement"]["supported"] is True
    assert line_feat["measurement"]["type"] == "length"
    assert line_feat["measurement"]["unit"] == "meters"
    assert line_feat["measurement"]["value"] > 0
    assert line_feat["measurement"]["length"] == line_feat["measurement"]["value"]

    point_feat = features_by_type["Point"]
    assert point_feat["measurement"]["supported"] is False
    assert point_feat["measurement"]["type"] is None
    assert point_feat["measurement"]["value"] is None
    assert point_feat["measurement"]["status"] == "NOT_APPLICABLE"


def test_upload_and_measure_shapefile_flow(client: TestClient, sample_shapefile_path: Path):
    with open(sample_shapefile_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("survey_parcels.zip", f, "application/zip")},
        )

    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    file_id = upload_data["id"]
    assert upload_data["feature_count"] == 2
    assert upload_data["status"] == "COMPLETED"

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()

    assert len(meas_data["features"]) == 2
    for feat in meas_data["features"]:
        assert feat["geometry_type"] == "Polygon"
        assert feat["measurement"]["supported"] is True
        assert feat["measurement"]["type"] == "area"
        assert feat["measurement"]["value"] > 0
        assert "Alpha Sector Parcel" in str(feat["properties"]) or "Beta Sector Parcel" in str(feat["properties"])


def test_nonexistent_file_returns_404(client: TestClient):
    response = client.get("/api/files/nonexistent_id_999/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"


def test_unsupported_file_extension_returns_400(client: TestClient):
    response = client.post(
        "/api/files/",
        files={"file": ("unsupported_doc.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_FORMAT"
