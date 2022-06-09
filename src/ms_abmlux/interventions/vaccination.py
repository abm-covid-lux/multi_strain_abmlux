"""Represents vaccination schemes consisting of multiple vaccines"""

import logging
import math

from ms_abmlux.interventions.vaccine import Vaccine
from ms_abmlux.sim_time import DeferredEventPool
from ms_abmlux.interventions import Intervention

log = logging.getLogger("vaccination")

# This file uses callbacks and interfaces which make this hit many false positives
#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class Vaccination(Intervention):
    """Vaccinate agents with several different vaccines available"""

    def __init__(self, config, init_enabled):
        super().__init__(config, init_enabled)

        # This represents the daily vaccination capacity
        self.register_variable('max_first_doses_per_day')

        # A list of all vaccines found in the config
        self.vaccines = []

        # A record of how many doses of each vaccine are administered each day
        self.max_first_doses_per_day = {}

    def init_sim(self, sim):
        super().init_sim(sim)

        self.sim   = sim
        self.world = sim.world

        self.bus.subscribe("notify.time.midnight", self.midnight, self)
        self.bus.subscribe("request.vaccination.second_dose", self.administer_second_dose, self)

        self.second_dose_events = DeferredEventPool(self.bus, sim.clock)

        # Initialize the strains
        for vaccine in self.config['vaccines']:
            second_dose_needed = self.config['vaccines'][vaccine]['second_dose_needed']
            time_between_doses_days = self.config['vaccines'][vaccine]['time_between_doses']
            prob_first_dose_successful =\
                self.config['vaccines'][vaccine]['prob_first_dose_successful']
            prob_second_dose_successful =\
                self.config['vaccines'][vaccine]['prob_second_dose_successful']
            targetted_strains = self.config['vaccines'][vaccine]['targetted_strains']
            duration = int(sim.clock.days_to_ticks(self.config['vaccines'][vaccine]['duration']))
            new_vaccine = Vaccine(vaccine,
                                  second_dose_needed,
                                  int(sim.clock.days_to_ticks(time_between_doses_days)),
                                  prob_first_dose_successful,
                                  prob_second_dose_successful,
                                  targetted_strains, duration)
            self.vaccines.append(new_vaccine)

        # First doses per day for each vaccine
        self.scale_factor = sim.world.scale_factor
        for vaccine in self.vaccines:
            self.max_first_doses_per_day[vaccine] = math.ceil(self.scale_factor *\
                                                    self.config['max_first_doses_per_day'][vaccine])

        # Vaccination priority list
        care_home_location_type = self.config['care_home_location_type']
        hospital_location_type  = self.config['hospital_location_type']
        home_activity_type      = sim.activity_manager.as_int(self.config['home_activity_type'])
        work_activity_type      = sim.activity_manager.as_int(self.config['work_activity_type'])
        min_age                 = self.config['min_age']
        self.vaccination_priority_list = self._get_vaccination_priority_list(home_activity_type,
            work_activity_type, care_home_location_type, hospital_location_type, min_age)

        # Vaccine hesitancy
        age_low   = self.config['age_low']
        age_high  = self.config['age_high']
        prob_low  = self.config['prob_low']
        prob_med  = self.config['prob_med']
        prob_high = self.config['prob_high']
        self.agent_wants_vaccine = self._get_vaccine_hesitancy(age_low, age_high,
                                                               prob_low, prob_med, prob_high)

    def administer_second_dose(self, agent, vaccine):
        """Administers agents with a second dose of the vaccine"""

        if self.prng.boolean(vaccine.prob_second_dose_successful):
            self.bus.publish("request.agent.gain_immunity", agent,
                             vaccine.targetted_strains, vaccine.duration)

    def midnight(self, clock, t):
        """At midnight, remove from the priority list agents who have tested positive that day
        and vaccinate an appropriate number of the remainder"""

        if not self.enabled:
            return

        # Determine how many agents will be vaccinated today
        total_num_to_vaccinate = 0
        num_to_vaccinate = {}
        for vaccine in self.vaccines:
            max_rescaled =  math.ceil(self.scale_factor * self.max_first_doses_per_day[vaccine])
            num_to_vaccinate[vaccine] = min(max_rescaled, len(self.vaccination_priority_list))
            total_num_to_vaccinate += num_to_vaccinate[vaccine]

        # Vaccinate these agents
        total_agents_to_vaccinate = self.vaccination_priority_list[0:total_num_to_vaccinate]
        del self.vaccination_priority_list[0:total_num_to_vaccinate]
        for vaccine in self.vaccines:
            agents_to_vaccinate = self.prng.random_sample(total_agents_to_vaccinate,
                                                          num_to_vaccinate[vaccine])
            for agent in agents_to_vaccinate:
                if self.agent_wants_vaccine[agent]:
                    if self.prng.boolean(vaccine.prob_first_dose_successful):
                        self.bus.publish("request.agent.gain_immunity", agent,
                                         vaccine.targetted_strains, vaccine.duration)
                    if vaccine.second_dose_needed:
                        self.second_dose_events.add("request.vaccination.second_dose",
                                                    vaccine.time_between_doses, agent, vaccine)

    def _get_vaccine_hesitancy(self, age_low, age_high, prob_low, prob_med, prob_high):
        """Decides who will refuse the vaccine at the moment of being offered it"""

        # Decide in advance who will refuse the vaccine
        agent_wants_vaccine = {}
        for agent in self.world.agents:
            if agent.age < age_low:
                agent_wants_vaccine[agent] = self.prng.boolean(prob_low)
            if agent.age >= age_low and agent.age < age_high:
                agent_wants_vaccine[agent] = self.prng.boolean(prob_med)
            if agent.age >= age_high:
                agent_wants_vaccine[agent] = self.prng.boolean(prob_high)

        return agent_wants_vaccine

    def _get_vaccination_priority_list(self, home_activity_type, work_activity_type,
                                       care_home_location_type, hospital_location_type, min_age):
        """Creates ordered list of agents for vaccination"""

        # Determine which agents live or work in carehomes and which agents work in hospitals. Note
        # that workplaces are assigned to everybody, so some agents will be assigned hospitals or
        # carehomes as places of work but, due to their routines, will not actually go to work at
        # these places due to not working at all. So this is somewhat approximate.
        # Order the agents according to the desired preferential scheme
        vaccination_priority_list  = []
        carehome_residents_workers = []
        hospital_workers           = []
        other_agents               = []
        for agent in self.world.agents:
            if agent.age >= min_age:
                home_location = agent.locations_for_activity(home_activity_type)[0]
                work_location = agent.locations_for_activity(work_activity_type)[0]
                if home_location.typ in care_home_location_type or\
                    work_location.typ in care_home_location_type:
                    carehome_residents_workers.append(agent)
                elif work_location.typ in hospital_location_type:
                    hospital_workers.append(agent)
                else:
                    other_agents.append(agent)

        # Sort the lists of agents by age, with the oldest first
        def return_age(agent):
            return agent.age
        carehome_residents_workers.sort(key=return_age, reverse=True)
        hospital_workers.sort(key=return_age, reverse=True)
        other_agents.sort(key=return_age, reverse=True)

        # Combine these lists together to get the order of agents to be vaccinated
        vaccination_priority_list = carehome_residents_workers + hospital_workers\
                                                                    + other_agents

        return vaccination_priority_list
