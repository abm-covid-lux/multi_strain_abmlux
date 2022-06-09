"""Labour assignment"""

import logging
import math
from collections import defaultdict
import numpy

from tqdm import tqdm
from ms_abmlux.location import Location
from ms_abmlux.labour_model import LabourModel

log = logging.getLogger("simple_labour_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleLabourModel(LabourModel):
    """Represents a simple model of labour market assignment."""

    def __init__(self, config, activity_manager, occupants, world):

        super().__init__(config, activity_manager)

        self.work_activity_type_int = activity_manager.as_int(config['work_activity_type'])
        self.work_activity_type_str = activity_manager.as_str(self.work_activity_type_int)
        self.home_activity_type_int = activity_manager.as_int(config['home_activity_type'])

        num_locs                            = config['additional_work_location_types']
        self.additional_work_location_types = {typ: math.ceil(world.scale_factor * \
                                               num_locs[typ]) for typ in num_locs.keys()}

        self.workforce_profile_distribution = config['workforce_profile_distribution']
        self.profile_format                 = config['workforce_profile_distribution_format']

        self.location_choice_fp             = config['location_choice_fp']
        self.bin_width                      = config['bin_width']
        self.number_of_bins                 = config['number_of_bins']
        self.destination_country            = config['destination_country']
        self.origin_country_dict            = config['origin_country_dict']
        data_act_dict                       = config['data_activity_dict']
        self.data_activity_dict_int         = {activity_manager.as_int(act): data_act_dict[act] for
                                               act in data_act_dict}
        self.location_sample_size           = config['location_sample_size']
        self.house_location_type            = config['house_location_type']
        self.carehome_location_type         = config['carehome_location_type']
        self.other_region_location_types    = config['other_region_location_types']

        self.positions                      = defaultdict(int)
        self.occupants                      = occupants

        self.network_distance               = world.network_distance

        """Determine any necessary augmentations of the world that relate to work"""

        # Create locations for each type, of the amounts requested
        for ltype, lcount in self.additional_work_location_types.items():
            log.info("Creating locations of type: %s...", ltype)
            for _ in range(lcount):
                new_coord = world.map.sample_coord()
                new_location = Location(ltype, new_coord)
                world.add_location(new_location)

        log.info("Assigning locations by distance for activity: %s...", self.work_activity_type_str)

        houses    = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)

        venues = world.locations_for_types(list(self.workforce_profile_distribution.keys()))

        # Construct the probability distributions
        activity_type_int = self.work_activity_type_int
        dist_dist = {}
        for origin_country in self.origin_country_dict:
            dist_dist[origin_country] =\
                self._make_distribution(self.data_activity_dict_int[activity_type_int],
                    self.origin_country_dict[origin_country], self.destination_country,
                    self.number_of_bins[origin_country], self.bin_width[origin_country])

        # Weights reflect typical size of workforce in locations across different sectors
        for location_type in self.workforce_profile_distribution:
            profile = self.workforce_profile_distribution[location_type]
            if isinstance(profile, list):
                for location in world.locations_by_type[location_type]:
                    interval = self.profile_format[self.prng.multinoulli(profile)]
                    weight = self.prng.random_randrange_interval(interval[0], interval[1])
                    self.positions[location] = weight
            elif isinstance(profile, int):
                weight = profile
                for location in world.locations_by_type[location_type]:
                    self.positions[location] = weight
            else:
                raise Exception("Work force profile is of incorrect format")

        log.debug("Assigning workplaces to house occupants...")

        work_loc_sample_size = min(self.location_sample_size, len(venues))
        for house in tqdm(houses):
            # Here each house gets a sample from which occupants choose
            work_locations_sample = self.prng.random_sample(venues, k = work_loc_sample_size)
            weights_for_house = {}
            for location in work_locations_sample:
                dist_m = house.distance_euclidean_m(location)
                dist_km = dist_m / 1000
                weight = self._get_weight(dist_km, dist_dist[self.destination_country])
                # For each location, the workforce weights and distance weights are multiplied
                weights_for_house[location] = self.positions[location] * weight
            # If all the weights are zero, set them all equal to a positive number
            if sum(list(weights_for_house.values())) == 0:
                for location in weights_for_house:
                    weights_for_house[location] = 1
            # For each agent occupying the house, chosen randomly from the weighted sample
            for agent in self.occupants[house]:
                if agent.work_behaviour_type:
                    workplace = self.prng.multinoulli_dict(weights_for_house)
                    agent.add_activity_location(self.work_activity_type_int, workplace)
            weights_for_house.clear()

        log.debug("Assigning workplaces to carehome occupants...")
        self._do_activity_from_home(carehomes, self.work_activity_type_int)

        log.debug("Assigning workplaces to border country occupants...")
        for other_region in other_regions:
            for agent in tqdm(self.occupants[other_region]):
                # Here each agent gets a sample from which to choose
                work_locations_sample = self.prng.random_sample(venues, k = work_loc_sample_size)
                weights_for_agent = {}
                for location in work_locations_sample:
                    dist_m = other_region.distance_euclidean_m(location)
                    dist_km = dist_m / 1000
                    weight = self._get_weight(dist_km, dist_dist[other_region.typ])
                    # For each location, the workforce weights and distance weights are multiplied
                    weights_for_agent[location] = self.positions[location] * weight
                # If all the weights are zero, set them all equal to a positive number
                if sum(list(weights_for_agent.values())) == 0:
                    for location in weights_for_agent:
                        weights_for_agent[location] = 1
                # For each agent occupying the house, chosen randomly from the weighted sample
                workplace = self.prng.multinoulli_dict(weights_for_agent)
                agent.add_activity_location(self.work_activity_type_int, workplace)
                weights_for_agent.clear()

        # Have unassigned agents perform the work activity at home
        for agent in world.agents:
            if len(agent.locations_for_activity(self.work_activity_type_int)) == 0:
                home = agent.locations_for_activity(self.home_activity_type_int)[0]
                agent.add_activity_location(self.work_activity_type_int, home)

    def init_sim(self, sim):
        super().init_sim(sim)

        # self.labour_param_sim = self.config['labour_param_sim']

        self.bus.subscribe("notify.time.tick", self.handle, self)

        # Initialize labour model

        def do_something():
            return

        do_something()

    def handle(self, clock, t):
        """Handles the topic"""

        def do_something():
            return

        do_something()

    def _do_activity_from_home(self, locations, activity_type_int):
        """Sets the activity location as the locaiton of occupancy."""

        for location in locations:
            for agent in self.occupants[location]:
                agent.add_activity_location(activity_type_int, location)

    def _make_distribution(self, motive, country_origin, country_destination, number_of_bins,
                           bin_width):
        """For given country of origin, country of destination and motive, this creates a
        probability distribution over a range of distances."""

        log.debug("Generating distance distribution...")

        # For the following distribution, the probability assigned to a given range reflects the
        # probability that the length of a trip, between the input countries and with the given
        # motivation, falls within that range. Note that the units of bid_width are kilometers, and
        # that the distances recorded in the data refer to distance travelled by the respondent, not
        # as the crow flies.
        actsheet = numpy.genfromtxt(self.location_choice_fp, dtype = str, delimiter=",")
        max_row  = numpy.shape(actsheet)[0]
        distance_distribution = {}

        for bin_num in range(number_of_bins):
            distance_distribution[range(bin_width * bin_num, bin_width * (bin_num + 1))] = 0
        for sheet_row in range(1, max_row):
            motive_sample              = actsheet[sheet_row][0]
            country_origin_sample      = actsheet[sheet_row][1]
            country_destination_sample = actsheet[sheet_row][2]
            distance_str               = actsheet[sheet_row][3]
            weight_str                 = actsheet[sheet_row][4]
            # For each sample of the desired type, record the distance and add to the distribution
            # if the distance is less than the maxiumum distance recorded by the distribution
            if ([motive_sample, country_origin_sample, country_destination_sample]
                == [motive, country_origin, country_destination]) and distance_str != "Na":
                distance = float(distance_str)
                if distance < number_of_bins * bin_width:
                    weight = float(weight_str)
                    range_min = int((distance//bin_width) * bin_width)
                    range_max = int(((distance//bin_width) + 1) * bin_width)
                    distance_distribution[range(range_min, range_max)] += round(weight)
        # Normalize to obtain a probability distribution
        total_weight = sum(distance_distribution.values())
        if total_weight == 0:
            for distribution_bin in distance_distribution:
                distance_distribution[distribution_bin] = 1
        else:
            for distribution_bin in distance_distribution:
                distance_distribution[distribution_bin] /= total_weight

        return distance_distribution

    def _get_weight(self, dist_km, distance_distribution):
        """Given a distance, in kilometers, and a distance_distribution, returns the probability
        weight associated to that distance by the distribution."""

        max_dist = sum([len(dist_bin) for dist_bin in distance_distribution])
        if int(self.network_distance(dist_km)) >= max_dist:
            return 0.0

        for dist_bin in distance_distribution:
            if int(self.network_distance(dist_km)) in dist_bin:
                return distance_distribution[dist_bin]
