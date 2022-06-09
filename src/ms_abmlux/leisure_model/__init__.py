"""Base class for all leisure models."""

import logging

from ms_abmlux.component import Component

log = logging.getLogger("leisure_model")

class LeisureModel(Component):
    """Represents leisure within the system"""

    def __init__(self, config, activity_manager):

        super().__init__(config)

        self.activity_manager = activity_manager
