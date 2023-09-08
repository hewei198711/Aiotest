# encoding: utf-8

from timeit import default_timer
from abc import ABCMeta, abstractmethod
from aiotest import runners


class LoadUserShape(metaclass=ABCMeta):
    """
    A simple load test shape class used to control the shape of load generated
    during a load test.
    """
    def __init__(self):
        self.start_time = default_timer()

    def reset_time(self):
        "Resets start time back to 0"
        self.start_time = default_timer()
    
    def get_run_time(self):
        "Calculates run time in seconds of the load user"
        return default_timer() - self.start_time
        
    @abstractmethod
    def tick(self):
        """
        Returns a tuple with 2 elements to control the running load user:
            user_count -- Total user count
            rate -- Number of users to start/stop per second when changing number of users
        if 'None' is returned then the running load user will be stopped.
        
        """
        return None
