"""Tools for representing locations on the world.

Locations have a type and coordinates in space."""

# Allows classes to return their own type, e.g. from_file below
from __future__ import annotations

import uuid
from math import sqrt

from pyproj import Transformer

# Keep these between runs.  This brings a significant performance improvement
# 4326 is the EPSG identifier of WGS84
# 3035 is the EPSG identifier of ETRS89
_transform_ETRS89_to_WGS84 = Transformer.from_crs('epsg:3035', 'epsg:4326')
_transform_WGS84_to_ETRS89 = Transformer.from_crs('epsg:4326', 'epsg:3035')

LocationTuple = tuple[float, float]

class Location:
    """Represents a location to the system"""

    def __init__(self, typ: str, coord: LocationTuple):
        """Represents a location on the world.

        Parameters:
          typ (str): The type of location, as a string
          etrs89_coord (tuple):2-tuple with x, y grid coordinates in ETRS89 format
        """

        # Unique identifier
        self.uuid      = uuid.uuid4().hex
        # The type of location, for example House, Restaurant etc
        self.typ       = typ

        # Spatial coordinates of the location
        self.coord     = coord
        self.wgs84     = ETRS89_to_WGS84(self.coord)

    def distance_euclidean_m(self, other: Location) -> float:
        """Return the distance between the two locations in metres."""

        return sqrt(((self.coord[0]-other.coord[0])**2) + ((self.coord[1]-other.coord[1])**2))

    def __str__(self):
        return f"{self.typ}[{self.uuid}]"

# pylint: disable=invalid-name
def ETRS89_to_WGS84(coord: LocationTuple) -> LocationTuple:
    """Convert from ABMLUX grid format (actually ETRS89) to lat, lon in WGS84 format"""

    return _transform_ETRS89_to_WGS84.transform(coord[1], coord[0])

def WGS84_to_ETRS89(coord: LocationTuple) -> LocationTuple:
    """Convert from lat, lon in WGS84 format to ABMLUX' grid format (ETRS89)"""
    # FIXME: this is inconsistent with ETRS89_to_WGS84, taking lat/lon instead of a tuple

    latitude, longitude = coord
    return _transform_WGS84_to_ETRS89.transform(latitude, longitude)
