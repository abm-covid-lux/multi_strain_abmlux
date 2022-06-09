"""Base class for all transport models.

This class is used to represent models of private and public transport.
"""

import logging

from ms_abmlux.component import Component

log = logging.getLogger("transport_model")

class TransportModel(Component):
    """Represents private and public transport within the system"""

    def __init__(self, config, activity_manager):

        super().__init__(config)

        self.activity_manager = activity_manager
