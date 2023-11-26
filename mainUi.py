"""
Application for controlling home automation:
*Control and monitoring of MQTT devices
*Creating schedules according to electricity price
TODO: implement AHU device
TODO: store data in DB
TODO: graphs for stored values (Grafana?)
TODO: load devices, schedules etc from files, allow creation of new ones automatically
TODO: Ability to associate devices with schedules from UI
TODO: MQTT security
"""

import os
from threading import Timer
import subprocess
from tkinter import Tk, Label, Button, Frame
import logging
from devices.shellyPlugMqtt import ShellyPlug
from devices.device import Device
from devices.deviceTypes import DeviceType
from mqtt_client import MyMqttClient
from price_file_manager import PriceFileManager
from custom_tk_widgets.shelly_plug_widget import ShellyPlugWidget
from custom_tk_widgets.schedule_2_days_widget import Schedule2DaysWidget
from schedules.hourly_schedule import HourlySchedule2days
from schedules.auto_schedule_creator import AutoScheduleCreator
from schedules.daily_timed_schedule import DailyTimedSchedule
from custom_tk_widgets.auto_hourly_schedule_creator_widget import AutoHourlyScheduleCreatorWidget
from custom_tk_widgets.daily_timed_schedule_widget import DailyTimedScheduleCreatorWidget
from observer_pattern import Observer
from data_logger import DataLogger
import secrets

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("logs", "main_ui.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def main():
    main = MainUIClass()


# Mainclass extends tkinter for creation of UI
class MainUIClass(Tk, Observer):
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
    DUMMY_PRICE_VALUE = -99.99
    # Price file location
    PRICE_FILE_LOCATION = "C:\\py_related\\home_el_cntrl\\price_lists"

    def __init__(self):
        super().__init__()
        logger.info("Program started")
        # Threads for repeated tasks
        self.device_thread, self.schedule_thread, self.price_mngr_thread, self.mqtt_thread = None, None, None, None
        self.mqtt_client = MyMqttClient()
        # UI displays MQTT status, subscribe to status changes
        self.mqtt_client.register(self, MyMqttClient.event_name_status_change)
        self.price_mngr = PriceFileManager(self.PRICE_FILE_LOCATION)
        self.price_mngr.register(self, PriceFileManager.event_name_prices_changed)
        self.setup_devices()
        self.setup_schedules()
        self.set_up_ui()
        self.setup_db_logger()
        # Start MQTT client only after all devices created, so the topics are listed
        self.mqtt_client.start(secrets.MQTT_SERVER, secrets.MQTT_PORT, user=secrets.MQTT_USER,
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

    def setup_db_logger(self):
        self.db_logger = DataLogger(get_prices_method=self.price_mngr.get_prices_today_tomorrow,
                                    device_list=self.dev_list)
        self.price_mngr.register(self.db_logger, PriceFileManager.event_name_prices_changed)
        for dev in self.dev_list:
            dev.register(self.db_logger, Device.event_name_status_changed)

    def mainloop_user(self):
        # Not used, instead Timer from Threading used
        # Start the loop again after delay
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def mqtt_threaded_loop(self):
        self.mqtt_client.loop()
        self.mqtt_thread = Timer(self.LOOP_MQTT_INTERVAL_S, self.mqtt_threaded_loop)
        self.mqtt_thread.start()

    def price_mngr_threaded_loop(self):
        # Execute this same function in regular intervals
        self.price_mngr.loop()
        self.price_mngr_thread = Timer(self.LOOP_PRICE_MNGR_INTERVAL_S, self.price_mngr_threaded_loop)
        self.price_mngr_thread.start()

    def schedule_threaded_loop(self):
        # Execute this same function in regular intervals
        self.schedule_2days.loop()
        self.auto_sch_creator.loop()
        self.alarm_clock.loop()
        self.christmas_lights.loop()
        self.schedule_thread = Timer(self.LOOP_SCHEDULE_INTERVAL_S, self.schedule_threaded_loop)
        self.schedule_thread.start()

    def device_threaded_loop(self):
        # Execute this same function in regular intervals
        for dev in self.dev_list:
            dev.loop()
        self.device_thread = Timer(self.LOOP_DEVICES_INTERVAL_S, self.device_threaded_loop)
        self.device_thread.start()

    def handle_subject_event(self, event_type: str, *args, **kwargs):
        logger.debug(f"Received event {event_type}")
        if event_type == PriceFileManager.event_name_prices_changed:
            self.populate_ui_with_el_prices()
        elif event_type == MyMqttClient.event_name_status_change:
            self.update_mqtt_status()

    def update_mqtt_status(self):
        """
        Update MQTT client status in the UI
        :return:
        """
        txt_color = "green" if self.mqtt_client.status == MyMqttClient.MqttClientThread.STATUS_CONNECTED else "red"
        new_text = self.mqtt_client.status_strings.get(self.mqtt_client.status, "UNKNOWN")
        self.lbl_status.config(text=new_text, fg=txt_color)

    def setup_schedules(self):
        self.schedule_2days = HourlySchedule2days("2 DAY SCHEDULE")
        # self.schedule_2days.add_to_device_list(self.plug1)
        self.auto_sch_creator = AutoScheduleCreator(get_prices_method=self.price_mngr.get_prices_today_tomorrow,
                                                    hourly_schedule=self.schedule_2days)
        self.alarm_clock = DailyTimedSchedule(name="Alarm clock")
        self.alarm_clock.add_device(self.plug1)
        self.christmas_lights = DailyTimedSchedule(name="Christmas lights")
        self.christmas_lights.add_device(self.plug2)


    def setup_devices(self):
        """
        Setup automation devices
        :return:
        """
        self.dev_list = []
        self.plug1 = ShellyPlug(name="Plug 1",
                                mqtt_publish=self.mqtt_client.publish,
                                plug_id="shellyplug-s-80646F840029")
        self.plug2 = ShellyPlug(name="Plug 2",
                                mqtt_publish=self.mqtt_client.publish,
                                plug_id="shellyplug-s-C8C9A3B8E92E")
        self.dev_list.append(self.plug1)
        self.dev_list.append(self.plug2)
        for dev in self.dev_list:
            if dev.device_type == DeviceType.SHELLY_PLUG:
                # if device is an MQTT device, register the topic that should be subscribed to and a callback
                # for receiving messages from that topic
                self.mqtt_client.add_listen_topic(dev.listen_topic, dev.process_received_mqtt_data)



    def set_up_ui(self):
        # Set up user interface
        self.protocol("WM_DELETE_WINDOW", self.save_and_finish)
        self.title('Home control')
        self.prepare_ui_elements()
        self.place_ui_elements()
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def populate_ui_with_el_prices(self):
        "Set electrical price data in the user interface"
        prices_today, prices_tomorrow = self.price_mngr.get_prices_today_tomorrow()
        price_list_today, price_list_tomorrow = [self.DUMMY_PRICE_VALUE] * 24, [self.DUMMY_PRICE_VALUE] * 24
        for hour, value in prices_today.items():
            price_list_today[hour] = value
        for hour, value in prices_tomorrow.items():
            price_list_tomorrow[hour] = value
        self.schedule_widget.add_extra_text_for_hours(price_list_today, price_list_tomorrow)

    def prepare_ui_elements(self):
        """
        Create UI elements
        """
        self.lbl_status = Label(self, text='MQTT STATUS')
        # Buttons for debuggin or extra features
        self.frame_extra_btns = Frame(self)
        self.btn_1 = Button(self.frame_extra_btns, text='OPEN PRICE FILE FOLDER',
                            command=self.open_price_file_folder, width=self.BTN_WIDTH)
        self.btn_2 = Button(self.frame_extra_btns, text='TEST 2', command=self.test_btn_2, width=self.BTN_WIDTH)
        self.frame_devices = Frame(self)
        # Place all widgets in one frame
        self.dev_widgets = []
        for dev in self.dev_list:
            if dev.device_type == DeviceType.SHELLY_PLUG:
                shelly_widget = ShellyPlugWidget(parent=self.frame_devices, device=dev)
                dev.register(shelly_widget, Device.event_name_status_changed)
                dev.register(shelly_widget, ShellyPlug.event_name_new_extra_data)
                self.dev_widgets.append(shelly_widget)
        # Create schedule widgets and register them as listeners for desired schedules
        self.schedule_widget = Schedule2DaysWidget(parent=self, schedule=self.schedule_2days)
        self.schedule_2days.register(self.schedule_widget, HourlySchedule2days.event_name_schedule_change)
        self.schedule_2days.register(self.schedule_widget, HourlySchedule2days.event_name_new_device_associated)
        self.frame_widgets_bottom = Frame(self)
        self.auto_schedule_creator_widget = AutoHourlyScheduleCreatorWidget(parent=self.frame_widgets_bottom,
                                                                            auto_schedule_creator=self.auto_sch_creator)
        self.alarm_clock_widget = DailyTimedScheduleCreatorWidget(parent=self.frame_widgets_bottom,
                                                                  sch=self.alarm_clock)
        self.alarm_clock.register(self.alarm_clock_widget, DailyTimedSchedule.event_name_schedule_change)
        self.alarm_clock.register(self.alarm_clock_widget, DailyTimedSchedule.event_name_new_device_associated)
        self.christmas_lights_widget = DailyTimedScheduleCreatorWidget(parent=self.frame_widgets_bottom,
                                                                  sch=self.christmas_lights)
        self.christmas_lights.register(self.christmas_lights_widget, DailyTimedSchedule.event_name_schedule_change)
        self.christmas_lights.register(self.christmas_lights_widget, DailyTimedSchedule.event_name_new_device_associated)

    def place_ui_elements(self):
        """
        Place created UI elements
        """
        # btns grid
        self.btn_1.grid(row=0, column=0)
        self.btn_2.grid(row=0, column=1)
        # Main grid
        self.lbl_status.grid(row=0, column=0)
        self.frame_extra_btns.grid(row=1, column=0)
        self.frame_devices.grid(row=2, column=0)
        for i, widget in enumerate(self.dev_widgets):
            widget.grid(row=0, column=i)
        self.schedule_widget.grid(row=3, column=0)
        self.frame_widgets_bottom.grid(row=4, column=0)
        self.auto_schedule_creator_widget.grid(row=0, column=0)
        self.alarm_clock_widget.grid(row=0, column=1)
        self.christmas_lights_widget.grid(row=0, column=2)

    def open_price_file_folder(self):
        subprocess.Popen(['explorer', self.PRICE_FILE_LOCATION])

    def test_btn_2(self):
        logger.info("Test btn 2")

    def save_and_finish(self):
        # Called on close of UI
        logger.info("UI closed")
        # Stop repeated tasks
        self.device_thread.cancel()
        self.schedule_thread.cancel()
        self.price_mngr_thread.cancel()
        self.mqtt_thread.cancel()
        # Stop DB manager
        self.db_logger.stop()
        # Stpo MQTT client
        self.mqtt_client.stop()
        # Close tkinter UI
        if hasattr(self, 'winfo_exists') and self.winfo_exists():
            self.destroy()


if __name__ == '__main__':
    main()
