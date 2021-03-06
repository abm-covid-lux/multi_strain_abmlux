"""This file constructs weekly routines using data of the same format as the most recent Time Use
Survey (TUS) of Luxembourg. Each respondent to the TUS provided two diaries of activities, one for a
week day and one for a weekend day, together with their age and the times at which these activities
began. Associated to each respondent there is also a statistical weight and an identification
number. Activities are denoted by a numeric code and therefore a daily routine consists of a
sequence of such numbers. Daily routines are then concatenated to produce, for each respondent, a
typical weekly routine. The week begins on Sunday and ends on Saturday."""

import logging

from collections import defaultdict
import pandas as pd
from tqdm import tqdm

import ms_abmlux.utils as utils
from ms_abmlux.activity_model import ActivityModel
from ms_abmlux.sim_time import SimClock
from ms_abmlux.activity_model.diary import DiaryDay, DiaryWeek, DayOfWeek

# Number of 10 minute chunks in a day. Used when parsing the input data at a 10 minute resolution
DAY_LENGTH_10MIN = 144

log = logging.getLogger('simple_activity_model')

#pylint: disable=unused-argument
#pylint: disable=attribute-defined-outside-init
class SimpleActivityModel(ActivityModel):
    """Uses Time Use Survey data to build a basic model of activities, which are cycled through
    in a set of routines."""

    def __init__(self, config, activity_manager, world, clock):

        super().__init__(config, activity_manager)

        self.activity_code_map        = config['activity_code_map']
        self.activities               = list(self.activity_code_map.keys())

        self.tick_length_s            = config['tick_length_s']
        self.age_bracket_length       = config['age_bracket_length']
        self.work_activity_type_int   = activity_manager.as_int(config['work_activity_type'])
        self.school_activity_type_int = activity_manager.as_int(config['school_activity_type'])

        self.weeks_changing_activity  = defaultdict(list)
        self.agents_by_week           = defaultdict(list)
        self.weeks_by_agent           = {}
        self.weeks                    = []

        """Determine a weekly routine for each agent and updates the world on which agents want to
        work and which agents want to go to school"""

        # Construct weeks
        self.weeks = self._create_weekly_routines()

        # Group weeks according to age
        weeks_by_age_bracket = defaultdict(dict)
        for week in self.weeks:
            weeks_by_age_bracket[week.age//self.age_bracket_length][week] = week.weight

        # Assign a weekly routine to each resident agent by random selection
        log.debug("Seeding week rountines and initial activities...")
        min_age_bracket = min(weeks_by_age_bracket.keys())
        max_age_bracket = max(weeks_by_age_bracket.keys())
        for agent in world.agents:
            if agent.region == config['region']:
                age_bracket = agent.age//self.age_bracket_length
                if age_bracket < min_age_bracket:
                    age_bracket_key = min_age_bracket
                elif age_bracket > max_age_bracket:
                    age_bracket_key = max_age_bracket
                else:
                    age_bracket_key = age_bracket
                weeks_sample = weeks_by_age_bracket[age_bracket_key]
                selected_week = self.prng.multinoulli_dict(weeks_sample)
                if self.work_activity_type_int in selected_week.weekly_routine:
                    agent.work_behaviour_type = True
                if self.school_activity_type_int in selected_week.weekly_routine:
                    agent.school_behaviour_type = True
                self.weeks_by_agent[agent] = selected_week
                self.agents_by_week[selected_week].append(agent)

        # Assign a weekly routine to each border worker
        border_worker_week = DiaryWeek('border_worker', -1, -1, config['border_worker_routine'])
        self.weeks.append(border_worker_week)
        for agent in world.agents:
            if agent.region != config['region']:
                self.weeks_by_agent[agent] = border_worker_week
                self.agents_by_week[border_worker_week].append(agent)

        # Set initial activities
        for agent in world.agents:
            new_activity = self.weeks_by_agent[agent].weekly_routine[clock.epoch_week_offset]
            agent.set_activity(new_activity)

    def init_sim(self, sim):
        super().init_sim(sim)

        clock = sim.clock

        # Hook into the simulation's messagebus
        self.bus.subscribe("notify.time.tick", self.send_activity_change_events, self)

        # Precalculate, at each time of the week, which weeks change activities
        for t_now in range(clock.ticks_in_week):
            if t_now == 0:
                t_previous = max(range(clock.ticks_in_week))
            else:
                t_previous = t_now - 1
            for week in self.weeks:
                if week.weekly_routine[t_now] != week.weekly_routine[t_previous]:
                    self.weeks_changing_activity[t_now].append(week)

    def send_activity_change_events(self, clock, t):
        """Update activities for those agents with routines chaning at this time."""

        ticks_through_week = clock.ticks_through_week()

        for week in self.weeks_changing_activity[ticks_through_week]:
            next_activity = week.weekly_routine[ticks_through_week]
            for agent in self.agents_by_week[week]:
                self.bus.publish("request.agent.activity", agent, next_activity)

    def _create_weekly_routines(self):
        """Create weekly routines for individuals, reading their daily routines
        as example days

        The format of the TUS data is such that each pair of daily diaries are listed consecutively,
        so for each person there are two rows, e.g:
        - personA: weekend
        - personA: weekday
        - personB: weekend
        - personB: weekday
        We don't know which way around these are, though.  This routine builds a week out of the
        weekday, repeated, plus the weekend.

        Parameters:
            days (list):List of ms_abmlux.DiaryDay objects representing individuals' routines from the
                        time-of-use survey daya

        Returns:
            weeks: A list of weekly routines built out of the daily routines.
        """

        # ------------------------------------------------------------------------------------------
        log.info("Loading time use data from %s...", self.config['time_use_filepath'])
        # TODO: force pandas to read the numeric ID columns as factors or ints
        #       same for weights
        tus = pd.read_csv(self.config['time_use_filepath'])
        tus = tus.dropna()

        # ------------------------------------------------------------------------------------------
        log.info('Generating daily routines...')

        # As mentioned above, activities are numerically coded. The file FormatsTUS displays the
        # codification of primary and secondary activities used by the TUS. The primary activities
        # will be grouped together according to datamap_primary while the secondary activities will
        # be grouped together according to datamap_secondary.
        #
        # The latter is used if and only if a respondent recorded 'Other specified location' as the
        # primary activity, in which case referal to the secondary activity is necessary. Activities
        # are consquently recoded as numbers in the set {0,...,13}, as described in the file
        # FormatActivities.

        map_func = self._get_tus_code_mapping(self.activity_code_map)
        days     = self._parse_days(tus, map_func, self.tick_length_s)
        log.info("Created %i days", len(days))

        # print('\n'.join([''.join([d[0] for d in days[x].daily_routine]) for x in \
        # range(len(days))]))
        # For each respondent there are now two daily routines; one for a week day and one for a
        # weekend day.  Copies of these routines are now concatenated so as to produce weekly
        # routines, starting on Sunday.

        # ------------------------------------------------------------------------------------------
        log.info("Generating weekly routines...")

        weeks = []
        for i in range(0, len(days)-1, 2):

            # Make a bold assumption
            weekend, weekday = days[i], days[i+1]

            # Swap if we were wrong
            if weekday.day in [DayOfWeek.SUNDAY, DayOfWeek.SATURDAY]:
                weekday, weekend = weekend, weekday

            # Check the identity is the same
            assert weekday.identity == weekend.identity

            # Create a week with most things the same, but with a whole week's worth of activities
            week = DiaryWeek(weekday.identity, weekday.age, weekday.weight,
                             weekend.daily_routine + weekday.daily_routine \
                             * 5 + weekend.daily_routine)
            weeks.append(week)
        log.info("Created %i weeks", len(weeks))

        return weeks

    def _get_tus_code_mapping(self, map_config):
        """Return a function mapping TUS activity codes onto those used in this model.

        TUS codes are defined in two fields, primary and secondary.
        If primary == 7, we switch to secondary.

        Primary and secondary mappings are defined in map_config as a dict
        of abm labels and primary/secondary keys containing a list of TUS
        codes, e.g.:

        {'House': {'primary': [1], 'secondary': [11,12,13,14]},
        'Work': {'primary': [2]}}

        The resulting function takes two arguments, namely the TUS primary
        and secondary codes, as ints.  It returns one of the keys
        from the mapping given to _this_ function.
        """
        # pylint doesn't like our primary, secondary shorthand below.
        # pylint: disable=invalid-name

        # Compute primary and secondary together.
        mapping_pri = {}
        mapping_sec = {}
        for abm_code, v in map_config.items():
            primary   = v['primary']   or [] if 'primary'   in v else []
            secondary = v['secondary'] or [] if 'secondary' in v else []

            for p in primary:
                mapping_pri[p] = self.activity_manager.as_int(abm_code)
            for s in secondary:
                mapping_sec[s] = self.activity_manager.as_int(abm_code)

        # Define mapping function, enclosing the above mapping
        def tus_activity_to_abm_activity(tus_pri, tus_sec):
            if tus_pri != 7:
                return mapping_pri[tus_pri]
            return mapping_sec[tus_sec]

        return tus_activity_to_abm_activity

    def _parse_days(self, tus, map_func, tick_length_s):
        """Returns a list of DiaryDay functions built from the TUS data provided.

        The following piece of code constructs the daily routines. This takes into account the fact
        that diaries appearing in the TUS do not all start at the same time and do not all run for
        24 hours.
        This is achieved by first extending the duration of the last activity, to create a 24 hour
        routine, after which the piece of the routine extending beyong the end of the day is
        repositioned to the start of the day. This way, all routines cover a 24 hour period running
        from midnight to midnight.

        Parameters:
            tus (pandas dataframe):The TUS dataset loaded from excel
            map_func (function):A function taking two ints and returning
                                the activity code for this row.
            tick_length_s:The length of ticks in the simulation, in seconds

        Returns:
            days(list):A list of DiaryDay objects.
        """
        # We use so many variables to be clearer in the parsing logic
        # pylint: disable=too-many-locals

        days  = []
        clock = SimClock(tick_length_s, 1)
        for date in tqdm(tus['id_jour'].unique()):
            tus_date  = tus.loc[tus['id_jour'] == date]
            durations = [y-x for x, y in
                         list(zip(tus_date['heuredebmin'], tus_date['heuredebmin'][1:]))]

            end_activity = map_func(tus_date.iloc[-1]['loc1_num_f'], tus_date.iloc[-1]['act1b_f'])
            start_time = tus_date.iloc[0]['heuredebmin']

            # Build variables for object at 10min resolution
            identity, age, day, weight = [tus_date.iloc[0][x]
                                          for x in ['id_ind', 'age', 'jours_f', 'poids_ind']]
            daily_routine_tenmin = [end_activity] * start_time \
                        + utils.flatten([[map_func(tus_date.iloc[i]['loc1_num_f'],
                                                   tus_date.iloc[i]['act1b_f'])] * d
                                         for i, d in enumerate(durations)]) \
                        + [end_activity] * (DAY_LENGTH_10MIN - sum(durations) - start_time)

            # Resample into the clock resolution
            log.debug("Resampling 10min chunks into clock resolution (%is)...", clock.tick_length_s)
            daily_routine = []
            clock.reset()
            for _ in clock:
                seconds_through_day = clock.seconds_elapsed()
                tenmin_bin = int(seconds_through_day / (10 * 60))
                daily_routine.append(daily_routine_tenmin[tenmin_bin])

            # Create the list entry
            day = DiaryDay(identity, age, day, weight, daily_routine)
            days.append(day)

        return days
