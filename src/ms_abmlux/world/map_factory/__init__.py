"""Superclass of all classes that output a map."""

from ms_abmlux.world.map import Map

class MapFactory:
    """Outputs an ms_abmlux.Map object.

    Maps go on to be used in creating a world, which represents Agents and Locations.
    """

    def get_map(self) -> Map:
        """Return a map"""
