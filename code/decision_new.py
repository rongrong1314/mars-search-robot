"""
Module for rover decision-handling.

Used to build a decision tree for determining throttle, brake and
steer commands based on the output of the perception_step() function
in the perception module.

"""

__author__ = 'Salman Hashmi'
__license__ = 'BSD License'


import time

import numpy as np

import states
import events


class DecisionHandler():
    """Handle events and switch between states."""

    def __init__(self):
        """Initialize a DecisionHandler instance."""
        # define the set of states
        self.state = {
            0: states.FindWall(),
            1: states.FollowWall(),
            2: states.AvoidWall(),
            3: states.TurnToWall(),
            4: states.GetUnstuck(),
            5: states.GoToSample(),
            6: states.Stop(),
            7: states.InitiatePickup(),
            8: states.WaitForPickupInitiate(),
            9: states.WaitForPickupFinish(),
            10: states.ReturnHome(),
            11: states.AvoidObstacles(),
            12: states.Park()
        }
        # define the set of events
        self.event = {
            'velocity_exceeded': events.velocity_exceeded,
            'front_path_clear': events.front_path_clear,
            'left_path_clear': events.left_path_clear,
            'pointed_at_nav': events.pointed_at_nav,
            'pointed_along_wall': events.pointed_along_wall,
            'deviated_from_wall': events.deviated_from_wall,
            'at_front_obstacle': events.at_front_obstacle,
            'at_left_obstacle': events.at_left_obstacle,
            'sample_on_left': events.sample_on_left,
            'sample_right_close': events.sample_right_close,
            'sample_in_view': events.sample_in_view,
            'pointed_at_sample': events.pointed_at_sample,
            'can_pickup_sample': events.can_pickup_sample,
            'completed_mission': events.completed_mission,
            'reached_home': events.reached_home
        }
        self.curr_state = self.state[0]  # default state

    def is_event(self, Rover, name):
        """Check if given event has occurred."""
        func = self.event.get(name)
        return func(Rover)

    def is_state(self, name):
        """Check if handler is in given state."""
        return name is self.curr_state

    def switch_to_state(self, Rover, name):
        """Update current state to the next state."""
        name.execute(Rover)
        self.curr_state = name

    def finding_wall(self, Rover):
        """Handle switching from FindWall state."""
        if Rover.yaw > 45 and Rover.yaw < 65:
            self.switch_to_state(Rover, self.state[1])  # FollowWall
        else:
            self.switch_to_state(Rover, self.curr_state)

    def following_wall(self, Rover):
        """Handle switching from FollowWall state."""
        if (self.is_event(Rover, 'deviated_from_wall') and
                self.is_event(Rover, 'left_path_clear')):
            self.switch_to_state(Rover, self.state[3])  # TurnToWall

        elif self.is_event(Rover, 'at_left_obstacle'):
            self.switch_to_state(Rover, self.state[2])  # AvoidWall

        elif (self.is_event(Rover, 'sample_on_left') or
                self.is_event(Rover, 'sample_right_close')):
            self.switch_to_state(Rover, self.state[5])  # GoToSample
        else:
            self.switch_to_state(Rover, self.curr_state)

    def avoiding_wall(self, Rover):
        """Handle switching from AvoidWall state."""
        if self.is_event(Rover, 'pointed_along_wall'):
            self.switch_to_state(Rover, self.state[1])  # FollowWall
        else:
            self.switch_to_state(Rover, self.curr_state)

    def going_to_sample(self, Rover):
        """Handle switching from GoToSample state."""
        if self.is_event(Rover, 'sample_in_view'):
            if Rover.near_sample:
                self.switch_to_state(Rover, self.state[6])  # Stop
            else:
                self.switch_to_state(Rover, self.curr_state)

    def stopped(self, Rover):
        """Handle switching from Stop state."""
        if self.is_event(Rover, 'can_pickup'):
            self.switch_to_state(Rover, self.state[7])  # InitiatePickup
        else:
            self.switch_to_state(Rover, self.curr_state)

    def initiating_pickup(self, Rover):
        """Handle switching from InitiatePickup state."""
        self.switch_to_state(Rover, self.state[8])  # WaitForPickupInitiate

    def waiting_pickup_initiate(self, Rover):
        """Handle switching from WaitForPickupInitiate state."""
        if Rover.picking_up == 1:
            self.switch_to_state(Rover, self.state[9])  # WaitForPickupFinish
        else:
            self.switch_to_state(Rover, self.curr_state)

    def waiting_pickup_finish(self, Rover):
        """Handle switching from WaitForPickupFinish state."""
        if Rover.picking_up == 0:
            self.switch_to_state(Rover, self.state[2])  # AvoidWall
        else:
            self.switch_to_state(Rover, self.curr_state)

    def returning_home(self, Rover):
        """Handle switching from ReturnHome state."""
        if self.is_event(Rover, 'at_front_obstacle'):
            self.switch_to_state(Rover, self.state[10])  # ReturnHome
        elif self.is_event(Rover, 'reached_home'):
            self.switch_to_state(Rover, self.state[12])  # Park
        else:
            self.next_state(Rover, self.curr_state)

    def parking(self, Rover):
        """Handle switching from Park state."""
        self.next_state(Rover, self.state[12])  # Reamin in Park

    def execute(self, Rover):
        """Select and execute the current state action."""
        pass
