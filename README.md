# Multi-Strain ABMLUX
![Pytest](https://github.com/abm-covid-lux/multi_strain_abmlux/actions/workflows/python-package.yml/badge.svg)
![Pylint](https://github.com/abm-covid-lux/multi_strain_abmlux/workflows/Pylint/badge.svg)

This is a multi-strain version of the [ABMlux](https://github.com/abm-covid-lux/output) stochastic agent-based model of COVID-19.

![ABMLUX Logo](abmlux_logo.jpg)

## Overview
This model relies on time use survey data to automate the behaviour of agents.  Map, activity, disease, and intervention models are all modular and a number of alternative modules are bundled with the main distribution.  Scenarios for the model are configured using YAML, and a [comprehensive sample scenario] is provided in this repository.

The code is pure python, and has been developed with readability and maintainability in mind.

### Input Data
Input data are defined per-scenario in the [Scenarios](Scenarios/) directory.  A single [YAML configuration file](Scenarios/Luxembourg/config.yaml) specifies exact data locations and parameters for the simulation.  This file is heavily commented, and the example contains a very detailed use-case for all available modules.

## Requirements

 * python 3.9

## Usage

 * `pip install .`
 * `ms_abmlux Scenarios/Luxembourg/config.yaml`

## Testing
To test:

    pip install .[test]
    pytest

## Docs
To generate documentation:

    pip install pdoc
    pdoc --html --overwrite --html-dir docs ms_abmlux

There are a number of interfaces defined internally, which form the basis for pluggable modules through inheritance.  In addition to this, components communicate with the simulation engine via a messagebus, sending messages of two types:

 * _intent_ to change state, e.g. 'I wish to change this agent's location to xxx'
 * _action_ notifications updating the state of the world, e.g. 'Agent xxx has moved to location yyy'

Though it is possible to write new events, the [existing list of event types is documented here](docs/events.md).

## Citing This Work
The multi-strain ABMlux model is based on the original [ABMlux](https://github.com/abm-covid-lux/abmlux), an epidemic model which was used in the article Thompson, J. and Wattam, S. "Estimating the impact of interventions against COVID-19: from lockdown to vaccination", 2021, PLOS ONE, https://doi.org/10.1371/journal.pone.0261330.

If you publish using technology from this repository, please cite the above article using this BibTeX:

    @article{10.1371/journal.pone.0261330,
        doi = {10.1371/journal.pone.0261330},
        author = {Thompson, James AND Wattam, Stephen},
        journal = {PLOS ONE},
        publisher = {Public Library of Science},
        title = {Estimating the impact of interventions against COVID-19: From lockdown to vaccination},
        year = {2021},
        month = {12},
        volume = {16},
        url = {https://doi.org/10.1371/journal.pone.0261330},
        pages = {1-51},
        number = {12},
    }


## License
<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="Creative Commons Licence" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</a>.

Read the full text for details, but basically this means:
 * No commercial exploitation ([contact us](https://www.ms_abmlux.org) for another license in this case);
 * You must re-publish the source if you modify the application.

We would like this work to be useful to non-profit and academic users without significant effort.  If the license is an impediment to you using the work, please get in touch with us to discuss other licensing options.
