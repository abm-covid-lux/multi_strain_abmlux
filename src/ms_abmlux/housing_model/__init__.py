"""Base class for all labour models.

This class is used to represent models of labour market dynamics.
"""

import logging

from ms_abmlux.component import Component

log = logging.getLogger("housing_model")

class HousingModel(Component):
    """Represents housing within the system"""

    def __init__(self, config, activity_manager):

        super().__init__(config)

        self.activity_manager = activity_manager
