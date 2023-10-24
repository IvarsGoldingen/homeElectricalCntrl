from abc import ABC, abstractmethod
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
file_handler = logging.FileHandler(os.path.join("logs", "observer_pattern.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

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

    def notify_observers(self, event_type):
        logger.debug(f"Notifying observers, event type: {event_type}")
        if event_type in self._observers:
            for observer in self._observers[event_type]:
                observer.handle_subject_event(event_type)

class Observer(ABC):
    def handle_subject_event(self, event_type: str):
        pass
