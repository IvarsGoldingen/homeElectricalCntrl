import json
import logging
import os
from abc import abstractmethod, ABC

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("/logs", "device.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def test():
    # base_path = "C:\\py_related\\home_el_cntrl\\state"
    # test = {"key1": 100,
    #         "key2": 34.5,
    #         "key3": "value_str"}
    # StateSaver.save_state_to_file(base_path, "test", test)
    # result = StateSaver.load_state_to_file(base_path, "test")
    # print(type(result))
    # print(result)
    test = TestClass(name="test2")
    test.save_state()
    test.load_state()


class StateSaver(ABC):
    FILE_NAME_EXTENSION = ".st"

    @abstractmethod
    def save_state(self):
        """
        Save class state
        """
        pass

    @abstractmethod
    def load_state(self):
        """
        Load class state
        """
        pass

    @staticmethod
    def save_state_to_file(base_path: str, name: str, data: dict):
        """
        Save some parameters to file so they can be restored on next program launch
        @param base_path: location of state file
        @param name: name of Class instance
        @param data: dictionary of state to save
        @return:
        """
        file_path = os.path.join(base_path, name + StateSaver.FILE_NAME_EXTENSION)
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file)
        except FileNotFoundError:
            logger.error(f"Invalid file path when saveing state: {file_path}")
        except Exception as e:
            logger.error(f"Unable to save state for file {file_path}. Error: {e}")

    @staticmethod
    def load_state_from_file(base_path: str, name: str) -> dict:
        """
        Load some parameters from file
        @param base_path: location of state file
        @param name: name of Class instance
        @return:
        """
        file_path = os.path.join(base_path, name + StateSaver.FILE_NAME_EXTENSION)
        if not os.path.exists(file_path):
            # State file does not exist, create one with default parameters
            logger.info(f"State file does not exist for {file_path}.")
            return None
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                return data
        except json.decoder.JSONDecodeError:
            logger.error(f"Unable to parse state data from {file_path}.")
        except Exception as e:
            logger.error(f"Unable to load state {file_path}. Error {e}")
        return None


class TestClass(StateSaver):

    def __init__(self, name: str = "test", state_file_loc: str = "C:\\py_related\\home_el_cntrl\\state"):
        self.state_1 = True
        self.state_2 = 13.1
        self.name = name
        self.state_file_loc = state_file_loc
        self.load_state()

    def save_state(self):
        state_to_save = {
            "state_1": self.state_1,
            "state_2": self.state_2
        }
        StateSaver.save_state_to_file(base_path=self.state_file_loc, data=state_to_save, name=self.name)

    def load_state(self):
        loaded_state = StateSaver.load_state_from_file(base_path=self.state_file_loc, name=self.name)
        if loaded_state is not None:
            try:
                self.state_1 = loaded_state["state_1"]
                self.state_2 = loaded_state["state_2"]
            except KeyError as e:
                logger.error(f"KeyError while loading state: {e}")
            except Exception as e:
                logger.error(f"Failed to load state. Error: {e}")
        else:
            logger.info(f"No state file for this object {self.name} in {self.state_file_loc}")


if __name__ == '__main__':
    test()
