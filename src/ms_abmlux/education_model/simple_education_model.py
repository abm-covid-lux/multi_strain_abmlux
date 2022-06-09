"""Labour dynamics based on the labour flow network paradigm"""

import logging
import copy
import math
from collections import defaultdict
import numpy
from tqdm import tqdm
from scipy.spatial import KDTree

from ms_abmlux.location import Location
from ms_abmlux.education_model import EducationModel
from ms_abmlux.education_model.school import School

log = logging.getLogger("simple_education_model")

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleEducationModel(EducationModel):
    """Represents schools within the system, with students being assigned to
    school classrooms according to age."""

    def __init__(self, config, activity_manager, occupants, world):

        super().__init__(config, activity_manager)

        self.school_activity_type_int  = activity_manager.as_int(config['school_activity_type'])
        self.school_activity_type_str  = activity_manager.as_str(self.school_activity_type_int)

        self.school_location_types     = config['school_location_types']
        self.number_of_schools_by_type = {school_type : math.ceil(world.scale_factor *
                                          config['number_of_schools'][school_type]) for school_type
                                          in self.school_location_types}

        self.home_activity_type_int    = activity_manager.as_int(config['home_activity_type'])
        self.house_location_type       = config['house_location_type']
        self.classroom_type            = config['classroom_type']
        self.min_age                   = config['min_age']
        self.years_per_school          = config['years_per_school']
        self.classrooms_per_year       = config['classrooms_per_year']
        self.students_per_classroom    = config['students_per_classroom']

        self.schools_by_type           = defaultdict(list)
        self.students                  = defaultdict(list)
        self.places                    = defaultdict(int)

        self.occupants                 = occupants

        """Determine any necessary augmentations of the world that relate to education"""

        # Create school classrooms and group them according to school and year
        for school_type in self.school_location_types:
            classroom_type = self.classroom_type[school_type]
            log.info("Creating locations of type: %s...", classroom_type)
            min_age = self.min_age[school_type]
            max_age = self.min_age[school_type] + self.years_per_school[school_type]
            for _ in range(self.number_of_schools_by_type[school_type]):
                new_coord = world.map.sample_coord()
                new_school = School(school_type, new_coord)
                for age in range(min_age, max_age):
                    new_classrooms = []
                    for _ in range(self.classrooms_per_year[school_type]):
                        new_classroom = Location(classroom_type, new_coord)
                        world.add_location(new_classroom)
                        self.places[new_classroom] = self.students_per_classroom[school_type]
                        new_classrooms.append(new_classroom)
                    new_school.classrooms[age] = new_classrooms
                self.schools_by_type[school_type].append(new_school)

        # Assign students to classrooms by school proximity and availability
        log.info("Assigning locations for activity: %s...", self.school_activity_type_str)
        houses = world.locations_by_type[self.house_location_type]
        for school_type in self.school_location_types:
            min_age = self.min_age[school_type]
            max_age = self.min_age[school_type] + self.years_per_school[school_type]
            # A KDTree constructed from the corresponding coordinates
            kdtree = KDTree([school.coord for school in self.schools_by_type[school_type]])
            # Copy the list of houses and shuffle the order to avoid bias
            shuffled_houses = copy.copy(houses)
            self.prng.random_shuffle(shuffled_houses)
            # Loop through the houses and assign schools
            for house in tqdm(shuffled_houses):
                # Lists of children by age from this house who require places at this type of school
                required_places_by_age = self._required_places(house, min_age, max_age)
                # Find the nearest school with sufficiently many places for these ages
                knn = 1
                suitable_schools = []
                while len(suitable_schools) == 0:
                    # Returns knn items, in order of nearness
                    _, nearest_indices = kdtree.query(house.coord, knn)
                    if isinstance(nearest_indices, numpy.int64):
                        nearest_indices = [nearest_indices]
                    # Use the indices to recover the corresponding schools
                    suitable_schools = [self.schools_by_type[school_type][i]
                                        for i in nearest_indices]
                    # Remove schools that do not have places
                    suitable_schools = [s for s in suitable_schools if
                                     self._school_is_suitable(required_places_by_age, s.classrooms)]
                    knn = min(knn*2, self.number_of_schools_by_type[school_type])
                nearest_suitable_school = suitable_schools[0]
                # Having found for this house the nearest suitable school, now assign the children
                # to the classrooms, randomly selecting from classrooms within a given year
                for age in required_places_by_age:
                    for agent in required_places_by_age[age]:
                        nearest_crms = [crm for crm in nearest_suitable_school.classrooms[age] if
                                        self.places[crm] - len(self.students[crm]) > 0]
                        classroom = self.prng.random_choice(nearest_crms)
                        agent.add_activity_location(self.school_activity_type_int, classroom)
                        self.students[classroom].append(agent)

        # Have unassigned agents perform the school activity at home
        for agent in world.agents:
            if len(agent.locations_for_activity(self.school_activity_type_int)) == 0:
                home = agent.locations_for_activity(self.home_activity_type_int)[0]
                agent.add_activity_location(self.school_activity_type_int, home)

    def init_sim(self, sim):
        super().init_sim(sim)

        self.bus.subscribe("notify.time.tick", self.handle, self)

        # Initialize education model

        def do_something():
            return

        do_something()

    def handle(self, clock, t):
        """Handles the topic"""

        def do_something():
            return

        do_something()

    def _school_is_suitable(self, required_places_by_age, school_classes_by_age):
        """Determines whether or not a school has places for a dictionary of children
        sorted by age"""

        suitable = True

        for age in required_places_by_age:
            remaining_places = sum([self.places[school_class] - len(self.students[school_class])
                                    for school_class in school_classes_by_age[age]])
            if remaining_places - len(required_places_by_age[age]) < 0:
                suitable = False

        return suitable

    def _required_places(self, house, min_age, max_age):
        """Determines a dictionary of children requiring school places, sorted by age for ages
        within a given age range"""

        required_places_by_age = defaultdict(list)

        for agent in self.occupants[house]:
            if agent.school_behaviour_type:
                if agent.age >= min_age:
                    if agent.age < max_age:
                        required_places_by_age[agent.age].append(agent)

        return required_places_by_age
