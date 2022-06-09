"""Labour dynamics based on the labour flow network paradigm"""

import logging
import math

from tqdm import tqdm
from ms_abmlux.location import Location
from ms_abmlux.transport_model import TransportModel

log = logging.getLogger("simple_transport_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleTransportModel(TransportModel):
    """Represents transport within the system, including cars and public transport (pt)"""

    def __init__(self, config, activity_manager, occupants, world):

        super().__init__(config, activity_manager)

        self.car_activity_type_int  = activity_manager.as_int(config['car_activity_type'])
        self.car_activity_type_str  = activity_manager.as_str(self.car_activity_type_int)
        self.pt_activity_type_int   = activity_manager.as_int(config['pt_activity_type'])
        self.pt_activity_type_str   = activity_manager.as_str(self.pt_activity_type_int)

        self.number_of_pt_locations = math.ceil(world.scale_factor*config['number_of_pt_locations'])

        self.car_location_type      = config['car_location_type']
        self.pt_location_type       = config['pt_location_type']

        self.number_can_visit_pt    = config['number_can_visit_pt']
        self.house_location_type    = config['house_location_type']
        self.carehome_location_type = config['carehome_location_type']
        self.other_region_location_types = config['other_region_location_types']

        self.alpha                  = config['alpha']
        self.beta                   = config['beta']

        self.units_available_week_day    = self.config['units_available_week_day']
        self.units_available_weekend_day = self.config['units_available_weekend_day']

        self.scale_factor = world.scale_factor

        self.occupants = occupants

        """Determine any necessary augmentations of the world that relate to transport"""

        log.debug("Configuring network detour ratio...")

        world.alpha = self.alpha
        world.beta  = self.beta

        houses    = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)

        log.info("Creating locations of type: %s...", self.car_location_type)

        log.info("Assigning locations for activity: %s...", self.car_activity_type_str)

        # Create and assign cars for house occupants
        for house in tqdm(houses):
            new_car = Location(self.car_location_type, house.coord)
            world.add_location(new_car)
            for agent in self.occupants[house]:
                agent.add_activity_location(self.car_activity_type_int, new_car)

        # Have agents from care homes perform the activity in their care home
        for carehome in carehomes:
            for agent in self.occupants[carehome]:
                agent.add_activity_location(self.car_activity_type_int, carehome)

        # Have agents from other regions perform the activity in their home region
        for other_region in other_regions:
            for agent in self.occupants[other_region]:
                agent.add_activity_location(self.car_activity_type_int, other_region)

        log.info("Creating locations of type: %s...", self.pt_location_type)

        log.info("Assigning locations for activity: %s...", self.pt_activity_type_str)

        log.debug("Creating public transport locations...")
        for _ in range(self.number_of_pt_locations):
            new_coord = world.map.sample_coord()
            new_pt = Location(self.pt_location_type, new_coord)
            world.add_location(new_pt)

        self.public_transport_units      = world.locations_for_types(self.pt_location_type)
        self.max_units_available         = len(self.public_transport_units)
        self.units_available             = len(self.public_transport_units)

        # Assign public transport for house occupants
        for house in tqdm(houses):
            for agent in self.occupants[house]:
                sample = self.prng.random_sample(self.public_transport_units,
                                                 k = min(len(self.public_transport_units),
                                                 self.number_can_visit_pt))
                agent.add_activity_location(self.pt_activity_type_int, sample)

        # Have agents from care homes perform the activity in their care home
        for carehome in carehomes:
            for agent in self.occupants[carehome]:
                agent.add_activity_location(self.pt_activity_type_int, carehome)

        # Have agents from other regions perform the activity in their home region
        for other_region in other_regions:
            for agent in self.occupants[other_region]:
                agent.add_activity_location(self.pt_activity_type_int, other_region)

    def init_sim(self, sim):
        super().init_sim(sim)

        self.bus.subscribe("notify.time.tick", self.update_unit_availability, self)

        def do_something():
            return

        do_something()

    def update_unit_availability(self, clock, t):
        """Updates the number of units of public transport available during each tick"""

        seconds_through_day = clock.now().hour * 3600 + clock.now().minute * 60 + clock.now().second
        index = int(seconds_through_day / clock.tick_length_s)
        if clock.now().weekday() in [5,6]:
            self.units_available = min(max(math.ceil(self.units_available_weekend_day[index] *
                                                 self.scale_factor), 1), self.max_units_available)
        else:
            self.units_available = min(max(math.ceil(self.units_available_week_day[index] *
                                                 self.scale_factor), 1), self.max_units_available)

        self.bus.publish("notify.pt.availability", self.units_available)

    def _internal_function(self, args):
        """A function used by the labour model"""

        def do_something():
            return

        do_something()
