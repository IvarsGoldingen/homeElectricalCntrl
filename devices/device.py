"""
Abstract class of a device which can be turned on or off
Has 2 modes:
Manual = controlled by user
Auto = controlled by program, algorthm etc.
"""
from abc import ABC, abstractmethod
from observer_pattern import Subject
import logging
import os

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "device.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


class Device(Subject):
    # TODO: use ENUM here
    STATUS_FAULT = 0
    STATUS_MAN_ON = 1
    STATUS_MAN_OFF = 2
    STATUS_AUTO_ON = 3
    STATUS_AUTO_OFF = 4
    STATUS_BLOCKED = 5
    MODE_AUTO = False
    MODE_MAN = True

    status_strings = {
        STATUS_FAULT: "Fault",
        STATUS_MAN_ON: "Manual On",
        STATUS_MAN_OFF: "Manual Off",
        STATUS_AUTO_ON: "Auto On",
        STATUS_AUTO_OFF: "Auto Off",
        STATUS_BLOCKED: "Blocked"
    }

    event_name_status_changed = "device_status_changed"

    def __init__(self, name: str = "Test_device"):
        # On or off setpoint for device which it listens to if it is the corresponding mode
        # _man_run always holds the current setpoint
        super().__init__()
        self._man_run = False
        self._auto_run = False
        # device will be turned off in either mode
        self._block = False
        self.name = name
        # if false device in auto mode if true in manual mode
        self.auto_man = False

    def set_mode(self, auto_man):
        self.auto_man = auto_man
        if not self.auto_man:
            # if switched to auto mode, write auto cmd to device
            self.set_auto_run(self._auto_run)
        self.notify_observers(self.event_name_status_changed)

    def set_block(self, block: bool):
        """
        block or unblock the device
        :param block: determines if device should be blocked or not
        :return:
        """
        self._block = block
        if block:
            # Set manual run dirrectly to represent the state desired on the device
            self._man_run = False
            # Turn off device if block request
            self._turn_device_off_on(False)
        self.notify_observers(self.event_name_status_changed)

    def set_manual_run(self, off_on: bool):
        """
        control the device in manual mode
        :param off_on: turn the device on or off - manual mode only
        :return:
        """
        if self.auto_man:
            # if device in manual mode allow control
            self._man_run = self._block_check(off_on)
            self._turn_device_off_on(self._man_run)
        self.notify_observers(self.event_name_status_changed)

    def get_cmd_given(self):
        # The final command is written in man_run so return that
        return self._man_run

    def set_auto_run(self, off_on: bool):
        """
        control the device in auto mode
        :param off_on: turn the device on or off - auto mode only
        :return:
        """
        if off_on != self._auto_run:
            self._auto_run = off_on
            self.notify_observers(self.event_name_status_changed)
        if not self.auto_man:
            # device in auto mode
            # write same to man run so when switching from auto to man does not change device state
            self._man_run = self._block_check(self._auto_run)
            self._turn_device_off_on(self._man_run)

    def get_status(self) -> int:
        """
        Status depending on device parameters not actual status
        :return: device status represented by int
        """
        if self._block:
            return self.STATUS_BLOCKED
        if self.auto_man:
            if self._man_run:
                return self.STATUS_MAN_ON
            else:
                return self.STATUS_MAN_OFF
        if not self.auto_man:
            if self._auto_run:
                return self.STATUS_AUTO_ON
            else:
                return self.STATUS_AUTO_OFF

    def _block_check(self, off_on: bool):
        """
        called before the turn on off method to check weather the device is not blocked
        :param off_on: the desired device state
        :return:
        """
        off_on_to_use = False if self._block else off_on
        return off_on_to_use

    @abstractmethod
    def _turn_device_off_on(self, off_on: bool):
        """
        Turn device on or off
        :param off_on: desired device state
        :return:
        """
        pass
