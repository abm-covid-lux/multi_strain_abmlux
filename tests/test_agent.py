"""Test the Agent object, which is pretty simple"""

import unittest
from ms_abmlux.agent import Agent
from ms_abmlux.location import Location

class TestAgent(unittest.TestCase):
    """Test the agent object, which stores agent config"""

    def test_agent_age_region(self):
        """Test that agents report as the correct type based on age"""

        expected = {0: "Luxembourg",
                    10: "Germany",
                    18: "France",
                    45: "Luxembourg",
                    65: "Belgium",
                    99: "France"}

        for age, region in expected.items():
            new_agent = Agent(age, region)
            assert new_agent.region == region
            assert new_agent.age == age

    def test_set_health(self):
        """Test setting of current activity"""

        test_agent = Agent(75, "Luxembourg")
        test_agent.set_health("Exposed")

        assert test_agent.health == "Exposed"

    def test_set_activity(self):
        """Test setting of current activity"""

        test_agent = Agent(15, "German")
        test_agent.set_activity("Test activity")

        assert test_agent.current_activity == "Test activity"

    def test_set_location(self):
        """Test setting of current location"""

        test_agent = Agent(55, "French")
        test_location = Location("Test location type", (0,0))

        test_agent.set_location(test_location)

        assert test_agent.current_location == test_location

    def test_add_activity_location(self):
        """Test assigning location to activity and recalling"""

        test_agent = Agent(34, "German")
        test_location_1 = Location("Test location type", (10,-3))
        test_location_2 = Location("Test location type", (13,-9))
        test_agent.add_activity_location("Test activity 1", test_location_1)
        test_agent.add_activity_location("Test activity 2", [test_location_1, test_location_2])

        assert test_agent.locations_for_activity("Test activity 1") == [test_location_1]
        assert test_agent.locations_for_activity("Test activity 2") == [test_location_1,
                                                                        test_location_2]
