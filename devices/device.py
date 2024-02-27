"""
Abstract class of a device which can be turned on or off
Has 2 modes:
Manual = controlled by user
Auto = controlled by program, algorthm etc.
"""
from abc import abstractmethod
import logging
import os
from devices.deviceTypes import DeviceType
from helpers.observer_pattern import DeviceSubject
from helpers.state_saver import StateSaver


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


class Device(DeviceSubject, StateSaver):
    # Types of devices

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

    def __init__(self, device_type: DeviceType, name: str = "Test_device",
                 state_file_loc: str ="C:\\py_related\\home_el_cntrl\\state"):
        # On or off setpoint for device which it listens to if it is the corresponding mode
        # _man_run always holds the current setpoint
        super().__init__()
        self.state_file_loc = state_file_loc
        self._man_run = False
        self._auto_run = False
        # device will be turned off in either mode
        self._block = False
        self.name = name
        self.device_type = device_type
        # if false device in auto mode if true in manual mode
        self.auto_man = False
        self.load_state()

    def save_state(self):
        state_to_save = {
            "auto_man": self.auto_man,
            "_man_run": self._man_run,
            "_auto_run": self._auto_run
        }
        StateSaver.save_state_to_file(base_path=self.state_file_loc, data=state_to_save, name=self.name)

    def load_state(self):
        loaded_state = StateSaver.load_state_from_file(base_path=self.state_file_loc, name=self.name)
        if loaded_state is None:
            logger.info(f"No state file for this object {self.name} in {self.state_file_loc}")
            return
        try:
            self.auto_man = loaded_state["auto_man"]
            self._man_run = loaded_state["_man_run"]
            self._auto_run = loaded_state["_auto_run"]
            self.set_manual_run(self._man_run) if self.auto_man else self.set_auto_run(self._auto_run)
        except KeyError as e:
            logger.error(f"KeyError while loading state object {self.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load state object {self.name}. Error: {e}")

    def set_mode(self, auto_man):
        if auto_man != self.auto_man:
            self.auto_man = auto_man
            if not self.auto_man:
                # if switched to auto mode, write auto cmd to device
                self.set_auto_run(self._auto_run)
            self.device_notify(self.event_name_status_changed, self.name, self.device_type)
            self.save_state()



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
        self.device_notify(event_name=self.event_name_status_changed,
                           device_name=self.name,
                           device_type=self.device_type)

    def set_manual_run(self, off_on: bool):
        """
        control the device in manual mode
        :param off_on: turn the device on or off - manual mode only
        :return:
        """
        if not self.auto_man:
            # device in auto mode, manual control not possible
            return
        if off_on != self._man_run:
            # execute only if commande differs from current
            self._man_run = self._block_check(off_on)
            self._turn_device_off_on(self._man_run)
            self.device_notify(self.event_name_status_changed, self.name, self.device_type)
            self.save_state()

    def get_cmd_given(self):
        # The final command is written in man_run so return that
        return self._man_run

    def set_auto_run(self, off_on: bool):
        """
        control the device in auto mode
        :param off_on: turn the device on or off - auto mode only
        :return:
        """
        if self.auto_man:
            # device in manual mode, auto control not possible
            return
        if off_on != self._auto_run:
            self._auto_run = off_on
            # notify observers only if state changes
            self.device_notify(self.event_name_status_changed, self.name, self.device_type)
            self.save_state()
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
