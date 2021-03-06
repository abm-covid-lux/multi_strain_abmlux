"""Represents the simulation state.  Is built gradually by the various model stages, ands then
ingested by the simulator as it runs."""

# Allows classes to return their own type, e.g. from_file below
from __future__ import annotations

import logging
import uuid
import pickle
from datetime import datetime
from typing import Union

from ms_abmlux.activity_model.activity_manager import ActivityManager
from ms_abmlux.config import Config
from ms_abmlux.sim_time import SimClock
from ms_abmlux.version import VERSION
from ms_abmlux.world.map import Map
from ms_abmlux.simulator import Simulator
from ms_abmlux.activity_model import ActivityModel
from ms_abmlux.housing_model import HousingModel
from ms_abmlux.education_model import EducationModel
from ms_abmlux.health_model import HealthModel
from ms_abmlux.transport_model import TransportModel
from ms_abmlux.leisure_model import LeisureModel
from ms_abmlux.labour_model import LabourModel
from ms_abmlux.movement_model import MovementModel
from ms_abmlux.disease_model import DiseaseModel
from ms_abmlux.world import World
from ms_abmlux.interventions import Intervention

log = logging.getLogger("sim_state")



class SimulationFactory:
    """Class that allows for gradual composition of a number of components, eventually outputting
    a simulator object that can be used to run simulations with the config given."""

    def __init__(self, config: Config):

        # Static info
        self.abmlux_version = VERSION
        self.created_at     = datetime.now()
        self.run_id         = uuid.uuid4().hex

        log.info("Simulation state created at %s with ID=%s", self.created_at, self.run_id)

        self.config                 = config
        self.activity_manager       = ActivityManager(config['activities'])

        # Components of the simulation
        self.clock                  = None
        self.map                    = None
        self.world                  = None
        self.activity_model         = None
        self.housing_model          = None
        self.education_model        = None
        self.transport_model        = None
        self.health_model           = None
        self.leisure_model          = None
        self.labour_model           = None
        self.movement_model         = None
        self.disease_model          = None
        self.interventions          = {}
        self.intervention_schedules = {}

    def set_activity_model(self, activity_model: ActivityModel) -> None:
        """Sets activity model"""
        self.activity_model = activity_model

    def set_housing_model(self, housing_model: HousingModel) -> None:
        """Sets housing model"""
        self.housing_model = housing_model

    def set_education_model(self, education_model: EducationModel) -> None:
        """Sets education model"""
        self.education_model = education_model

    def set_transport_model(self, transport_model: TransportModel) -> None:
        """Sets transport model"""
        self.transport_model = transport_model

    def set_health_model(self, health_model: HealthModel) -> None:
        """Sets health model"""
        self.health_model = health_model

    def set_leisure_model(self, leisure_model: LeisureModel) -> None:
        """Sets leisure model"""
        self.leisure_model = leisure_model

    def set_labour_model(self, labour_model: LabourModel) -> None:
        """Sets labour model"""
        self.labour_model = labour_model

    def set_movement_model(self, movement_model: MovementModel) -> None:
        """Sets movement model"""
        self.movement_model = movement_model

    def set_disease_model(self, disease_model: DiseaseModel) -> None:
        """Sets disease model"""
        self.disease_model = disease_model

    def set_world(self, world: World) -> None:
        """Sets world model"""
        self.world = world

    def set_map(self, _map: Map) -> None:
        """Sets map"""
        self.map = _map

    def set_clock(self, clock: SimClock) -> None:
        """Sets clock"""
        self.clock = clock

    def add_intervention(self, name: str, intervention: Intervention) -> None:
        """Adds intervention"""
        self.interventions[name] = intervention

    def add_intervention_schedule(self, intervention: Intervention,
                                  schedule: dict[Union[str, int], str]) -> None:
        """Adds intervention schedule"""
        self.intervention_schedules[intervention] = schedule

    def new_sim(self, telemetry_bus):
        """Return a new simulator based on the config above.

        Telemetry data will be sent to the telemetry_bus provided (of type MessageBus)
        """
        # FIXME: this should be runnable multiple times without any impact on the data integrity.

        if self.map is None:
            raise ValueError("No Map")
        if self.world is None:
            raise ValueError("No world defined.")
        if self.activity_model is None:
            raise ValueError("No activity model defined.")
        if self.housing_model is None:
            raise ValueError("No housing model defined.")
        if self.education_model is None:
            raise ValueError("No education model defined.")
        if self.health_model is None:
            raise ValueError("No health model defined.")
        if self.transport_model is None:
            raise ValueError("No transport model defined.")
        if self.leisure_model is None:
            raise ValueError("No leisure model defined.")
        if self.labour_model is None:
            raise ValueError("No labour model defined.")
        if self.movement_model is None:
            raise ValueError("No location model defined.")
        if self.disease_model is None:
            raise ValueError("No disease model defined.")
        if self.interventions is None:
            raise ValueError("No interventions defined.")
        if self.intervention_schedules is None:
            raise ValueError("No interventions scheduler defined.")

        sim = Simulator(self.config, self.activity_manager, self.clock, self.map,
                        self.world, self.activity_model, self.housing_model, self.education_model,
                        self.health_model, self.transport_model, self.leisure_model,
                        self.labour_model, self.movement_model, self.disease_model,
                        self.interventions, self.intervention_schedules, telemetry_bus)

        return sim

    def to_file(self, output_filename: str) -> None:
        """Write an object to disk at the filename given.

        Parameters:
            output_filename (str):The filename to write to.  Files get overwritten
                                  by default.

        Returns:
            None
        """

        log.info("Writing to %s...", output_filename)
        # FIXME: error handling
        with open(output_filename, 'wb') as fout:
            pickle.dump(self, fout, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_file(input_filename: str) -> SimulationFactory:
        """Read an object from disk from the filename given.

        Parameters:
            input_filename (str):The filename to read from.

        Returns:
            obj(Object):The python object read from disk
        """

        log.info('Reading data from %s...', input_filename)
        with open(input_filename, 'rb') as fin:
            payload = pickle.load(fin)

        return payload
