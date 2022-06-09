"""Represents the intervention of symptomatic quarantining."""

import logging

from ms_abmlux.sim_time import DeferredEventPool
from ms_abmlux.interventions import Intervention
from ms_abmlux.messagebus import MessageBus

log = logging.getLogger("symptomatic_quarantine")

# This file uses callbacks and interfaces which make this hit many false positives
#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SymptomaticQuarantine(Intervention):
    """Intervention that applies quarantine rules.

    Symptomatic agents are forced to return to certain locations when they request to move."""

    def init_sim(self, sim):
        super().init_sim(sim)

        self.clock = sim.clock

        self.default_duration_days  = self.config['default_duration_days']
        self.default_duration_ticks = int(self.clock.days_to_ticks(self.default_duration_days))
        self.location_blacklist     = self.config['location_blacklist']
        self.home_activity_type     = sim.activity_manager.as_int(self.config['home_activity_type'])
        self.symptomatic_states     = self.config['symptomatic_states']
        self.asymptomatic_states    = self.config['asymptomatic_states']

        self.prob_quarantine_symptomatic = self.config['prob_quarantine_symptomatic']
        self.prob_quarantine_asymptomatic = self.config['prob_quarantine_asymptomatic']

        self.end_quarantine_events = DeferredEventPool(self.bus, self.clock)
        self.agent_in_quarantine  = {}
        for agent in sim.world.agents:
            self.agent_in_quarantine[agent] = False

        self.bus.subscribe("request.quarantine.stop", self.handle_end_quarantine, self)
        self.bus.subscribe("request.agent.location", self.handle_location_change, self)
        self.bus.subscribe("notify.agent.health", self.handle_health_change, self)

    def handle_health_change(self, agent, old_health):
        """When an agent changes health state to a symptomatic state, they enter quarantine."""

        if not self.enabled:
            return

        # If no change, skip
        if old_health == agent.health:
            return

        # If moving from an asymptomatic state to a symtomatic state
        if old_health not in self.symptomatic_states and agent.health in self.symptomatic_states:
            if self.prng.boolean(self.prob_quarantine_symptomatic):
                self.agent_in_quarantine[agent] = True
                self.end_quarantine_events.add("request.quarantine.stop", \
                                               self.default_duration_ticks, agent)

        # If moving from to an asymptomatic state
        if old_health not in self.asymptomatic_states and agent.health in self.asymptomatic_states:
            if self.prng.boolean(self.prob_quarantine_asymptomatic):
                self.agent_in_quarantine[agent] = True
                self.end_quarantine_events.add("request.quarantine.stop", \
                                               self.default_duration_ticks, agent)

    def handle_end_quarantine(self, agent):
        """Queues up agents to end quarantine next time quarantine status is updated."""

        self.agent_in_quarantine[agent] = False
        return MessageBus.CONSUME

    def handle_location_change(self, agent, new_location):
        """Catch any location changes that will move quarantined agents out of their home,
        and rebroadcast an event to move them home again.
        """

        if self.agent_in_quarantine[agent]:
            home_location = agent.locations_for_activity(self.home_activity_type)[0]
            if new_location != home_location:
                if new_location.typ not in self.location_blacklist:
                    self.bus.publish("request.agent.location", agent, home_location)
                    return MessageBus.CONSUME
