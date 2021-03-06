"""Represents the set of locations, and all agents in the world"""

from typing import Union

import ms_abmlux.utils as utils
from ms_abmlux.world.map import Map
from ms_abmlux.agent import Agent
from ms_abmlux.location import Location

class World:
    """Represents the set of locations, upon a map describing their relationship to real life.
    """

    def __init__(self, map_: Map):

        self.map: Map                  = map_
        self.agents: list[Agent]       = []
        self.locations: list[Location] = []
        self.scale_factor: float       = 1

        self.alpha = None
        self.beta  = None

        self.locations_by_type: dict[str, list[Location]] = {}
        self.location_types = list(self.locations_by_type.keys())

    def set_scale_factor(self, scale_factor: float) -> None:
        """Set the scale factor for this map: how does it relate to the population
        in the world it's modelling?"""

        if scale_factor <= 0:
            raise ValueError("Scale factor must be above 0")

        self.scale_factor = scale_factor

    def network_distance(self, euclidean_distance_km):
        """Converts a Euclidean distance into a network distance."""

        return (euclidean_distance_km * self.alpha) + self.beta

    def n_locations(self) -> int:
        """Return the number of locations in the world"""

        return len(self.locations)

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the world.

        Parameters:
            agent: The Agent object to add.
        """
        self.agents.append(agent)

    def add_location(self, location: Location) -> None:
        """Add a Location object to the world."""

        self.locations.append(location)

        if location.typ not in self.locations_by_type:
            self.locations_by_type[location.typ] = []

        self.locations_by_type[location.typ].append(location)

    def count(self, location_type: str) -> int:
        """Return the number of locations on this world of the type specified"""

        if location_type not in self.locations_by_type:
            return 0
        return len(self.locations_by_type[location_type])

    def locations_for_types(self, location_types: Union[str, list[str]]) -> list[Location]:
        """Return a list of allowable locations for all of the types given.

        location_types may be a string, or a list of strings."""

        if isinstance(location_types, str):
            location_types = [location_types]

        stuff = [self.locations_by_type[lt] for lt in location_types]
        return utils.flatten(stuff)
