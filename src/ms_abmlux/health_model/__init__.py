"""Base class for all health models.

This class is used to represent models of health, including hospitals and medical centers.
"""

import logging

from ms_abmlux.component import Component

log = logging.getLogger("health_model")

class HealthModel(Component):
    """Represents private and public health within the system"""

    def __init__(self, config, activity_manager):

        super().__init__(config)

        self.activity_manager = activity_manager
