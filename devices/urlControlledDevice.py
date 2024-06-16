"""
Abstract class that inherits from device class
For controlling/monitoring a device that can be accessed through an URL
Example smart plugs
"""

import logging
import os
import threading
import queue
import time
from abc import abstractmethod
from devices.device import Device
from devices.deviceTypes import DeviceType

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "URLControlledDev.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


class URLControlledDev(Device):
    TIMEOUT_TIME_S = 1.0

    def __init__(self,
                 url_off: str,
                 url_on: str,
                 device_type: DeviceType,
                 name: str = "Test URL controlled device"):
        """
        @param url_off:
        URL to call to turn device off
        Example shelly http://172.31.0.246/relay/0?turn=off
        @param url_on:
        URL to call to turn device on
        Example shelly http://172.31.0.246/relay/0?turn=on
        """
        self.state_online = False
        self.state_off_on = False
        self.url_off = url_off
        self.url_on = url_on
        # Queue to transfer data between mani thread and URL call therad
        self.url_call_queue = queue.Queue()
        self.url_thread = threading.Thread(target=self.call_url_threaded,
                                           args=("www.fakeurl.com", self.url_call_queue,))
        super().__init__(device_type, name)

    def _turn_device_off_on(self, off_on: bool):
        """
        Turn device on or off by calling the appropriate URL
        @param off_on: command
        @return:
        """
        if not self.url_thread.is_alive():
            # Only execute if previous call has ended
            if off_on:
                self.url_thread = threading.Thread(target=self.call_url_threaded,
                                                   args=(self.url_on, self.url_call_queue,))
            else:
                self.url_thread = threading.Thread(target=self.call_url_threaded,
                                                   args=(self.url_off, self.url_call_queue,))
            self.url_thread.start()
            # save time of last call so it is known when to recheck
            self.time_of_last_call = time.perf_counter()
        else:
            logger.warning(f"{self.name}: URL call thread is alive, cannot start another one")

    @abstractmethod
    def call_url_threaded(self, url: str, return_queue: queue.Queue):
        """
        Call the URL
        Implement depending on what device returns in its response.
        As bare minimum inform main thread if call was successful.
        @param url:
        @param return_queue:
        @return:
        """
        pass
