"""KML file parser supporting safe XML parsing, Placemarks, Polygons, LineStrings, and Points."""

import logging
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element
import defusedxml.ElementTree as dET
import shapely
import shapely.geometry

from app.core.exceptions import CorruptedFileError
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class KMLParser:
    """Parses OGC KML documents into structured geospatial features."""

    KML_DEFAULT_CRS = CRSService.DEFAULT_GEOGRAPHIC_CRS

    @classmethod
    def parse_file(cls, kml_file_path: Path) -> tuple[str, list[dict[str, Any]]]:
        """Parses a KML file into features and standard CRS."""
        try:
            tree = dET.parse(str(kml_file_path))
            root = tree.getroot()
        except Exception as e:
            logger.error("Failed to parse KML XML document: %s", e, exc_info=True)
            raise CorruptedFileError(f"Uploaded file is not a valid or readable KML XML document: {str(e)}") from e

        features = cls._extract_features(root)
        return cls.KML_DEFAULT_CRS, features

    @classmethod
    def _strip_ns(cls, tag: str) -> str:
        """Strip XML namespace prefix from tag name."""
        return tag.split("}")[-1] if "}" in tag else tag

    @classmethod
    def _find_child(cls, elem: Element, tag_name: str) -> Element | None:
        """Find immediate child element matching tag_name, ignoring XML namespaces."""
        for child in elem:
            if cls._strip_ns(child.tag) == tag_name:
                return child
        return None

    @classmethod
    def _parse_coordinates(cls, coord_text: str | None) -> list[tuple[float, float]]:
        """Parses KML coordinate text into a list of (lon, lat) tuples."""
        if not coord_text:
            return []

        coords: list[tuple[float, float]] = []
        tokens = coord_text.strip().split()
        for token in tokens:
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    @classmethod
    def _parse_polygon(cls, poly_elem: Element) -> shapely.Polygon | None:
        """Parses a KML Polygon element including outer boundary and optional inner rings."""
        shell_coords: list[tuple[float, float]] = []
        holes_coords: list[list[tuple[float, float]]] = []

        for child in poly_elem:
            tag = cls._strip_ns(child.tag)
            if tag == "outerBoundaryIs":
                ring = cls._find_child(child, "LinearRing")
                if ring is not None:
                    coord_elem = cls._find_child(ring, "coordinates")
                    if coord_elem is not None and coord_elem.text:
                        shell_coords = cls._parse_coordinates(coord_elem.text)
            elif tag == "innerBoundaryIs":
                ring = cls._find_child(child, "LinearRing")
                if ring is not None:
                    coord_elem = cls._find_child(ring, "coordinates")
                    if coord_elem is not None and coord_elem.text:
                        hole = cls._parse_coordinates(coord_elem.text)
                        if len(hole) >= 3:
                            holes_coords.append(hole)

        if len(shell_coords) < 3:
            return None

        try:
            poly = shapely.Polygon(shell_coords, holes=holes_coords if holes_coords else None)
            return shapely.make_valid(poly) if not poly.is_valid else poly
        except Exception as e:
            logger.warning("Error creating Polygon: %s", e)
            return None

    @classmethod
    def _parse_geometry(cls, elem: Element) -> shapely.Geometry | None:
        """Parses individual or composite geometries from a KML element."""
        tag = cls._strip_ns(elem.tag)

        if tag == "Point":
            coord_elem = cls._find_child(elem, "coordinates")
            if coord_elem is not None and coord_elem.text:
                coords = cls._parse_coordinates(coord_elem.text)
                if coords:
                    return shapely.Point(coords[0])

        elif tag == "LineString":
            coord_elem = cls._find_child(elem, "coordinates")
            if coord_elem is not None and coord_elem.text:
                coords = cls._parse_coordinates(coord_elem.text)
                if len(coords) >= 2:
                    return shapely.LineString(coords)

        elif tag == "Polygon":
            return cls._parse_polygon(elem)

        elif tag == "MultiGeometry":
            sub_geoms: list[shapely.Geometry] = []
            for sub in elem:
                g = cls._parse_geometry(sub)
                if g is not None and not g.is_empty:
                    sub_geoms.append(g)

            if not sub_geoms:
                return None

            types = {g.geom_type for g in sub_geoms}
            if types == {"Polygon"}:
                return shapely.MultiPolygon(sub_geoms)
            if types == {"LineString"}:
                return shapely.MultiLineString(sub_geoms)
            if types == {"Point"}:
                return shapely.MultiPoint(sub_geoms)

            return shapely.GeometryCollection(sub_geoms)

        return None

    @classmethod
    def _extract_placemark_attributes(cls, placemark: Element) -> dict[str, Any]:
        """Extracts metadata properties from a Placemark."""
        props: dict[str, Any] = {}

        name_elem = cls._find_child(placemark, "name")
        if name_elem is not None and name_elem.text:
            props["name"] = name_elem.text.strip()

        desc_elem = cls._find_child(placemark, "description")
        if desc_elem is not None and desc_elem.text:
            props["description"] = desc_elem.text.strip()

        ext_elem = cls._find_child(placemark, "ExtendedData")
        if ext_elem is not None:
            for child in ext_elem:
                ctag = cls._strip_ns(child.tag)
                if ctag == "Data":
                    key = child.get("name")
                    val_elem = cls._find_child(child, "value")
                    if key and val_elem is not None and val_elem.text:
                        props[key] = val_elem.text.strip()
                elif ctag == "SimpleData":
                    key = child.get("name")
                    if key and child.text:
                        props[key] = child.text.strip()

        return props

    @classmethod
    def _extract_features(cls, root: Element) -> list[dict[str, Any]]:
        """Extracts all placemarks and their geometries from the KML document tree."""
        features: list[dict[str, Any]] = []
        feature_index = 0

        placemarks = [el for el in root.iter() if cls._strip_ns(el.tag) == "Placemark"]

        for pm in placemarks:
            props = cls._extract_placemark_attributes(pm)
            geom: shapely.Geometry | None = None

            for child in pm:
                ctag = cls._strip_ns(child.tag)
                if ctag in ("Point", "LineString", "Polygon", "MultiGeometry"):
                    geom = cls._parse_geometry(child)
                    if geom is not None:
                        break

            if geom is not None and not geom.is_empty:
                features.append({
                    "feature_index": feature_index,
                    "geometry_type": geom.geom_type,
                    "geometry": shapely.geometry.mapping(geom),
                    "shapely_geom": geom,
                    "crs": cls.KML_DEFAULT_CRS,
                    "properties": props,
                })
                feature_index += 1

        return features
