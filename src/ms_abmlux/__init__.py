"""ABMlux is an agent-based model of a human population."""

import os
import os.path as osp
import sys
import logging
import logging.config
import traceback
import argparse

from ms_abmlux.random_tools import Random
from ms_abmlux.utils import instantiate_class, remove_dunder_keys
from ms_abmlux.messagebus import MessageBus
from ms_abmlux.sim_time import SimClock
from ms_abmlux.sim_factory import SimulationFactory

import ms_abmlux.tools as tools

from ms_abmlux.version import VERSION
from ms_abmlux.config import Config


# Global module log
log = logging.getLogger()


def build_model(sim_factory):
    """Builds world using map and world factories and builds components, such as the activity,
    movement and disease models"""

    config = sim_factory.config

    # ----------------------------------------[ Clock ]---------------------------------------------

    # Create the clock
    _clock = SimClock(config['tick_length_s'], config['simulation_length_days'], config['epoch'])
    log.info("New clock created at %s, tick_length = %i, simulation_days = %i, week_offset = %i",
             _clock.epoch, _clock.tick_length_s, _clock.simulation_length_days,
             _clock.epoch_week_offset)
    sim_factory.set_clock(_clock)

    # ----------------------------------------[ World ]---------------------------------------------

    # Create the map
    map_factory_class = config['map_factory.__type__']
    map_factory_config = config.subconfig('map_factory')
    map_factory = instantiate_class("ms_abmlux.world.map_factory", map_factory_class,
                                    map_factory_config)
    _map = map_factory.get_map()
    sim_factory.set_map(_map)

    # Create the world
    world_factory_class = config['world_factory.__type__']
    world_factory_config = config.subconfig('world_factory')
    world_factory = instantiate_class("ms_abmlux.world.world_factory", world_factory_class,
                                      sim_factory.map, sim_factory.activity_manager,
                                      world_factory_config)
    world = world_factory.get_world()
    sim_factory.set_world(world)

    # ----------------------------------------[ Components ]----------------------------------------

    # Activity model
    activity_model_class = config['activity_model.__type__']
    activity_model_config = config.subconfig('activity_model')
    activity_model = instantiate_class("ms_abmlux.activity_model", activity_model_class,
                                       activity_model_config, sim_factory.activity_manager, world,
                                       sim_factory.clock)
    sim_factory.set_activity_model(activity_model)

    # Housing model
    housing_model_class = config['housing_model.__type__']
    housing_model_config = config.subconfig('housing_model')
    housing_model = instantiate_class("ms_abmlux.housing_model", housing_model_class,
                                      housing_model_config, sim_factory.activity_manager, world)
    sim_factory.set_housing_model(housing_model)

    # Education model
    education_model_class = config['education_model.__type__']
    education_model_config = config.subconfig('education_model')
    education_model = instantiate_class("ms_abmlux.education_model", education_model_class,
                                        education_model_config, sim_factory.activity_manager,
                                        sim_factory.housing_model.occupants, world)
    sim_factory.set_education_model(education_model)

    # Transport model
    transport_model_class = config['transport_model.__type__']
    transport_model_config = config.subconfig('transport_model')
    transport_model = instantiate_class("ms_abmlux.transport_model", transport_model_class,
                                        transport_model_config, sim_factory.activity_manager,
                                        sim_factory.housing_model.occupants, world)
    sim_factory.set_transport_model(transport_model)

    # Health model
    health_model_class = config['health_model.__type__']
    health_model_config = config.subconfig('health_model')
    health_model = instantiate_class("ms_abmlux.health_model", health_model_class,
                                     health_model_config, sim_factory.activity_manager,
                                     sim_factory.housing_model.occupants, world)
    sim_factory.set_health_model(health_model)

    # Leisure model
    leisure_model_class = config['leisure_model.__type__']
    leisure_model_config = config.subconfig('leisure_model')
    leisure_model = instantiate_class("ms_abmlux.leisure_model", leisure_model_class,
                                      leisure_model_config, sim_factory.activity_manager,
                                      sim_factory.housing_model.occupants, world)
    sim_factory.set_leisure_model(leisure_model)

    # Labour model
    labour_model_class = config['labour_model.__type__']
    labour_model_config = config.subconfig('labour_model')
    labour_model = instantiate_class("ms_abmlux.labour_model", labour_model_class,
                                     labour_model_config, sim_factory.activity_manager,
                                     sim_factory.housing_model.occupants, world)
    sim_factory.set_labour_model(labour_model)

    # Movement model
    movement_model_class = config['movement_model.__type__']
    movement_model_config = config.subconfig('movement_model')
    movement_model = instantiate_class("ms_abmlux.movement_model", movement_model_class,
                                       movement_model_config, sim_factory.activity_manager, world)
    sim_factory.set_movement_model(movement_model)

    # Disease model
    disease_model_class  = config['disease_model.__type__']
    disease_model_config = config.subconfig('disease_model')
    disease_model = instantiate_class("ms_abmlux.disease_model", disease_model_class,
                                      disease_model_config, world, sim_factory.clock)
    sim_factory.set_disease_model(disease_model)

    # Interventions
    for intervention_id, intervention_config in config["interventions"].items():

        # Extract keys from the intervention config
        intervention_class    = intervention_config['__type__']

        log.info("Creating intervention %s of type %s...", intervention_id, intervention_class)
        initial_enabled = False if '__enabled__' in intervention_config \
                                                 and not intervention_config['__enabled__']\
                                else True
        new_intervention = instantiate_class("ms_abmlux.interventions", intervention_class, \
                                             intervention_config, initial_enabled)

        sim_factory.add_intervention(intervention_id, new_intervention)
        sim_factory.add_intervention_schedule(new_intervention, intervention_config['__schedule__'])

