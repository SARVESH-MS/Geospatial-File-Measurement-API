"""Utility script to generate sample geospatial test data (KML and Zipped Shapefile)."""

from pathlib import Path
import zipfile
import shapefile


def generate_samples():
    sample_dir = Path(__file__).resolve().parent.parent / "sample_data"
    sample_dir.mkdir(exist_ok=True)

    # 1. Generate Shapefile with Polygon and Line features
    shp_base = sample_dir / "survey_parcels"
    w = shapefile.Writer(str(shp_base), shapeType=shapefile.POLYGON)
    w.field("name", "C", size=50)
    w.field("zone_type", "C", size=30)
    w.field("parcel_id", "N", decimal=0)

    # Add Polygon 1 (Bangalore urban parcel)
    w.poly([
        [
            [77.5900, 12.9700],
            [77.5950, 12.9700],
            [77.5950, 12.9740],
            [77.5900, 12.9740],
            [77.5900, 12.9700],
        ]
    ])
    w.record("Alpha Sector Parcel", "Commercial", 101)

    # Add Polygon 2 (Adjacent parcel)
    w.poly([
        [
            [77.5960, 12.9700],
            [77.6000, 12.9700],
            [77.6000, 12.9740],
            [77.5960, 12.9740],
            [77.5960, 12.9700],
        ]
    ])
    w.record("Beta Sector Parcel", "Residential", 102)

    w.close()

    # Write WGS84 .prj file
    prj_wkt = (
        'GEOGCS["GCS_WGS_1984",'
        'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],'
        'UNIT["Degree",0.0174532925199433]]'
    )
    prj_file = sample_dir / "survey_parcels.prj"
    prj_file.write_text(prj_wkt, encoding="utf-8")

    # Create ZIP archive
    zip_path = sample_dir / "sample_shapefile.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_pack = sample_dir / f"survey_parcels{ext}"
            zipf.write(file_to_pack, arcname=file_to_pack.name)
            file_to_pack.unlink()

    print(f"Generated {zip_path} (size: {zip_path.stat().st_size} bytes)")


if __name__ == "__main__":
    generate_samples()
