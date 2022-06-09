"""Representations of a single agent within the system"""

import logging
import uuid
from collections.abc import Iterable
from typing import Union, Optional

from ms_abmlux.location import Location

log = logging.getLogger("agent")

class Agent:
    """Represents a single agent within the simulation"""

    def __init__(self, age: int, region: str, current_location: Union[None, Location]=None):

        # Unique indentifier for each agent
        self.uuid = uuid.uuid4().hex
        # Age of agent
        self.age: int = age
        # Region in which agent in resident
        self.region: str = region
        # Where the agent might perform various activities
        self.activity_locations: dict[str, list[Location]] = {}

        # Whether or not the agent wants to work
        self.work_behaviour_type: bool = False
        # Whether or not the agent wants to go to school
        self.school_behaviour_type: bool = False

        # Current state
        self.current_activity: Optional[str]       = None
        self.current_location: Optional[Location]  = current_location
        self.health: Optional[str]                 = None
        self.current_employment: Optional[str]     = None

    def locations_for_activity(self, activity: str) -> list[Location]:
        """Return a list of locations this agent can go to for
        the activity given"""

        if activity not in self.activity_locations:
            return []

        return self.activity_locations[activity]

    def add_activity_location(self, activity: str, location: Location) -> None:
        """Add a location to the list allowed for a given activity

        Parameters:
            activity: The activity that will be performed
            location: A single location, or a list of locations.
        """

        if activity not in self.activity_locations:
            self.activity_locations[activity] = []

        # Ensure we can join the lists together if given >1 item
        location_list: list[Location]
        if isinstance(location, Iterable):
            location_list = list(location)
        else:
            location_list = [location]

        self.activity_locations[activity] += location_list

    def set_health(self, health: str) -> None:
        """Sets the agent as having the given health state"""

        log.debug("Agent %s: Health %s -> %s", self.uuid, self.health, health)
        self.health = health

    def set_activity(self, activity: str) -> None:
        """Sets the agent as performing the activity given"""

        log.debug("Agent %s: Activity %s -> %s", self.uuid, self.current_activity, activity)
        self.current_activity = activity

    def set_location(self, location: Location) -> None:
        """Sets the agent as being in the location specified"""

        log.debug("Agent %s: Location %s -> %s", self.uuid, self.current_location, location)
        self.current_location = location

    def set_employment(self, employment: str) -> None:
        """Sets the employment status of the agent"""

        log.debug("Agent %s: Employment %s -> %s", self.uuid, self.current_employment, employment)
        self.current_employment = employment

    def __str__(self):
        return (f"<Agent {self.uuid}; age={self.age}, "
                f"activities={len(self.activity_locations)}, "
                f"current_loc={self.current_location}>")
