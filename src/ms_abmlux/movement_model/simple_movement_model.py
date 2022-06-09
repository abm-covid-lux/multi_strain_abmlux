"""Simple random location selection."""

import logging

from ms_abmlux.movement_model import MovementModel

log = logging.getLogger("simple_movement_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleMovementModel(MovementModel):
    """Uses simple random sampling to select locations in response to activity changes."""

    def __init__(self, config, activity_manager, world):
        """Determines any necessary augmentations of the world that relate to agent movement"""
        super().__init__(config, activity_manager)

        # Moving to public transport is a special case
        self.no_move_states         = self.config['no_move_health_states']
        self.pt_activity_type_int   = activity_manager.as_int(config['pt_activity_type'])
        self.pt_loc_type            = config['pt_location_type']
        self.public_transport_units = world.locations_for_types(self.pt_loc_type)

        # Assign initial locations
        for agent in world.agents:
            allowed_locations = agent.locations_for_activity(agent.current_activity)
            new_location = self.prng.random_choice(list(allowed_locations))
            agent.set_location(new_location)

    def init_sim(self, sim):
        super().init_sim(sim)

        self.pt_units_available = sim.transport_model.units_available

        self.bus.subscribe("request.agent.activity", self.handle_activity_change, self)
        self.bus.subscribe("notify.pt.availability", self.update_pt_unit_availability, self)

    def update_pt_unit_availability(self, pt_units_available):
        """Update public transport unit availability"""

        self.pt_units_available = pt_units_available

    def handle_activity_change(self, agent, new_activity):
        """Respond to an activity by sending location change requests."""

        # If agent is hospitalised or dead, don't change location in response to new activity
        if agent.health not in self.no_move_states:
            if new_activity == self.pt_activity_type_int:
                allowable_locations = self.public_transport_units[0:self.pt_units_available]
                self.bus.publish("request.agent.location", agent, \
                self.prng.random_choice(list(allowable_locations)))
            else:
                allowable_locations = agent.locations_for_activity(new_activity)
                self.bus.publish("request.agent.location", agent, \
                self.prng.random_choice(list(allowable_locations)))
