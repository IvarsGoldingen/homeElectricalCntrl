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
from observer_pattern import Subject

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("logs", "ahu.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
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


class ValloxAhu(Subject):
    """
    Class that webscrapes data from web interface of a Vallox recuperation unit
    Only sensor readings, not control
    """
    NO_DATA_VALUE = -99.99
    # Max new data request frequency
    _MAX_NEW_DATA_REQ_S = 300.0
    # For the observer pattern
    event_name_new_data = "ahu_new_data"

    def __init__(self, ip: str, auto_req_data_period_s: float = _MAX_NEW_DATA_REQ_S):
        # data available from the ahu device web interface
        super().__init__()
        self.ip = ip
        self.fan_speed = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.rh = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.co2 = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.t_indoor_air = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.t_outdoor_air = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.t_supply_air = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.t_exhaust_air = self.AhuWebScrapeThread.NO_DATA_VALUE
        self.queue_to_webscrapping_thread = Queue()
        self.queue_from_webscrapping_thread = Queue()
        # Time since last data req
        self.last_data_req_time = 0.0
        self.auto_req_data_period_s = auto_req_data_period_s if auto_req_data_period_s <= self._MAX_NEW_DATA_REQ_S \
            else self._MAX_NEW_DATA_REQ_S
        self.ahu_web_thread = self.AhuWebScrapeThread(queue_to_webscrapping_thread=self.queue_to_webscrapping_thread,
                                                      queue_from_webscrapping_thread=self.queue_from_webscrapping_thread,
                                                      ip=ip)
        self.ahu_web_thread.start()

    def debug_printout(self):
        logger.debug(f"RH: {self.rh}")
        logger.debug(f"co2: {self.co2}")
        logger.debug(f"fan_speed: {self.fan_speed}")
        logger.debug(f"t_indoor_air: {self.t_indoor_air}")
        logger.debug(f"t_outdoor_air: {self.t_outdoor_air}")
        logger.debug(f"t_supply_air: {self.t_supply_air}")
        logger.debug(f"t_exhaust_air: {self.t_exhaust_air}")

    def loop(self):
        """
        Has to be called periodically
        """
        self.handle_msgs_from_mqtt_client()
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

    def handle_msgs_from_mqtt_client(self):
        while not self.queue_from_webscrapping_thread.empty():
            logger.debug("New values received")
            sensor_values_dic = self.queue_from_webscrapping_thread.get()
            for sensor in sensor_values_dic:
                setattr(self, sensor, sensor_values_dic[sensor])
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
                     ip: str):
            super().__init__()
            #  Key names must equal to variable names
            self.data_element_dict = {
                "rh": self.ELEM_XPATH_RH,
                "co2": self.ELEM_XPATH_CO2,
                "fan_speed": self.ELEM_XPATH_FAN_SPEED,
                "t_indoor_air": self.ELEM_XPATH_T_IN,
                "t_outdoor_air": self.ELEM_XPATH_T_OUT,
                "t_supply_air": self.ELEM_XPATH_T_SUPPLY,
                "t_exhaust_air": self.ELEM_XPATH_T_EXHAUST,
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
            time.sleep(1.0)
            try:
                # Increased poll frequency because ahu sometimes hangs up
                WebDriverWait(self.driver, timeout=6, poll_frequency=2).until(EC.presence_of_element_located(
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
            for data in self.data_element_dict:
                try:
                    element = self.driver.find_element(By.XPATH, self.data_element_dict[data])
                    value_str = element.text
                    value_numeric = self.extract_numeric_part(value_str)
                    value_dict[data] = value_numeric
                except NoSuchElementException:
                    logger.error(f"No such element: {data}")
                    value_dict[data] = self.NO_DATA_VALUE
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
                # TODO: always getting error:
                """
                HTTPConnectionPool(host='localhost', port=57268): Max retries exceeded with url: 
                /session/c84807f0-afd5-48c7-ab93-0c859cc583a9/window 
                (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x0000014C61EBB390>: 
                Failed to establish a new connection: [WinError 10061] No connection could be made because the target
                machine actively refused it'))
                """
            except Exception as e:
                logger.error("Closed with exception")
                logger.error(e)
            logger.info("Closed")


if __name__ == "__main__":
    test()
