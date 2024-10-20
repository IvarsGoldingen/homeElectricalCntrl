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

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "ahu.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def test():
    ahu = ValloxAhu("http://192.168.94.117/")
    cntr1 = 10
    cntr2 = 30
    try:
        while True:
            ahu.loop()
            time.sleep(1.0)
            cntr1 += 1
            cntr2 += 1
            if cntr1 >= 10:
                ahu.debug_printout()
                cntr1 = 0
            if cntr2 >= 30:
                ahu.req_new_data()
                cntr2 = 0
    except KeyboardInterrupt:
        logger.debug("KeyboardInterrupt caught. Exiting gracefully.")
    finally:
        ahu.stop()


@dataclass()
class ValloxSensorData:
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
    # Max new data request frequency
    _MAX_NEW_DATA_REQ_S = 300.0
    NO_DATA_VALUE = -99.99
    FAN_SPEED_NAME = "fan_speed"
    RH_NAME = "rh"
    CO2_NAME = "co2"
    T_INDOOR_NAME = "t_indoor_air"
    T_OUTDOOR_NAME = "t_outdoor_air"
    T_SUPPLY_NAME = "t_supply_air"
    T_EXHAUST_NAME = "t_exhaust_air"
    # For the observer pattern
    event_name_new_data = "ahu_new_data"

    def __init__(self, ip: str, auto_req_data_period_s: float = _MAX_NEW_DATA_REQ_S, name: str = "ahu"):
        # data available from the ahu device web interface
        super().__init__()
        self.ip = ip
        self.name = name
        self.fan_speed = Sensor(name=self.FAN_SPEED_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.rh = Sensor(name=self.RH_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.co2 = Sensor(name=self.CO2_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_indoor_air = Sensor(name=self.T_INDOOR_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_outdoor_air = Sensor(name=self.T_OUTDOOR_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_supply_air = Sensor(name=self.T_SUPPLY_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.t_exhaust_air = Sensor(name=self.T_EXHAUST_NAME, value=Sensor.NO_DATA_VALUE, group_name=name)
        self.sensor_data = ValloxSensorData(fan_speed=self.fan_speed,
                                            rh=self.rh,
                                            co2=self.co2,
                                            t_indoor_air=self.t_indoor_air,
                                            t_outdoor_air=self.t_outdoor_air,
                                            t_supply_air=self.t_supply_air,
                                            t_exhaust_air=self.t_exhaust_air)
        self.queue_to_webscrapping_thread = Queue()
        self.queue_from_webscrapping_thread = Queue()
        # Time since last data req
        self.last_data_req_time = 0.0
        self.auto_req_data_period_s = auto_req_data_period_s if auto_req_data_period_s <= self._MAX_NEW_DATA_REQ_S \
            else self._MAX_NEW_DATA_REQ_S
        self.ahu_web_thread = self.AhuWebScrapeThread(queue_to_webscrapping_thread=self.queue_to_webscrapping_thread,
                                                      queue_from_webscrapping_thread=self.queue_from_webscrapping_thread,
                                                      ip=ip,
                                                      sensors=self.sensor_data)
        self.ahu_web_thread.start()

    def get_sensor_list(self):
        ahu_sensors = []
        for sensor in fields(self.sensor_data):
            sensor_name = sensor.name
            sensor_obj = getattr(self.sensor_data, sensor_name)
            ahu_sensors.append(sensor_obj)
        return ahu_sensors

    def debug_printout(self):
        logger.debug(f"RH: {self.rh.value}")
        logger.debug(f"co2: {self.co2.value}")
        logger.debug(f"fan_speed: {self.fan_speed.value}")
        logger.debug(f"t_indoor_air: {self.t_indoor_air.value}")
        logger.debug(f"t_outdoor_air: {self.t_outdoor_air.value}")
        logger.debug(f"t_supply_air: {self.t_supply_air.value}")
        logger.debug(f"t_exhaust_air: {self.t_exhaust_air.value}")

    def loop(self):
        """
        Has to be called periodically
        """
        self.handle_msgs_from_ahu_web()
        self.auto_req_data()

    def auto_req_data(self):
        time_passed = time.perf_counter() - self.last_data_req_time
        if time_passed > self.auto_req_data_period_s:
            self.req_new_data()

    def req_new_data(self):
        self.last_data_req_time = time.perf_counter()
        self.queue_to_webscrapping_thread.put(self.AhuWebScrapeThread.MsgType.NEW_DATA_REQ)

    def stop(self):
        logger.info("Stopping ahu webscrape thread")
        self.queue_to_webscrapping_thread.put(self.AhuWebScrapeThread.MsgType.STOP)
        logger.debug("Before join")
        self.ahu_web_thread.join()
        logger.debug("After join")

    def handle_msgs_from_ahu_web(self):
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

        NO_DATA_VALUE = -99.99
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
            NEW_DATA_REQ = auto()

        def __init__(self, queue_to_webscrapping_thread: Queue,
                     queue_from_webscrapping_thread: Queue,
                     ip: str,
                     sensors: ValloxSensorData):
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
            self.queue_to_webscrapping_thread = queue_to_webscrapping_thread
            self.queue_from_webscrapping_thread = queue_from_webscrapping_thread
            self.ip = ip
            self.driver: Optional[webdriver.Firefox] = None

        def run(self):
            self.init_driver()
            self.handle_msgs()

        def handle_msgs(self):
            """
            Handle messages from the main device class
            Loop until stop is given
            """
            run = True
            while run:
                time.sleep(0.5)
                while not self.queue_to_webscrapping_thread.empty():
                    data = self.queue_to_webscrapping_thread.get()
                    if data == self.MsgType.NEW_DATA_REQ:
                        logger.debug("MsgType.NEW_DATA_REQ")
                        self.get_data()
                    elif data == self.MsgType.STOP:
                        logger.debug("MsgType.STOP")
                        self.close_driver()
                        run = False
                    else:
                        logger.error("Unknown value in queue webscrapper thread")
                        logger.error(data)

        def get_data(self):
            """
            Open AHU device web page, get the data and return in the queue
            """
            success = self.open_page()
            if success:
                sensor_dict = self.get_sensor_values()
                self.queue_from_webscrapping_thread.put(sensor_dict)

        def init_driver(self):
            """Initialise selenium driver"""
            logger.info("Initialising driver")
            options = Options()
            # so the UI of Firefox does not open
            options.add_argument('-headless')
            self.driver = webdriver.Firefox(options=options)
            logger.info("Initialising driver finished")

        def open_page(self):
            """
            open web interface of the ahu unit
            :return: true if success else false
            """
            logger.debug("Opening page")
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

        def get_sensor_values(self):
            """
            get sensor values of the previously opened page
            :return:
            """
            logger.debug(f"Getting values")
            value_dict = {}
            for sensor_name in self.sensor_xpath_dict:
                try:
                    element = self.driver.find_element(By.XPATH, self.sensor_xpath_dict[sensor_name])
                    value_str = element.text
                    value_numeric = self.extract_numeric_part(value_str)
                    value_dict[sensor_name] = value_numeric
                except NoSuchElementException:
                    logger.error(f"No such element: {sensor_name}")
                    value_dict[sensor_name] = self.NO_DATA_VALUE
            return value_dict

        def extract_numeric_part(self, str_value: str):
            # Extract numeric part from string were it starts with value and ends with
            # Regex used because values formatted differently: 15%, -12 °C, 790ppm
            # Regex allows for negative, positive values and floats as well
            match = re.match(r'^[-+]?\d*\.?\d+', str_value)
            # Check if a match is found
            if match:
                return match.group()
            else:
                logger.error("Could not convert string value to number")
                return self.NO_DATA_VALUE

        def close_driver(self):
            logger.info("Closing driver")
            try:
                self.driver.close()
            except Exception as e:
                logger.error("Closed with exception")
                logger.error(e)
            logger.info("Closed")


if __name__ == "__main__":
    test()
