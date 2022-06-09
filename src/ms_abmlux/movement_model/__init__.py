"""Manages location choice within the model, that is, where agents perform the activities
they are assigned."""

from ms_abmlux.component import Component

class MovementModel(Component):
    """Defines the location finding behaviour of agents.

    Subclasses are expected to select a location for agents during the simulation, responding to
    activity events and selecting an appropriate location for the agent to perform that activity.
    """

    def __init__(self, config, activity_manager):

        super().__init__(config)

        self.activity_manager = activity_manager