def build_reporters(telemetry_bus, config):
    """Instantiates reporters, which record data on the simulation for analysis"""

    for reporter_class, reporter_config in config['reporters'].items():
        log.info(f"Creating reporter '{reporter_class}'...")

        instantiate_class("ms_abmlux.reporters", reporter_class, telemetry_bus,
                          Config(_dict=reporter_config))

def main():
    """Main ABMLUX entry point"""
    print(f"ABMLUX {VERSION}")

    # FIXME: proper commandline argparse

    # System config/setup
    if len(sys.argv) > 2 and osp.isfile(sys.argv[2]):
        sim_factory = SimulationFactory.from_file(sys.argv[2])
        logging.config.dictConfig(sim_factory.config['logging'])
        log.warning("Existing factory loaded from %s", sys.argv[2])
    else:
        config = Config(sys.argv[1])
        sim_factory = SimulationFactory(config)
        logging.config.dictConfig(sim_factory.config['logging'])

        # Summarise the sim_factory
        log.info("State info:")
        log.info("  Run ID: %s", sim_factory.run_id)
        log.info("  ABMLUX version: %s", sim_factory.abmlux_version)
        log.info("  Created at: %s", sim_factory.created_at)
        log.info("  Activity Model: %s", sim_factory.activity_model)
        log.info("  Map: %s", sim_factory.map)
        log.info("  World: %s", sim_factory.world)
        log.info("  PRNG seed: %i", sim_factory.config['random_seed'])

        build_model(sim_factory)

        # If a second parameter is given, use this for the statefile name
        if len(sys.argv) > 2:
            log.info("Writing to state file: %s", sys.argv[2])
            sim_factory.to_file(sys.argv[2])

    # Build list from config
    telemetry_bus = MessageBus()
    build_reporters(telemetry_bus, sim_factory.config)

    # ############## Run ##############
    sim = sim_factory.new_sim(telemetry_bus)
    sim.run()

    log.info("Simulation Finished successfully.")
