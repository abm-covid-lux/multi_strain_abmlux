"""Labour dynamics based on the labour flow network paradigm"""

import logging
import copy
import math
from collections import defaultdict

from ms_abmlux.location import Location, WGS84_to_ETRS89
from ms_abmlux.housing_model import HousingModel

log = logging.getLogger("simple_housing_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleHousingModel(HousingModel):
    """Represents a simple of model of housing within the system, consisting of
    houses and carehomes."""

    def __init__(self, config, activity_manager, world):

        super().__init__(config, activity_manager)

        self.home_activity_type_int = activity_manager.as_int(config['home_activity_type'])
        self.home_activity_type_str = activity_manager.as_str(self.home_activity_type_int)

        self.number_of_carehomes    = math.ceil(world.scale_factor * config['number_of_carehomes'])

        self.child_age_limit        = config['child_age_limit']
        self.retired_age_limit      = config['retired_age_limit']
        self.house_location_type    = config['house_location_type']
        self.carehome_location_type = config['carehome_location_type']
        self.residents_per_carehome = config['residents_per_carehome']
        self.hshld_dst_c            = config['household_distribution_children']
        self.hshld_dst_r            = config['household_distribution_retired']

        self.occupants              = defaultdict(list)
        self.sleeps                 = defaultdict(int)

        """Determine any necessary augmentations of the world that relate to housing"""

        log.info("Creating locations of type: %s...", self.house_location_type)
        log.info("Creating locations of type: %s...", self.carehome_location_type)

        log.info("Assigning locations for activity: %s...", self.home_activity_type_str)

        # Create other regions
        for region in config['other_regions']:
            coord = WGS84_to_ETRS89((config['other_regions'][region][0],
                                     config['other_regions'][region][1]))
            new_region = Location(region, (coord[1], coord[0]))
            world.add_location(new_region)
            for agent in world.agents:
                if agent.region == region:
                    self.occupants[new_region].append(agent)
                    agent.add_activity_location(self.home_activity_type_int, new_region)

        # Sort agents by age
        children, adults, retired = [], [], []
        for agent in world.agents:
            if agent.region == config['region']:
                if agent.age in range(0, self.child_age_limit):
                    children.append(agent)
                if agent.age in range(self.child_age_limit, self.retired_age_limit):
                    adults.append(agent)
                if agent.age in range(self.retired_age_limit, 120):
                    retired.append(agent)

        unassigned_children = copy.copy(children)
        unassigned_adults   = copy.copy(adults)
        unassigned_retired  = copy.copy(retired)

        # Create and populate carehomes
        log.debug("Creating and populating care homes...")
        total_retired_in_carehomes = self.residents_per_carehome * self.number_of_carehomes
        unassigned_retired.sort(key = lambda agent: agent.age)
        carehome_residents = unassigned_retired[-total_retired_in_carehomes:]
        del unassigned_retired[-total_retired_in_carehomes:]
        for _ in range(self.number_of_carehomes):
            # Create carehome
            carehome_coord = world.map.sample_coord()
            new_carehome = Location(self.carehome_location_type, carehome_coord)
            world.add_location(new_carehome)
            self.sleeps[new_carehome] = self.residents_per_carehome
            # Populate carehome
            residents = self.prng.random_sample(carehome_residents, k = self.residents_per_carehome)
            for agent in residents:
                carehome_residents.remove(agent)
                self.occupants[new_carehome].append(agent)
                agent.add_activity_location(self.home_activity_type_int, new_carehome)

        self.prng.random_shuffle(unassigned_children)
        self.prng.random_shuffle(unassigned_retired)
        self.prng.random_shuffle(unassigned_adults)

        # Create and populate houses
        log.debug("Creating and populating houses...")
        household_profile_distribution = self._make_household_profile_distribution(self.hshld_dst_c,
                                                                                   self.hshld_dst_r)
        while len(unassigned_children + unassigned_adults + unassigned_retired) > 0:
            # Generate household profile
            household_profile = self.prng.multinoulli_dict(household_profile_distribution)
            num_children = min(household_profile[0], len(unassigned_children))
            num_adults   = min(household_profile[1], len(unassigned_adults))
            num_retired  = min(household_profile[2], len(unassigned_retired))
            # Take agents from front of lists
            children = unassigned_children[0:num_children]
            adults = unassigned_adults[0:num_adults]
            retired = unassigned_retired[0:num_retired]
            # If some agents are found then create a new house
            if len(children + adults + retired) > 0:
                del unassigned_children[0:num_children]
                del unassigned_adults[0:num_adults]
                del unassigned_retired[0:num_retired]
                # Create new house and add it to the world
                house_coord = world.map.sample_coord()
                new_house = Location(self.house_location_type, house_coord)
                world.add_location(new_house)
                # Assign agents to new house
                residents = children + adults + retired
                self.sleeps[new_house] = len(residents)
                for agent in residents:
                    self.occupants[new_house].append(agent)
                    agent.add_activity_location(self.home_activity_type_int, new_house)

    def init_sim(self, sim):
        super().init_sim(sim)

        self.bus.subscribe("notify.time.tick", self.handle, self)

        # Initialize housing model

        def do_something():
            return

        do_something()

    def handle(self, clock, t):
        """Handles the topic"""

        def do_something():
            return

        do_something()

    def _make_household_profile_distribution(self, hshld_dst_c, hshld_dst_r):
        """Creates a probability distribution across household profiles."""

        log.debug("Making housing dictionary...")

        max_house_size = len(hshld_dst_r[0]) - 1
        if max_house_size != len(hshld_dst_c[0]) - 1:
            raise Exception("Distributions of children and retired are in conflict: max house size")
        total_houses = sum([sum(x) for x in zip(*hshld_dst_r)])
        if total_houses != sum([sum(x) for x in zip(*hshld_dst_c)]):
            raise Exception("Distributions of children and retired are in conflict: total houses")
        # Each key in the following dictionary, house_profiles, will be a triple. The entries in
        # each triple will correspond to numbers of children, adults and retired, respectively. The
        # corresponding value indicates the probility of that triple occuring as household profile.
        # The sum of the entries in a given triple is bounded by the maximum house size. All
        # possible keys are generated that satisfy this bound.
        #
        # To generate the probabilties, it is assumed that, conditional on the house size being n
        # and the number of retired residents in a house being r, the number of children c follows
        # the distribution given by normalizing the first n-r entries in the n-th column of the
        # matrix hshld_dst_c, averaged against the probability obtained by calculating the same
        # quantity with the roles of children and retired interchanged.
        house_profiles = {}
        for house_size in range(1, max_house_size + 1):
            for num_children in range(house_size + 1):
                for num_retired in range(house_size + 1 - num_children):
                    num_adult = house_size - num_children - num_retired
                    weight_1 = sum(tuple(zip(*hshld_dst_c))[house_size][0:house_size + 1 -
                                                                                       num_retired])
                    prob_1 = hshld_dst_c[num_children][house_size]\
                        * hshld_dst_r[num_retired][house_size] / (total_houses*weight_1)
                    weight_2 = sum(tuple(zip(*hshld_dst_r))[house_size][0:house_size + 1 -
                                                                                      num_children])
                    prob_2 = hshld_dst_r[num_retired][house_size]\
                        * hshld_dst_c[num_children][house_size] / (total_houses*weight_2)
                    house_profiles[(num_children, num_adult, num_retired)] = (prob_1 + prob_2)/2

        return house_profiles
