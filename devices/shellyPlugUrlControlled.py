import logging
import os
import json
import queue
import time
from urllib.request import urlopen
from urllib.error import URLError
from devices.deviceTypes import DeviceType
from devices.urlControlledDevice import URLControlledDev
import settings

# Setup logger
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(settings.CONSOLE_LOG_LEVEL)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "URLcontrolledShelly.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test():
    logger.debug("Test")
    url_dev = URLControlledShellyPlug(
        url_off="http://172.31.0.246/relay/0?turn=off",
        url_on="http://172.31.0.246/relay/0?turn=on"
    )
    url_dev.set_mode(True)
    cntr = 0
    while True:
        if cntr % 10 == 0:
            if url_dev.get_cmd_given():
                print("Turning off")
                url_dev.set_manual_run(False)
            else:
                print("Turning on")
                url_dev.set_manual_run(True)
        url_dev.loop()
        print("looping")
        time.sleep(1)
        cntr += 1


class URLControlledShellyPlug(URLControlledDev):
    # if online recall url every 5 minutes
    RECALL_INTERVAL_STATE_ONLINE_S = 300
    # if offline attempt to call url once every minute
    RECALL_INTERVAL_STATE_OFFLINE_S = 60
    # For observer pattern
    event_name_new_extra_data = "device_new_extra_data"

    def __init__(self,
                 url_off: str,
                 url_on: str,
                 device_type: DeviceType = DeviceType.URL_CONTROLLED_SHELLY_PLUG,
                 name: str = "Test URL controlled device"):
        """
        @param url_off: Example shelly http://172.31.0.246/relay/0?turn=off
        @param url_on: Example shelly http://172.31.0.246/relay/0?turn=on
        """
        self.time_of_last_call = time.perf_counter()
        # On first URL call print error but not otherwise
        self.first_url_call = True
        super().__init__(url_off, url_on, device_type, name)

    def loop(self):
        self.check_url_call_queue()
        self.check_if_recall_needed()

    def check_if_recall_needed(self):
        time_passed_since_last_call = time.perf_counter() - self.time_of_last_call
        # Use shorter interval if previous call did not work
        time_to_check_for = URLControlledShellyPlug.RECALL_INTERVAL_STATE_ONLINE_S if self.state_online else \
            URLControlledShellyPlug.RECALL_INTERVAL_STATE_OFFLINE_S
        if time_passed_since_last_call > time_to_check_for:
            logger.debug("recheck")
            # call cmd again, to update its state
            self._turn_device_off_on(self._man_run)

    def check_url_call_queue(self):
        # Check for messages from URL call thread
        data_changed = False
        if not self.url_call_queue.empty():
            result = self.url_call_queue.get()
            success = result["Success"]
            data_changed = success != self.state_online
            # if successful then online
            self.state_online = success
            if self.state_online:
                is_on = result["ison"]
                if is_on != self.state_off_on:
                    self.device_notify(self.event_name_actual_state_changed, self.name, self.device_type)
                    data_changed = True
                self.state_off_on = is_on
        if data_changed:
            self.device_notify(self.event_name_new_extra_data, self.name, self.device_type)

    def call_url_threaded(self, url: str, return_queue: queue.Queue):
        """
        For shelly plug, answers are:
        {'ison': True, 'has_timer': False, 'timer_started': 0, 'timer_duration': 0,
        'timer_remaining': 0, 'overpower': False, 'source': 'http'}
        {'ison': False, 'has_timer': False, 'timer_started': 0, 'timer_duration': 0,
        'timer_remaining': 0, 'overpower': False, 'source': 'http'}
        """
        return_result = {"Success": False,
                         "ison": False}

        try:
            dev_reply = json.loads(urlopen(url, timeout=URLControlledDev.TIMEOUT_TIME_S).read())
            logger.debug(f"{self.name} URL call reply {dev_reply}")
            # consider success if shelly URL was reachable
            return_result["Success"] = True
            return_result["ison"] = dev_reply["ison"]
        except TimeoutError:
            self.log_url_call_error(f"Timeout device name {self.name} url {url}")
        except URLError:
            self.log_url_call_error(f"URL error device name: {self.name} url: {url}")
        except Exception as e:
            self.log_url_call_error(f"Other error when attempting to call URL device name {self.name} url {url}", e)
        self.first_url_call = False
        return_queue.put(return_result)

    def log_url_call_error(self, message: str, exception: Exception = None):
        """
        Log URL error only on first call or if device was online previously
        """
        if self.state_online or self.first_url_call:
            logger.error(message)
            if exception:
                logger.error(exception)


if __name__ == '__main__':
    test()
