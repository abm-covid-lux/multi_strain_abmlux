"""Represents a vaccine."""

from __future__ import annotations

class Vaccine:
    """Represents a vaccine"""

    def __init__(self, name, second_dose_needed, time_between_doses, prob_first_dose_successful,
                 prob_second_dose_successful, targetted_strains, duration):

        self.name                        = name
        self.second_dose_needed          = second_dose_needed
        self.time_between_doses          = time_between_doses
        self.prob_first_dose_successful  = prob_first_dose_successful
        self.prob_second_dose_successful = prob_second_dose_successful
        self.targetted_strains           = targetted_strains
        self.duration                    = duration
