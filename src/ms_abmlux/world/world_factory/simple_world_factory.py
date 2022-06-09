"""This file creates the world, adding the map and a population of agents."""

import math
import logging

from ms_abmlux.agent import Agent
from ms_abmlux.world import World
from ms_abmlux.world.world_factory import WorldFactory

log = logging.getLogger('world_factory')

class SimpleWorldFactory(WorldFactory):
    """Reads a DensityMap and generates a world based on the densities indicated therein."""

    def __init__(self, _map, activity_manager, config):
        """Create agents and locations according to the population density map given"""

        self.map              = _map
        self.config           = config
        self.activity_manager = activity_manager

    def get_world(self) -> World:

        log.info("Creating world...")

        world = World(self.map)

        log.info("Scale factor: %.2f", self.config['scale_factor'])

        world.set_scale_factor(self.config['scale_factor'])

        self._create_agents(world)

        return world

    def _create_agents(self, world):
        """Create a number of Agent objects within the world, according to the distributions
        specified in the configuration object provided"""

        log.debug('Initializing agents...')

        for region in self.config['regions']:
            age_distribution = self.config['regions'][region]['age_distribution']
            population_normalised = [int(x * world.scale_factor) for x in age_distribution]
            log.info("Creating %i agents from %s...", sum(population_normalised), region)
            for age, population in enumerate(population_normalised):
                for _ in range(population):
                    new_agent = Agent(age, region)
                    world.add_agent(new_agent)
