"""Represents a virus strain."""

from __future__ import annotations

class Strain:
    """Represents a virus strain"""

    def __init__(self, name, transmission_probability, labelled_profiles_by_age, step_size,
                 durations_by_profile):

        self.name                     = name
        self.transmission_probability = transmission_probability # maps 1-letter profiles to floats
        self.labelled_profiles_by_age = labelled_profiles_by_age
        self.step_size                = step_size
        self.durations_by_profile     = durations_by_profile
