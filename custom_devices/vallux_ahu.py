from dataclasses import dataclass,  fields
import logging
import os
from typing import Optional
import time
import re
import threading
from queue import Queue
from enum import Enum, auto
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from helpers.observer_pattern import Subject
from helpers.sensor import Sensor
import global_var
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
file_handler = logging.FileHandler(os.path.join("../logs", "ahu.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test():
    ahu = ValloxAhu("http://192.168.94.117/")
    cntr1 = 0
    cntr2 = 0
    try:
        while True:
            ahu.loop()
            time.sleep(1.0)
            # cntr1 += 1
            # cntr2 += 1
            # if cntr1 >= 10:
            #     ahu.debug_printout()
            #     cntr1 = 0
            # if cntr2 >= 30:
            #     ahu.req_new_data()
            #     cntr2 = 0
    except KeyboardInterrupt:
        logger.debug("KeyboardInterrupt caught. Exiting gracefully.")
    finally:
        logger.debug("Sending stop to ahu webscarping thread")
        ahu.stop()


@dataclass()
class ValloxSensorData:
    """
    Sensor data read from vallox AHU device
    """
    fan_speed: Sensor
    rh: Sensor
    co2: Sensor
    t_indoor_air: Sensor
    t_outdoor_air: Sensor
    t_supply_air: Sensor
    t_exhaust_air: Sensor


class ValloxAhu(Subject):
    """
    Class that webscrapes data from web interface of a Vallox recuperation unit
    Only sensor readings, no control
    """
    NO_DATA_VALUE = global_var.NO_DATA_VALUE
    # String names for variables
    FAN_SPEED_NAME = "fan_speed"
    RH_NAME = "rh"
    CO2_NAME = "co2"
    T_INDOOR_NAME = "t_indoor_air"
    T_OUTDOOR_NAME = "t_outdoor_air"
    T_SUPPLY_NAME = "t_supply_air"
    T_EXHAUST_NAME = "t_exhaust_air"
    # For the observer pattern
    event_name_new_data = "ahu_new_data"

    def __init__(self, ip: str, name: str = "ahu"):
        """
        :param ip: IP address of the web server
        :param name: name for the device
        """
        super().__init__()
        self.ip = ip
        self.name = name
        # create Sensor objects for data available from the ahu device web interface
        self.fan_speed = Sensor(name=self.FAN_SPEED_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.rh = Sensor(name=self.RH_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.co2 = Sensor(name=self.CO2_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_indoor_air = Sensor(name=self.T_INDOOR_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_outdoor_air = Sensor(name=self.T_OUTDOOR_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_supply_air = Sensor(name=self.T_SUPPLY_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_exhaust_air = Sensor(name=self.T_EXHAUST_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        # Put the sensor data in a single object
        self.sensor_data = ValloxSensorData(fan_speed=self.fan_speed,
                                            rh=self.rh,
                                            co2=self.co2,
                                            t_indoor_air=self.t_indoor_air,
                                            t_outdoor_air=self.t_outdoor_air,
                                            t_supply_air=self.t_supply_air,
                                            t_exhaust_air=self.t_exhaust_air)
        # Queues for data exchange between this and the webscraping thread
        self.queue_to_webscrapping_thread = Queue()
        self.queue_from_webscrapping_thread = Queue()
        # Thread that will be doing the webscaping
        self.ahu_web_thread = self.AhuWebScrapeThread(queue_to_webscrapping_thread=self.queue_to_webscrapping_thread,
                                                      queue_from_webscrapping_thread=self.queue_from_webscrapping_thread,
                                                      ip=ip,
                                                      sensors=self.sensor_data)
        self.ahu_web_thread.start()

    def get_sensor_list(self) -> list[Sensor]:
        """
        Used to get sensor list data in the main class
        :return: list of Sensors of the AHU device
        """
        ahu_sensors = []
        for sensor in fields(self.sensor_data):# type: ignore
            sensor_name = sensor.name
            sensor_obj = getattr(self.sensor_data, sensor_name)
            ahu_sensors.append(sensor_obj)
        return ahu_sensors

    def debug_printout(self) -> None:
        """
        Print sensor data for debuggin purposes
        """
        logger.debug(f"RH: {self.rh.value}")
        logger.debug(f"co2: {self.co2.value}")
        logger.debug(f"fan_speed: {self.fan_speed.value}")
        logger.debug(f"t_indoor_air: {self.t_indoor_air.value}")
        logger.debug(f"t_outdoor_air: {self.t_outdoor_air.value}")
        logger.debug(f"t_supply_air: {self.t_supply_air.value}")
        logger.debug(f"t_exhaust_air: {self.t_exhaust_air.value}")

    def loop(self) -> None:
        """
        Has to be called periodically
        Handles receiving data from the AHU webscraping thread
        """
        self.handle_msgs_from_ahu_web()

    def stop(self) -> None:
        """
        Stop reading of data
        """
        logger.info("Stopping ahu webscrape thread")
        self.queue_to_webscrapping_thread.put(self.AhuWebScrapeThread.MsgType.STOP)
        logger.debug("Before join")
        self.ahu_web_thread.join()
        logger.debug("After join")

    def handle_msgs_from_ahu_web(self) -> None:
        """
        Handles receiving data from the AHU webscraping thread
        """
        while not self.queue_from_webscrapping_thread.empty():
            logger.debug("New values received")
            sensor_values_dic = self.queue_from_webscrapping_thread.get()
            for sensor in sensor_values_dic:
                # Received dict keys are equal to sensor object names of this class
                # Use getattr to get needed sensor object of this class
                # the use set attr to set the new value
                setattr(getattr(self, sensor), 'value', sensor_values_dic[sensor])
            self.notify_observers(self.event_name_new_data)

    class AhuWebScrapeThread(threading.Thread):
        """
        Thread that will connect to AHU web server and  read the data and send it back to the main thread
        """
        RECONNECT_IF_DATA_NOT_CHANGED_FOR_S = 300
        MIN_TIME_BETWEEN_RECONNECTS_S = 600
        # How often to read data from the web page
        DATA_READ_PERIOD_S = 60
        NO_DATA_VALUE = global_var.NO_DATA_VALUE
        # Variables used to find values in the web page using selenium
        ELEM_XPATH_RH = "//div[@l10n-path='dashboard.profile.humidity']"
        ELEM_XPATH_CO2 = "//div[@l10n-path='dashboard.profile.co2']"
        ELEM_XPATH_FAN_SPEED = "//div[@l10n-path='dashboard.profile.fanspeed']"
        ELEM_XPATH_T_IN = "//div[@l10n-path='dashboard.now.indoor']"
        ELEM_XPATH_T_OUT = "//div[@l10n-path='dashboard.now.outdoor']"
        ELEM_XPATH_T_SUPPLY = "//div[@l10n-path='dashboard.now.supply']"
        ELEM_XPATH_T_EXHAUST = "//div[@l10n-path='dashboard.now.exhaust']"

        class MsgType(Enum):
            # Message types that can BE RECEIVED By the
            STOP = auto()

        def __init__(self, queue_to_webscrapping_thread: Queue,
                     queue_from_webscrapping_thread: Queue,
                     ip: str,
                     sensors: ValloxSensorData):
            """
            :param queue_to_webscrapping_thread: for receiving commands from main thread
            :param queue_from_webscrapping_thread: for sending data back to main thread
            :param ip: ip address of the web server
            :param sensors: sensor data of the AHU device
            """
            super().__init__()
            #  Key names must equal to variable names
            self.sensor_xpath_dict = {
                sensors.rh.name: self.ELEM_XPATH_RH,
                sensors.co2.name: self.ELEM_XPATH_CO2,
                sensors.fan_speed.name: self.ELEM_XPATH_FAN_SPEED,
                sensors.t_indoor_air.name: self.ELEM_XPATH_T_IN,
                sensors.t_outdoor_air.name: self.ELEM_XPATH_T_OUT,
                sensors.t_supply_air.name: self.ELEM_XPATH_T_SUPPLY,
                sensors.t_exhaust_air.name: self.ELEM_XPATH_T_EXHAUST,
            }
            # Create a dictionary of old data to check if data is changing
            self.sensor_data_old = {key:0 for key in self.sensor_xpath_dict.keys()}
            self.queue_to_webscrapping_thread = queue_to_webscrapping_thread
            self.queue_from_webscrapping_thread = queue_from_webscrapping_thread
            self.ip = ip
            # Selenium web driver
            self.driver: Optional[webdriver.Firefox] = None
            # Last time data was requested
            self.last_data_req_time = 0
            # Flag that indicates if connected to web page and if not reconnection happens
            self.connected_to_web_page = False
            # Time of last data change
            self.time_of_last_data_change = 0.0
            # Time of last connect attempt
            self.time_of_last_connection = 0.0

        def run(self):
            self.init_driver()
            self.main_loop()

        def main_loop(self):
            """
            Handle messages from the main device class
            Loop until stop is given
            """
            run = True
            while run:
                time.sleep(0.5)
                time_passed = time.perf_counter() - self.last_data_req_time
                if time_passed > self.DATA_READ_PERIOD_S:
                    # Enough time passed to attempt getting new values
                    logger.debug("Getting data from AHU web")
                    self.last_data_req_time = time.perf_counter()
                    self.get_data()
                while not self.queue_to_webscrapping_thread.empty():
                    # Check queu for messages from main thread
                    queue_msg = self.queue_to_webscrapping_thread.get()
                    if queue_msg == self.MsgType.STOP:
                        logger.debug("MsgType.STOP")
                        self.close_driver()
                        run = False
                    else:
                        logger.error("Unknown value in queue webscrapper thread")
                        logger.error(queue_msg)

        def get_data(self):
            """
            Open AHU device web page, get the data and return in the queue
            """
            if not self.connected_to_web_page:
                logger.debug("No connection to web page, attempting to make it")
                # If not connected, attempt connection
                self.connected_to_web_page = self.open_page()
            if self.connected_to_web_page:
                logger.debug("Connected to web page, getting values")
                sensor_dict = self.get_sensor_values()
                data_changed = self.check_if_values_changed(sensor_dict)
                if data_changed:
                    logger.debug("Sending data back to main thread")
                    # Send new data to main thread
                    self.queue_from_webscrapping_thread.put(sensor_dict)
                else:
                    self.check_time_since_no_data_changed()

        def check_if_values_changed(self, sensor_dict:dict) -> bool:
            """
            :param sensor_dict:
            :return: true if data changed
            """
            for old_value, new_value in zip(self.sensor_data_old.values(), sensor_dict.values()):
                if old_value != new_value:
                    logger.debug("Data has changed from the web page")
                    # A value has changed
                    self.time_of_last_data_change = time.perf_counter()
                    # Store new values in old ones
                    self.sensor_data_old = {key: sensor_dict[key] for key in self.sensor_data_old}
                    return True
            logger.debug("Data has NOT changed from the web page")
            # All data the same
            return False

        def check_time_since_no_data_changed(self) -> None:
            """
            If data has not changed for prolonged time set the flag connected_to_web_page to False so reconnection
            happens at next data check
            """
            time_passed = time.perf_counter() - self.time_of_last_data_change
            if time_passed > self.RECONNECT_IF_DATA_NOT_CHANGED_FOR_S:
                logger.warning("Data from web page has not changed for extensive time, requesting reconnect")
                self.connected_to_web_page = False

        def init_driver(self) -> None:
            """Initialise selenium driver"""
            logger.info("Initialising driver")
            options = Options()
            # so the UI of Firefox does not open
            options.add_argument('-headless')
            self.driver = webdriver.Firefox(options=options)
            logger.info("Initialising driver finished")

        def open_page(self) -> bool:
            """
            open web interface of the ahu unit
            :return: true if success else false
            """
            logger.debug("Opening page")
            time_passed_since_last_connection_attempt = time.perf_counter() - self.time_of_last_connection
            if time_passed_since_last_connection_attempt < self.MIN_TIME_BETWEEN_RECONNECTS_S:
                logger.info("Too early for another connection attempt")
                return False
            # Save time of connection attempt so they do not happen too often
            self.time_of_last_connection = time.perf_counter()
            try:
                self.driver.get(self.ip)
            except Exception as e:
                logger.error("Failed to connect to AHU")
                logger.error(e)
                return False
            logger.debug("Opened, delaying until dashboard controls found")
            # Sleep because AHU hangs up - possibly because instant polling
            time.sleep(4.0)
            try:
                # Increased poll frequency because ahu sometimes hangs up
                WebDriverWait(self.driver, timeout=30, poll_frequency=10).until(EC.presence_of_element_located(
                    (By.XPATH, "//div[@class='dashboard-controls']")))
                logger.debug("Dashboard controls found")
            except TimeoutException:
                logger.error("Dashboard controls was not found")
                return False
            return True

        def get_sensor_values(self) -> dict:
            """
            get sensor values of the previously opened page
            :return: dictionary where keys are sensor names and values are sensor readings as floats/ints
            """
            logger.debug(f"Getting values")
            value_dict = {}
            for sensor_name in self.sensor_xpath_dict:
                # Read sensors from the xpath dictionary
                try:
                    element = self.driver.find_element(By.XPATH, self.sensor_xpath_dict[sensor_name])
                    value_str = element.text
                    value_numeric = self.extract_numeric_part(value_str)
                    value_dict[sensor_name] = value_numeric
                except NoSuchElementException:
                    logger.error(f"No such element: {sensor_name}")
                    value_dict[sensor_name] = self.NO_DATA_VALUE
            return value_dict

        def extract_numeric_part(self, str_value: str) -> float:
            # Extract numeric part from string were it starts with value and ends with
            # Regex used because values formatted differently: 15%, -12 °C, 790ppm
            # Regex allows for negative, positive values and floats as well
            match = re.match(r'^[-+]?\d*\.?\d+', str_value)
            # Check if a match is found
            if match:
                # 2024.12.28 added cast to float
                try:
                    return float(match.group())
                except (ValueError, TypeError, Exception) as e:
                    logger.error(f"Could not convert to float: {e}")
            logger.error("Could not convert string value to number")
            return self.NO_DATA_VALUE

        def close_driver(self) -> None:
            logger.info("Closing driver")
            try:
                self.driver.close()
            except Exception as e:
                logger.error("Closed with exception")
                logger.error(e)
            logger.info("Closed")


if __name__ == "__main__":
    test()
