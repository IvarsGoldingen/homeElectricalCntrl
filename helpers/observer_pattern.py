from abc import ABC, abstractmethod
import logging
import os
from devices.deviceTypes import DeviceType
import settings

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(settings.CONSOLE_LOG_LEVEL)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "observer_pattern.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)

"""
A Subject and Observer classes for implementing the observer pattern.
Example use cases:
A device(plug) would be the subject. The observer for it would be a widget in the UI. When both objects are created
the widget is registered to the plug. Any change on the device would be shown in UI.
"""


class Subject(ABC):
    def __init__(self):
        self._observers = {}

    def register(self, observer, event_type):
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(observer)

    def unregister(self, observer, event_type):
        if event_type in self._observers:
            self._observers[event_type].remove(observer)

    def notify_observers(self, event_type: str, *args, **kwargs):
        if event_type in self._observers:

            for observer in self._observers[event_type]:
                observer.handle_subject_event(event_type, *args, **kwargs)


class SimpleSubject(Subject):
    def simple_notify(self, event_name):
        self.notify_observers(event_name)


class DeviceSubject(Subject):
    def device_notify(self, event_name: str, device_name: str, device_type: DeviceType):
        logger.debug(f"Notifying device event_name {event_name}, device_name{device_name}, device_type {device_type}")
        self.notify_observers(event_name, device_name=device_name, device_type=device_type)


class Observer(ABC):
    def handle_subject_event(self, event_type: str, *args, **kwargs):
        pass
