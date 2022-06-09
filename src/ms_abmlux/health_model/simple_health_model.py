"""Simple model of agent health, medical centers and hospitals"""

import logging
import copy
import math
from tqdm import tqdm
from scipy.spatial import KDTree

from ms_abmlux.location import Location
from ms_abmlux.health_model import HealthModel

log = logging.getLogger("simple_health_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleHealthModel(HealthModel):
    """Represents health within the system"""

    def __init__(self, config, activity_manager, occupants, world):
        super().__init__(config, activity_manager)

        self.medical_activity_type_int = activity_manager.as_int(config['medical_activity_type'])
        self.medical_activity_type_str = activity_manager.as_str(self.medical_activity_type_int)

        self.number_of_medical_clinics = math.ceil(world.scale_factor * \
                                                   config['number_of_medical_clinics'])
        self.number_of_hospitals       = math.ceil(world.scale_factor * \
                                                   config['number_of_hospitals'])
        self.number_of_cemeteries      = math.ceil(world.scale_factor * \
                                                   config['number_of_cemeteries'])

        self.medical_clinic_location_type = config['medical_clinic_location_type']
        self.hosptial_location_type       = config['hosptial_location_type']
        self.cemetery_location_type       = config['cemetery_location_type']
        self.house_location_type          = config['house_location_type']
        self.carehome_location_type       = config['carehome_location_type']
        self.other_region_location_types  = config['other_region_location_types']

        self.occupants                    = occupants

        """Determine any necessary augmentations of the world that relate to health"""

        log.info("Creating locations of type: %s...", self.medical_clinic_location_type)
        for _ in range(self.number_of_medical_clinics):
            medical_clinic_coord = world.map.sample_coord()
            new_medical_clinic = Location(self.medical_clinic_location_type, medical_clinic_coord)
            world.add_location(new_medical_clinic)

        log.info("Creating locations of type: %s...", self.hosptial_location_type)
        for _ in range(self.number_of_hospitals):
            hospital_coord = world.map.sample_coord()
            new_hospital = Location(self.hosptial_location_type, hospital_coord)
            world.add_location(new_hospital)

        log.info("Creating locations of type: %s...", self.cemetery_location_type)
        for _ in range(self.number_of_cemeteries):
            cemetery_coord = world.map.sample_coord()
            new_cemetery = Location(self.cemetery_location_type, cemetery_coord)
            world.add_location(new_cemetery)

        log.info("Assigning locations for activity: %s...", self.medical_activity_type_str)

        medical_clinics = world.locations_by_type[self.medical_clinic_location_type]
        hospitals = world.locations_by_type[self.hosptial_location_type]
        health_locations = medical_clinics + hospitals

        houses = world.locations_by_type[self.house_location_type]
        carehomes = world.locations_by_type[self.carehome_location_type]
        other_regions = world.locations_for_types(self.other_region_location_types)
        occcupied_locations = houses + carehomes

        kdtree = KDTree([l.coord for l in health_locations])
        # Copy the list of houses and shuffle the order to avoid bias
        shuffled_occcupied_locations = copy.copy(occcupied_locations)
        self.prng.random_shuffle(shuffled_occcupied_locations)
        # Loop through the houses and care homes and assign medical clinics or hospitals
        for occcupied_location in tqdm(shuffled_occcupied_locations):
            # Find the nearest medical clinic or hospital and assign to it all house occupants
            _, nearest_index = kdtree.query(occcupied_location.coord, 1)
            nearest_health_location = health_locations[nearest_index]
            for agent in self.occupants[occcupied_location]:
                agent.add_activity_location(self.medical_activity_type_int, nearest_health_location)

        # Have agents from other regions perform the activity in their home region
        for other_region in other_regions:
            for agent in self.occupants[other_region]:
                agent.add_activity_location(self.medical_activity_type_int, other_region)

    def init_sim(self, sim):
        super().init_sim(sim)

        self.bus.subscribe("notify.time.tick", self.handle, self)

        def do_something():
            return

        do_something()

    def handle(self, clock, t):
        """Handles the topic"""

        def do_something():
            return

        do_something()

    def _internal_function(self, args):
        """A function used by the labour model"""

        def do_something():
            return

        do_something()
