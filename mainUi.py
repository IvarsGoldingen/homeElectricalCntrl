"""
Application for controlling home automation:
*Control and monitoring of MQTT devices
*Creating schedules according to electricity price
"""
import os
from threading import Timer
import subprocess
from tkinter import Tk, Label, Button, Frame
import logging
import global_var
from custom_devices.vallux_ahu import ValloxAhu
from devices.shelly3emEnergyMeterMqtt import ShellyEnergyMeter3em
from devices.shellyPlugMqtt import ShellyPlug
from devices.shellyPlus import ShellyPlus
from devices.shellyPlugUrlControlled import URLControlledShellyPlug
from devices.device import Device
from devices.deviceTypes import DeviceType
from helpers.mqtt_client import MyMqttClient
from helpers.price_file_manager import PriceFileManager
from custom_tk_widgets.shelly_plug_widget import ShellyPlugWidget
from custom_tk_widgets.shelly_plus_widget import ShellyPlusWidget
from custom_tk_widgets.shelly_plug_url_widget import ShellyPlugUrlWidget
from custom_tk_widgets.shelly_plus_pm_widget import ShellyPlusPmWidget
from custom_tk_widgets.schedule_2_days_widget import Schedule2DaysWidget
from schedules.hourly_schedule import HourlySchedule2days
from schedules.auto_schedule_creator import AutoScheduleCreator
from schedules.daily_timed_schedule import DailyTimedSchedule
from custom_tk_widgets.auto_hourly_schedule_creator_widget import AutoHourlyScheduleCreatorWidget
from custom_tk_widgets.daily_timed_schedule_widget import DailyTimedScheduleCreatorWidget
from custom_tk_widgets.ahu_widget import AhuWidget
from custom_tk_widgets.shelly_3em_widget import ShellyEmWidget
from helpers.observer_pattern import Observer
from helpers.data_logger import DataLogger
from system_setup.device_setup import get_device_list_from_file
from system_setup.schedule_setup import get_schedule_list_from_file
import secrets
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
file_handler = logging.FileHandler(os.path.join("logs", "main_ui.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def main() -> None:
    # App started as object initiated
    main = MainUIClass()


# Mainclass extends tkinter for creation of UI
class MainUIClass(Tk, Observer):
    # How often to log system values to database or other storage location
    PERIODICAL_LOG_INTERVAL_S = 60
    # How often call mainloop
    MAINLOOP_OTHER_INTERVAL_MS = 100
    # How often should device loops be called
    LOOP_DEVICES_INTERVAL_S = 1.0
    # How often should schedule loops be called
    LOOP_SCHEDULE_INTERVAL_S = 1.0
    # How often should the price manager be called
    LOOP_PRICE_MNGR_INTERVAL_S = 10.0
    # How often should the mqtt client loop be called
    LOOP_MQTT_INTERVAL_S = 0.3
    # UI constants
    BTN_WIDTH = 60
    # For determining if checkbox of today or tomorrow pressed
    KEY_TODAY = 1
    KEY_TOMORROW = 2
    DUMMY_PRICE_VALUE = global_var.NO_DATA_VALUE
    # Price file location
    PRICE_FILE_LOCATION = settings.PRICE_FILE_LOCATION
    # display price per kWh, default is per MWh
    DISPLAY_PRICE_PER_KWH = True

    def __init__(self) -> None:
        super().__init__()
        logger.info("Program started")
        # Threads for repeated tasks
        self.device_thread, self.schedule_thread, self.price_mngr_thread, self.mqtt_thread = None, None, None, None
        self.mqtt_client = MyMqttClient()
        # UI displays MQTT status, subscribe to status changes
        self.mqtt_client.register(self, MyMqttClient.event_name_status_change)
        # Object responsible for getting and storing electricity prices
        self.price_mngr = PriceFileManager(self.PRICE_FILE_LOCATION)
        self.price_mngr.register(self, PriceFileManager.event_name_prices_changed)
        # Setup devices of the system
        self.setup_devices()
        # Setup schedules that will control the devices
        self.setup_schedules()
        self.set_up_ui()
        self.setup_data_logger()
        # Start MQTT client only after all devices created, so the topics are listed
        self.mqtt_client.start(settings.MQTT_SERVER, settings.MQTT_PORT, user=secrets.MQTT_USER,
                               psw=secrets.MQTT_PSW)
        self.update_mqtt_status()
        # Call repeated tasks after creation of UI
        self.price_mngr_threaded_loop()
        self.device_threaded_loop()
        self.schedule_threaded_loop()
        self.mqtt_threaded_loop()
        try:
            self.mainloop()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt")

    def setup_data_logger(self) -> None:
        # List of Sensor objects  whose values will be stored
        all_sensors = []
        if settings.AHU_ENABLED:
            # If ahu enabled get all sensors from it
            ahu_sensors = self.ahu.get_sensor_list()
            all_sensors.extend(ahu_sensors)
        for dev in self.dev_list:
            # If device has Sensor object within it add to sensor list
            if dev.device_type == DeviceType.SHELLY_PRO_3EM:
                # Get sensors from energy meter
                # noinspection PyUnresolvedReferences
                all_sensors.extend(dev.get_sensors_as_list())
        logger.info("Sensor registered in system")
        for sensor in all_sensors:
            logger.info(sensor)
        # noinspection PyAttributeOutsideInit
        self.data_logger = DataLogger(get_prices_method=self.price_mngr.get_prices_today_tomorrow,
                                      device_list=self.dev_list,
                                      sensor_list=all_sensors,
                                      periodical_log_interval_s=self.PERIODICAL_LOG_INTERVAL_S)
        # Notify data loggger when new prices arrive
        self.price_mngr.register(self.data_logger, PriceFileManager.event_name_prices_changed)
        for dev in self.dev_list:
            if dev.device_type == DeviceType.SHELLY_PLUG or \
                    dev.device_type == DeviceType.SHELLY_PLUS or \
                    dev.device_type == DeviceType.SHELLY_PLUS_PM or \
                    dev.device_type == DeviceType.URL_CONTROLLED_SHELLY_PLUG:
                # Register state changes for devices
                dev.register(self.data_logger, Device.event_name_actual_state_changed)
            else:
                logger.error(f"Logging not implemented for {dev.device_type} in method setup_db_logger")

    def mainloop_user(self) -> None:
        # TKinter loop not used, instead Timer from Threading used
        # Start the loop again after delay
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def mqtt_threaded_loop(self) -> None:
        # Periodically call mqtt_client loop
        self.mqtt_client.loop()
        self.mqtt_thread = Timer(self.LOOP_MQTT_INTERVAL_S, self.mqtt_threaded_loop)
        self.mqtt_thread.start()

    def price_mngr_threaded_loop(self) -> None:
        # Periodically call price manager loop - checks for prices
        self.price_mngr.loop()
        self.price_mngr_thread = Timer(self.LOOP_PRICE_MNGR_INTERVAL_S, self.price_mngr_threaded_loop)
        self.price_mngr_thread.start()

    def schedule_threaded_loop(self) -> None:
        # Schedule related loops
        for sch in self.schedule_list:
            sch.loop()
        self.schedule_thread = Timer(self.LOOP_SCHEDULE_INTERVAL_S, self.schedule_threaded_loop)
        self.schedule_thread.start()

    def device_threaded_loop(self) -> None:
        # Device related loops
        for dev in self.dev_list:
            dev.loop()
        if settings.AHU_ENABLED:
            self.ahu.loop()
        self.device_thread = Timer(self.LOOP_DEVICES_INTERVAL_S, self.device_threaded_loop)
        self.device_thread.start()

    def handle_subject_event(self, event_type: str, *args, **kwargs) -> None:
        # Method for handling subject events. Observer pattern.
        logger.debug(f"Main received event: {event_type}")
        if event_type == PriceFileManager.event_name_prices_changed:
            self.populate_ui_with_el_prices()
        elif event_type == MyMqttClient.event_name_status_change:
            self.update_mqtt_status()

    def update_mqtt_status(self) -> None:
        # Update MQTT client status in the UI
        txt_color = "green" if self.mqtt_client.status == MyMqttClient.MqttClientThread.STATUS_CONNECTED else "red"
        new_text = self.mqtt_client.status_strings.get(self.mqtt_client.status, "UNKNOWN")
        self.lbl_status.config(text=new_text, fg=txt_color)

    def setup_schedules(self) -> None:
        self.schedule_list = get_schedule_list_from_file(get_prices_method=self.price_mngr.get_prices_today_tomorrow,
                                                         dev_list=self.dev_list,
                                                         file_path=os.path.join(settings.SCH_CONFIG_FILE_LOCATION,
                                                                                # type: ignore
                                                                                settings.SCH_CONFIG_FILE_NAME))

    # noinspection PyAttributeOutsideInit
    def setup_devices(self) -> None:
        # Setup automation devices
        self.dev_list = get_device_list_from_file(mqtt_publish_method=self.mqtt_client.publish,
                                                  file_path=os.path.join(settings.DEV_CONFIG_FILE_LOCATION,
                                                                         # type: ignore
                                                                         settings.DEV_CONFIG_FILE_NAME))
        for dev in self.dev_list:
            if dev.device_type == DeviceType.SHELLY_PLUG or \
                    dev.device_type == DeviceType.SHELLY_PLUS or \
                    dev.device_type == DeviceType.SHELLY_PLUS_PM or \
                    dev.device_type == DeviceType.SHELLY_PRO_3EM:
                # if device is an MQTT device, register the topic that should be subscribed to and a callback
                # for receiving messages from that topic
                self.mqtt_client.add_listen_topic(dev.listen_topic, dev.process_received_mqtt_data)  # type: ignore
        if settings.AHU_ENABLED:
            self.ahu = ValloxAhu(ip="http://192.168.94.117/")

    def set_up_ui(self) -> None:
        # Set up user interface
        self.protocol("WM_DELETE_WINDOW", self.save_and_finish)
        self.title('Home control')
        self.prepare_ui_elements()
        self.place_ui_elements()
        # Start TKinter inherited inbuilt loop
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def populate_ui_with_el_prices(self) -> None:
        # Set electrical price data in the user interface
        # Values received as dictionaries, widget needs a list
        prices_today, prices_tomorrow = self.price_mngr.get_prices_today_tomorrow()
        # Have dummy values ready for items that are not received
        price_list_today, price_list_tomorrow = [self.DUMMY_PRICE_VALUE] * 24, [self.DUMMY_PRICE_VALUE] * 24
        for hour, value in prices_today.items():
            price_list_today[hour] = value
        for hour, value in prices_tomorrow.items():
            price_list_tomorrow[hour] = value
        # TODO: Handle getting the widget better - add class attribute associate prices or something
        # Find 2 day schedule which should show electricity prices
        schedule_2day_w_prices = next(
            (sch_widget for sch_widget in self.sch_widgets if isinstance(sch_widget, Schedule2DaysWidget)), None)
        # Set the prices on the schedule so they are visible in the UI
        if schedule_2day_w_prices:
            schedule_2day_w_prices.add_price_to_hourly_checkbox_label(price_list_today, price_list_tomorrow)

    # noinspection PyAttributeOutsideInit
    def prepare_ui_elements(self) -> None:
        # Create UI elements
        self.lbl_status = Label(self, text='MQTT STATUS')
        # Buttons for debuggin or extra features
        self.frame_extra_btns = Frame(self)
        self.btn_1 = Button(self.frame_extra_btns, text='OPEN PRICE FILE FOLDER',
                            command=self.open_price_file_folder, width=self.BTN_WIDTH)
        self.btn_2 = Button(self.frame_extra_btns, text='TEST 2', command=self.test_btn, width=self.BTN_WIDTH)
        self.setup_device_widgets_from_list()
        if settings.AHU_ENABLED:
            # Ahu widget
            self.ahu_widget = AhuWidget(parent=self.frame_devices, ahu=self.ahu)
            self.ahu.register(self.ahu_widget, ValloxAhu.event_name_new_data)
        self.setup_schedule_widgets_from_list()

    # noinspection PyAttributeOutsideInit
    def setup_device_widgets_from_list(self):
        self.frame_devices = Frame(self)
        # Store all widgets in a list to place in one TKinter frame
        self.dev_widgets = []
        for dev in self.dev_list:
            # For each device type create the apropriate widget and register listeners to those widgets
            if dev.device_type == DeviceType.SHELLY_PLUG:
                shelly_widget = ShellyPlugWidget(parent=self.frame_devices, device=dev)  # type: ignore
                dev.register(shelly_widget, Device.event_name_status_changed)
                dev.register(shelly_widget, ShellyPlug.event_name_new_extra_data)
                self.dev_widgets.append(shelly_widget)
            elif dev.device_type == DeviceType.SHELLY_PLUS:
                shelly_plus_widget = ShellyPlusWidget(parent=self.frame_devices, device=dev)  # type: ignore
                dev.register(shelly_plus_widget, Device.event_name_status_changed)
                dev.register(shelly_plus_widget, ShellyPlus.event_name_new_extra_data)
                dev.register(shelly_plus_widget, ShellyPlus.event_name_input_state_change)
                self.dev_widgets.append(shelly_plus_widget)
            elif dev.device_type == DeviceType.SHELLY_PLUS_PM:
                shelly_plus_pm_widget = ShellyPlusPmWidget(parent=self.frame_devices, device=dev)  # type: ignore
                dev.register(shelly_plus_pm_widget, Device.event_name_status_changed)
                dev.register(shelly_plus_pm_widget, ShellyPlus.event_name_new_extra_data)
                dev.register(shelly_plus_pm_widget, ShellyPlus.event_name_input_state_change)
                self.dev_widgets.append(shelly_plus_pm_widget)
            elif dev.device_type == DeviceType.URL_CONTROLLED_SHELLY_PLUG:
                shelly_url_widget = ShellyPlugUrlWidget(parent=self.frame_devices, device=dev)  # type: ignore
                dev.register(shelly_url_widget, Device.event_name_status_changed)
                dev.register(shelly_url_widget, URLControlledShellyPlug.event_name_new_extra_data)
                self.dev_widgets.append(shelly_url_widget)
            elif dev.device_type == DeviceType.SHELLY_PRO_3EM:
                shelly_em_widget = ShellyEmWidget(parent=self.frame_devices, device=dev)  # type: ignore
                dev.register(shelly_em_widget, ShellyEnergyMeter3em.event_name_new_extra_data)
                self.dev_widgets.append(shelly_em_widget)
            else:
                logger.warning(f"Device list contains device without widget associated to its type {dev.name}")

    # noinspection PyAttributeOutsideInit
    def setup_schedule_widgets_from_list(self):
        # Create schedule widgets and register them as listeners for desired schedules
        self.sch_widgets = []
        self.frame_widgets_bottom = Frame(self)
        for sch in self.schedule_list:
            if isinstance(sch, HourlySchedule2days):
                hourly_2day_widget = Schedule2DaysWidget(parent=self,
                                                         schedule=sch,
                                                         display_price_per_kwh=MainUIClass.DISPLAY_PRICE_PER_KWH)
                sch.register(hourly_2day_widget, HourlySchedule2days.event_name_schedule_change)
                sch.register(hourly_2day_widget, HourlySchedule2days.event_name_new_device_associated)
                sch.register(hourly_2day_widget, HourlySchedule2days.event_name_hour_changed)
                self.sch_widgets.append(hourly_2day_widget)
            elif isinstance(sch, AutoScheduleCreator):
                auto_sch_creator = AutoHourlyScheduleCreatorWidget(parent=self.frame_widgets_bottom,
                                                                   auto_schedule_creator=sch,
                                                                   display_price_per_kwh=MainUIClass.DISPLAY_PRICE_PER_KWH)
                self.sch_widgets.append(auto_sch_creator)
            elif isinstance(sch, DailyTimedSchedule):
                daily_timed_sch = DailyTimedScheduleCreatorWidget(parent=self.frame_widgets_bottom,
                                                                  sch=sch)
                sch.register(daily_timed_sch, DailyTimedSchedule.event_name_schedule_change)
                sch.register(daily_timed_sch, DailyTimedSchedule.event_name_new_device_associated)
                self.sch_widgets.append(daily_timed_sch)
            else:
                logger.error("Unknown schedule in schedule list")
                raise Exception("Unknown schedule in schedule list")

    def place_ui_elements(self) -> None:
        # Place created UI elements
        # Main grid  - label
        self.lbl_status.grid(row=0, column=0)
        # Buttons grid
        self.frame_extra_btns.grid(row=1, column=0)
        self.btn_1.grid(row=0, column=0)
        self.btn_2.grid(row=0, column=1)
        self.frame_devices.grid(row=2, column=0)
        last_socket_widget = 0
        # Place device widgets in frame
        for i, widget in enumerate(self.dev_widgets):
            widget.grid(row=0, column=i)
            # Save location so next free position is known
            last_socket_widget += 1
        if settings.AHU_ENABLED:
            self.ahu_widget.grid(row=0, column=last_socket_widget)
        # At which row start placing schedules
        row_to_use = 3
        last_small_sch_widget = 0
        for widget in self.sch_widgets:
            if isinstance(widget, Schedule2DaysWidget):
                # Large widget place in separate row
                widget.grid(row=row_to_use, column=0)
                row_to_use += 1
            else:
                # small widgets go on the widgets frame
                widget.grid(row=0, column=last_small_sch_widget)
                # Save location so next free position is known
                last_small_sch_widget += 1
        self.frame_widgets_bottom.grid(row=row_to_use, column=0)

    def open_price_file_folder(self) -> None:
        subprocess.Popen(['explorer', self.PRICE_FILE_LOCATION])

    def test_btn(self) -> None:
        logger.info("Test btn 2")

    def save_and_finish(self) -> None:
        # Called on close of UI
        logger.info("UI closed")
        # Stop repeated tasks
        self.device_thread.cancel()
        self.schedule_thread.cancel()
        self.price_mngr_thread.cancel()
        self.mqtt_thread.cancel()
        # Stop DB manager
        self.data_logger.stop()
        # Stpo MQTT client
        self.mqtt_client.stop()
        if settings.AHU_ENABLED:
            # Stop AHU data read
            self.ahu.stop()
        # Close tkinter UI
        if hasattr(self, 'winfo_exists') and self.winfo_exists():
            self.destroy()


if __name__ == '__main__':
    main()
