"""Multi-strain disease model"""

import logging
from collections import defaultdict
import numpy as np
import math

from ms_abmlux.disease_model import DiseaseModel
from ms_abmlux.disease_model.strain import Strain

log = logging.getLogger("multi_strain_disease_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class MultiStrainDiseaseModel(DiseaseModel):
    """Represents an infectious disease consisting of multiple strains"""

    def __init__(self, config, world, clock):
        super().__init__(config, config['health_states'])

        # Fundamental health states
        self.susceptible_state = config['susceptible_state'] # str
        self.infected_states   = config['infected_states'] # list
        self.dead_state        = config['dead_state'] # str

        # A list of all strains appearing in the model
        self.strains = []
        self.strains_by_name = {}

        # How many initial infections for each strain
        self.num_initial_cases = {} # num_initial_cases[strain]: int

        # Initialize the strains
        for strain in config['strains']:
            labels = config['strains'][strain]['disease_profile_list']
            profiles = config['strains'][strain]['disease_profile_distribution_by_age']
            labelled_profiles_by_age = {}
            for age in profiles:
                labelled_profiles_by_age[age] = {k:v for k,v in zip(labels, profiles[age])}
            new_strain = Strain(strain,
                                config['strains'][strain]['transmission_probability'],
                                labelled_profiles_by_age,
                                config['strains'][strain]['step_size'],
                                config['strains'][strain]['durations_by_profile'])
            self.strains.append(new_strain)
            self.strains_by_name[strain] = new_strain
            self.num_initial_cases[new_strain] =\
                math.ceil(world.scale_factor * config['strains'][strain]['num_initial_cases'])

        # Construct mutation matrix
        self.mutation_matrix = defaultdict(dict)
        for strain_1 in self.strains:
            for strain_2 in self.strains:
                self.mutation_matrix[strain_1][strain_2] =\
                    config['mutation_matrix'][strain_1.name][strain_2.name]

        # Construct immunity matrix
        self.immunity_matrix = defaultdict(dict)
        for strain_1 in self.strains:
            for strain_2 in self.strains:
                self.immunity_matrix[strain_1][strain_2] =\
                    config['immunity_matrix'][strain_1.name][strain_2.name]

        # Location types in which no or reduced transmission occurs
        self.no_transmission_locations      = config['no_transmission_locations']
        self.reduced_transmission_locations = config['reduced_transmission_locations']
        self.reduced_transmission_factor    = config['reduced_transmission_factor']

        # A record of who is infected with what
        self.infections = {} # self.infections[agent]: Strain

        # A record of who is immune to what
        self.immune = defaultdict(dict) # self.immune[agent][strain]: bool

        # A record of who loses immunity to what when
        self.immunity_loss_times = defaultdict(dict) # self.immunity_loss_times[agent][strain]: int

        # Set initial immunity
        for agent in world.agents:
            for strain in self.strains:
                self.immune[agent][strain] = False
                self.immunity_loss_times[agent][strain] = -1

        # Health state change time
        self.health_state_change_time   = {}
        self.transmission_probability   = {}

        # Initialize health of agents
        for agent in world.agents:
            agent.health = self.susceptible_state
            self.health_state_change_time[agent] = 0

        # Determine disease pathway and durations
        self.disease_profile_dict = defaultdict(dict)
        self.disease_profile_index_dict = {}
        self.disease_durations_dict = defaultdict(dict)
        for agent in world.agents:
            for strain in self.strains:
                max_age = max(age for age in strain.labelled_profiles_by_age)
                age_rounded = min((agent.age//strain.step_size)*strain.step_size, max_age)
                profile = self.prng.multinoulli_dict(strain.labelled_profiles_by_age[age_rounded])
                durations = self._durations_for_profile(profile, strain, clock)
                self.disease_profile_dict[agent][strain] = [self.state_for_letter(l) for l in profile]
                self.disease_durations_dict[agent][strain] = durations
                self.disease_profile_index_dict[agent] = 0

        # Resident region
        self.region = config['region']

    def init_sim(self, sim):
        super().init_sim(sim)

        self.sim   = sim
        self.world = sim.world

        self.bus.subscribe("notify.time.tick", self.get_health_transitions, self)
        self.bus.subscribe("notify.agent.health", self.update_health_state_change_time, self)
        self.bus.subscribe("request.agent.gain_immunity", self._gain_immunity, self)

        # Report list of strains to telemetry bus
        self.report("strains.list", [strain.name for strain in self.strains])

        # A record of cumulative cases by strain
        self.cumulative_cases_by_strain          = {strain: 0 for strain in self.strains}
        self.cumulative_resident_cases_by_strain = {strain: 0 for strain in self.strains}

        # The total number of initial infections
        total_num_initial_cases = sum([self.num_initial_cases[strain] for strain in self.strains])

        # The agents to be initially infected
        residents = [a for a in sim.world.agents if a.region == self.region]
        total_initial_cases = self.prng.random_sample(residents, total_num_initial_cases)

        # Infect these agents
        log.info("Infecting %i agents...", total_num_initial_cases)
        for strain in self.strains:
            initial_cases = self.prng.random_sample(total_initial_cases,
                                                    self.num_initial_cases[strain])
            for agent in initial_cases:
                # Check for immunity
                if self.immune[agent][strain]:
                    continue
                # Infect agent with strain
                self.infections[agent] = strain
                self.cumulative_cases_by_strain[strain] += 1
                if agent.region == self.region:
                    self.cumulative_resident_cases_by_strain[strain] += 1
                # Update health state
                self.disease_profile_index_dict[agent] = 2
                new_health = self.disease_profile_dict[agent][strain][2]
                self.transmission_probability[agent] = strain.transmission_probability[new_health]
                agent.health = new_health
                total_initial_cases.remove(agent)

    def get_health_transitions(self, clock, t):
        """Updates the health state of agents"""

        # Report counts to telemetry bus
        counts = {strain: 0 for strain in self.strains}
        resident_counts = {strain: 0 for strain in self.strains}
        for agent in self.world.agents:
            if agent.health in self.infected_states:
                counts[self.infections[agent]] += 1
                if agent.region == self.region:
                    resident_counts[self.infections[agent]] += 1
        row = [counts[strain] for strain in self.strains]\
              + [resident_counts[strain] for strain in self.strains]
        self.report("strain_counts.update", clock, row)

        # Report cumulative cases to telemetry bus
        row = [self.cumulative_cases_by_strain[strain] for strain in self.strains]
        row = row + [self.cumulative_resident_cases_by_strain[strain] for strain in self.strains]
        self.report("cumulative_cases_by_strain.update", clock, row)

        # Determine which suceptible agents are infected during this tick
        for location in self.sim.world.locations:
            if location.typ not in self.no_transmission_locations:
                infected_lists  = [self.sim.attendees_by_health[location][h]
                                   for h in self.infected_states]
                infected = [sym for sym_list in infected_lists for sym in sym_list]
                if len(infected) > 0:
                    if location.typ in self.reduced_transmission_locations:
                        r_t_f = self.reduced_transmission_factor
                    else:
                        r_t_f = 1
                    probability = 1 - np.prod([1 - (r_t_f * self.transmission_probability[a])
                                               for a in infected])
                    susceptibles = self.sim.attendees_by_health[location][self.susceptible_state]
                    num_new_exposures = self.prng.binomial(len(susceptibles), probability)
                    if num_new_exposures > 0:
                        new_exposures = self.prng.random_sample(susceptibles, num_new_exposures)
                        weights = [self.transmission_probability[a] for a in infected]
                        # Loop through new exposures and request health state updates
                        for agent in new_exposures:
                            infector = self.prng.random_choices(infected, weights, 1)[0]
                            strain = self.infections[infector]
                            self._infect(agent, strain, clock)

        # Determine which other agents need moving to their next health state
        for agent in self.world.agents:
            for strain in self.strains:
                if self.immunity_loss_times[agent][strain] == t:
                    self._lose_immunity(agent, strain)
            if agent.health in self.infected_states:
                duration_ticks = self.disease_durations_dict[agent][self.infections[agent]]\
                                 [self.disease_profile_index_dict[agent]]
                if duration_ticks is not None:
                    time_since_state_change = t - self.health_state_change_time[agent]
                    if time_since_state_change > duration_ticks:
                        new_health = self.disease_profile_dict[agent][self.infections[agent]]\
                                     [self.disease_profile_index_dict[agent] + 1]
                        self.bus.publish("request.agent.health", agent, new_health)

    def update_health_state_change_time(self, agent, old_health):
        """Update internal counts."""

        self.health_state_change_time[agent] = self.sim.clock.t

        strain = self.infections[agent]

        if agent.health == self.susceptible_state:
            immunity_duration = self.disease_durations_dict[agent][self.infections[agent]][-1]
            self._recover(agent, strain, immunity_duration)
        elif agent.health == self.dead_state:
            self._die(agent)
        else:
            self._next_state(agent, strain, agent.health)

    def _infect(self, agent, strain, clock):
        """Infects an agent"""

        # Mutate the strain
        weights = [self.mutation_matrix[strain][s] for s in self.strains]
        strain = self.prng.random_choices(self.strains, weights, 1)[0]

        # Check agent immunity
        if self.immune[agent][strain]:
            return

        # Infect agent with strain
        self.infections[agent] = strain
        self.cumulative_cases_by_strain[strain] += 1
        if agent.region == self.region:
            self.cumulative_resident_cases_by_strain[strain] += 1

        # Publish health state transition request
        new_health = self.disease_profile_dict[agent][self.infections[agent]][1]
        self.bus.publish("request.agent.health", agent, new_health)

    def _next_state(self, agent, strain, new_health):
        """Responds to new infected state of agent"""

        # Move agent health to next state
        self.disease_profile_index_dict[agent] += 1
        self.transmission_probability[agent] = strain.transmission_probability[new_health]

    def _recover(self, agent, strain, immunity_duration):
        """Responds to recovery of agent"""

        # Give agent immunity
        self._gain_immunity(agent, [strain], immunity_duration)

        # Remove strain from agent
        self.infections[agent] = None

        # Reset index
        self.disease_profile_index_dict[agent] = None
        self.transmission_probability[agent] = None

    def _die(self, agent):
        """Responds to death of agent"""

        # Remove strain from agent
        self.infections[agent] = None

        # Reset index
        self.disease_profile_index_dict[agent] = None
        self.transmission_probability[agent] = None

    def _gain_immunity(self, agent, strains, duration):
        """Agent gains immunity to this and possibly other strains"""

        # Add agent immunity
        for strain in strains:
            if isinstance(strain, str):
                strain = self.strains_by_name[strain]
            for other_strain in self.strains:
                if self.prng.boolean(self.immunity_matrix[strain][other_strain]):
                    self.immune[agent][other_strain] = True
                    if duration is not None:
                        self.immunity_loss_times[agent][other_strain] = self.sim.clock.t + duration
                    else:
                        self.immunity_loss_times[agent][other_strain] = -1

    def _lose_immunity(self, agent, strain):
        """Agent loses immunity to this and possibly other strains"""

        # Remove agent immunity
        self.immune[agent][strain] = False
        self.immunity_loss_times[agent][strain] = -1

    def _durations_for_profile(self, profile, strain, clock):
        """Assigns durations for each phase in a given profile"""

        durations = []
        for i in range(len(strain.durations_by_profile[profile])):
            dist = strain.durations_by_profile[profile][i]
            if dist == 'None':
                durations.append(None)
            if isinstance(dist,list):
                if dist[0] == 'G':
                    dur_days = self.prng.gammavariate(float(dist[1][0]), float(dist[1][1]))
                if dist[0] == 'U':
                    dur_days = self.prng.random_choice(list(range(int(dist[1][0]),
                                                                   int(dist[1][1]))))
                if dist[0] == 'C':
                    dur_days = float(dist[1][0])
                if dist[0] == 'E':
                    dur_days = self.prng.expovariate(1/float(dist[1][0]))
                durations.append(clock.days_to_ticks(dur_days))
        return durations
