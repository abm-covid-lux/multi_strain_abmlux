"""Represents educational facilities in the system."""

from __future__ import annotations

import uuid

LocationTuple = tuple[float, float]

class School:

    def __init__(self, typ: str, coord: LocationTuple):
        """Represents an educational facility"""

        self.uuid  = uuid.uuid4().hex
        self.typ   = typ
        self.coord = coord

        # Lists of classrooms for each age
        self.classrooms = {}
