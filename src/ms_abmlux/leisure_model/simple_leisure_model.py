"""Labour dynamics based on the labour flow network paradigm"""

import logging
import copy
import math
import numpy

from tqdm import tqdm
from scipy.spatial import KDTree
from ms_abmlux.location import Location
from ms_abmlux.leisure_model import LeisureModel

log = logging.getLogger("simple_leisure_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleLeisureModel(LeisureModel):
    """Represents a simple model of leisure."""

    def __init__(self, config, activity_manager, occupants, world):

        super().__init__(config, activity_manager)

        leis_map                          = config['leisure_activity_mapping']
        self.leisure_activity_mapping_int = {activity_manager.as_int(act_str): leis_map[act_str] for
                                             act_str in leis_map}
        self.activities_int_to_str        = {act_int: activity_manager.as_str(act_int) for
                                             act_int in self.leisure_activity_mapping_int.keys()}

        num_locs                          = config['numbers_of_leisure_locations']
        self.numbers_of_leisure_locations = {typ: math.ceil(world.scale_factor * num_locs[typ])
                                             for typ in num_locs.keys()}

        acts_rnd                          = config['activities_by_random']
        self.activities_by_random_int     = {activity_manager.as_int(act): acts_rnd[act] for
                                             act in acts_rnd}
        acts_prox                         = config['activities_by_proximity']
        self.activities_by_proximity_int  = {activity_manager.as_int(act): acts_prox[act] for
                                             act in acts_prox}
        acts_dist                         = config['activities_by_distance']
        self.activities_by_distance_int   = {activity_manager.as_int(act): acts_dist[act] for
                                             act in acts_dist}

        self.location_choice_fp           = config['location_choice_fp']
        data_act_dict                     = config['data_activity_dict']
        self.data_activity_dict_int       = {activity_manager.as_int(act): data_act_dict[act] for
                                             act in data_act_dict}
        self.origin_country               = config['origin_country']
        self.destination_country          = config['destination_country']
        self.bin_width                    = config['bin_width']
        self.number_of_bins               = config['number_of_bins']
        self.location_sample_size         = config['location_sample_size']

        self.house_location_type          = config['house_location_type']
        self.carehome_location_type       = config['carehome_location_type']
        self.other_region_location_types  = config['other_region_location_types']

        self.occupants                    = occupants

        self.network_distance             = world.network_distance

        """Determine any necessary augmentations of the world that relate to leisure"""

        # Create locations for each type, of the amounts requested
        for ltype, lcount in self.numbers_of_leisure_locations.items():
            log.info("Creating locations of type: %s...", ltype)
            for _ in range(lcount):
                new_coord = world.map.sample_coord()
                new_location = Location(ltype, new_coord)
                world.add_location(new_location)

        # Assign agents locations at which to perform activities whose corresponding locations
        # are chosen randomly
        for act_int, num in self.activities_by_random_int.items():
            self._assign_locations_by_random(world, act_int, num,
                                             self.leisure_activity_mapping_int[act_int])
        # Assign agents locations at which to perform activities whose corresponding locations
        # are chosen by proximity
        for act_int, num in self.activities_by_proximity_int.items():
            self._assign_locations_by_proximity(world, act_int,
                                                self.leisure_activity_mapping_int[act_int])
        # Assign agents locations at which to perform activities whose corresponding locations
        # are chosen by distance
        for act_int, num in self.activities_by_distance_int.items():
            self._assign_locations_by_distance(world, act_int, num,
                                               self.leisure_activity_mapping_int[act_int])

    def init_sim(self, sim):
        super().init_sim(sim)

        self.bus.subscribe("notify.time.tick", self.handle, self)

        # Initialize leisure model

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

    def _assign_locations_by_random(self, world, activity_type_int, sample_size, location_types):
        """For each agent, a number of distinct locations are randomly selected"""

        log.info("Assigning locations by random for activity: %s...",
                 self.activities_int_to_str[activity_type_int])

        houses    = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)

        venues = world.locations_for_types(location_types)
        log.debug("Assigning locations by random to house occupants...")
        for house in tqdm(houses):
            for agent in self.occupants[house]:
                venues_sample = self.prng.random_sample(venues, k = min(len(venues), sample_size))
                agent.add_activity_location(activity_type_int, venues_sample)

        log.debug("Assigning locations by random to carehome occupants...")
        self._do_activity_from_home(carehomes, activity_type_int)

        log.debug("Assigning locations by random to other region occupants...")
        self._do_activity_from_home(other_regions, activity_type_int)

    def _assign_locations_by_proximity(self, world, activity_type_int, location_types):
        """Each house is assigned the nearest location of the given types, unless that location has
        already been assigned a fair share of houses in which case the next nearest available
        location is selected. The occupants of the house are assinged that location to perform the
        given activity"""

        log.info("Assigning locations by proximity for activity: %s...",
                 self.activities_int_to_str[activity_type_int])

        houses    = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)

        venues = world.locations_for_types(location_types)
        log.debug("Assigning locations by proximity to house occupants...")
        max_houses  = math.ceil(len(houses) / len(venues))
        # A KDTree constructed from the corresponding coordinates
        kdtree     = KDTree([l.coord for l in venues])
        # Copy the list of houses and shuffle the order to avoid bias
        shuffled_houses = copy.copy(houses)
        self.prng.random_shuffle(shuffled_houses)
        # Keep track of how many houses have been assigned to each location
        num_houses = {l: 0 for l in venues}
        for house in tqdm(shuffled_houses):
            # Find the nearest available location
            knn = 1
            suitable_locations = []
            while len(suitable_locations) == 0:
                # Returns knn items, in order of nearness
                _, nearest_indices = kdtree.query(house.coord, knn)
                if isinstance(nearest_indices, numpy.int64):
                    nearest_indices = [nearest_indices]
                # Use the indices to recover the corresponding locations
                suitable_locations = [venues[i] for i in nearest_indices]
                # Remove locations that have too many houses already
                suitable_locations = [s for s in suitable_locations if num_houses[s] < max_houses]
                knn = min(knn*2, len(venues))
            nearest_suitable_location = suitable_locations[0]
            # Record that a new house has been assigned to this location
            num_houses[nearest_suitable_location] += 1
            for agent in self.occupants[house]:
                agent.add_activity_location(activity_type_int, nearest_suitable_location)

        log.debug("Assigning locations by proximity to carehome occupants...")
        self._do_activity_from_home(carehomes, activity_type_int)

        log.debug("Assigning locations by proximity to other region occupants...")
        self._do_activity_from_home(other_regions, activity_type_int)

    def _assign_locations_by_distance(self, world, activity_type_int, sample_size, location_types):
        """For each agent a number of distinct locations, not including the individual's own home,
        are randomly selected based on distance so that the individual is able to visit them when
        performing the relevant activity"""

        log.info("Assigning locations by distance for activity: %s...",
                 self.activities_int_to_str[activity_type_int])

        houses    = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)

        venues = world.locations_for_types(location_types)

        # Construct the probability distribution
        dist_dist = self._make_distribution(self.data_activity_dict_int[activity_type_int],
                                            self.origin_country, self.destination_country,
                                            self.number_of_bins, self.bin_width)

        log.debug("Assigning locations by distance to house occupants...")
        for house in tqdm(houses):
            # For each house, sample some locations of the appropriate types
            locations_sample = self.prng.random_sample(venues, k = min(sample_size, len(venues)))
            weights_for_house = {}
            # For each location in the sample, determine a weight using the distance to the house
            for location in locations_sample:
                dist_m = house.distance_euclidean_m(location)
                dist_km = dist_m / 1000
                weights_for_house[location] = self._get_weight(dist_km, dist_dist)
            # If all the weights are zero, set them all equal to a positive number
            if sum(list(weights_for_house.values())) == 0:
                for location in weights_for_house:
                    weights_for_house[location] = 1
            # For each agent occupying the house, chosen randomly from the weighted sample
            for agent in self.occupants[house]: # TODO: Use sampling without replacement?
                locs = self.prng.random_choices(list(weights_for_house.keys()),
                                                list(weights_for_house.values()),
                                                self.activities_by_distance_int[activity_type_int])
                # Remove the agent's own home from the sample, in case it appears there
                if house in locs:
                    locs.remove(house)
                agent.add_activity_location(activity_type_int, locs)
            weights_for_house.clear()

        log.debug("Assigning locations by distance to carehome occupants...")
        self._do_activity_from_home(carehomes, activity_type_int)

        log.debug("Assigning locations by distance to other region occupants...")
        self._do_activity_from_home(other_regions, activity_type_int)

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
