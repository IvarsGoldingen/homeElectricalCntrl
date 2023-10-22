"""
Application for controlling home automation:
*Control and monitoring of MQTT devices
*Creating schedules according to electricity price
TODO: Create tkinter widget for schedule
TODO: load devices, schedules etc from files, allow creation of new ones automatically
TODO: use device lists instead of single test device - same for schedule
TODO: Schedule by hours
TODO: Use listener design pattern


"""

import os
import time
import subprocess
from tkinter import Tk, Label, Button, StringVar, IntVar, Entry, Frame, Checkbutton, BooleanVar
import logging
from functools import partial
from devices.shellyPlugMqtt import ShellyPlug
from mqtt_client import MyMqttClient
from price_file_manager import PriceFileManager
from custom_tk_widgets.shelly_plug_widget import ShellyPlugWidget
from custom_tk_widgets.schedule_2_days_widget import Schedule2DaysWidget
from custom_tk_widgets.hourly_schedule_creator_widget import HourlyScheduleCreatorWidget
from schedules.hourly_schedule import HourlySchedule2days
from schedules.schedule_creator import ScheduleCreator
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
class MainUIClass(Tk):
    # How often should the status Queue be checked from the cam recorder process
    MAINLOOP_OTHER_INTERVAL_MS = 100
    # In how many mainloops should the device widgets be updated
    MAINLOOP_UPDATE_DEVICE_WIDGETS_MULTIPLIER = 5
    # In how many mainloops should the mqtt broker status be updated
    MAINLOOP_UPDATE_MQTT_CLIENT_MULTIPLIER = 4
    # In how many mainloops should the device_loops_be_called
    MAINLOOP_CALL_DEVICE_LOOPS_MULTIPLIER = 6
    # In how many mainloops should the schedule loops be called
    MAINLOOP_CALL_SCHEDULE_LOOPS_MULTIPLIER = 7
    # In how many mainloops should the price_mngr_be_called
    MAINLOOP_CALL_FILE_MNGR_LOOPS_MULTIPLIER = 51
    # UI constants
    BTN_WIDTH = 60
    HOUR_WIDTH = 6
    # For determining if checkbox of today or tomorrow pressed
    KEY_TODAY = 1
    KEY_TOMORROW = 2
    DUMMY_PRICE_VALUE = -99.99
    # Price file location
    PRICE_FILE_LOCATION = "C:\\py_related\\home_el_cntrl\\price_lists"

    def __init__(self):
        super().__init__()
        logger.info("Program started")
        # Variables that determine how often certain functions are called
        self.mainloop_cntr_widgets, self.mainloop_cntr_mqtt, self.mainloop_cntr_device_loops, \
            self.mainloop_cntr_schedule_loops, self.mainloop_cntr_price_mngr_loops = 0, 0, 0, 0, 0
        self.mqtt_client = MyMqttClient(secrets.MQTT_SERVER, secrets.MQTT_PORT, user=secrets.MQTT_USER,
                                        psw=secrets.MQTT_PSW)
        self.mqtt_client.start()
        self.setup_devices()
        self.setup_schedules()
        self.set_up_ui()
        self.price_mngr = PriceFileManager(self.PRICE_FILE_LOCATION, self.populate_ui_with_el_prices)
        self.mainloop()

    def mainloop_user(self):
        self.update_device_widgets()
        self.update_mqtt_status()
        self.call_schedule_loops()
        self.call_device_loops()
        self.price_manager_loop()
        # Start the loop again after delay
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def price_manager_loop(self):
        self.mainloop_cntr_price_mngr_loops += 1
        if self.mainloop_cntr_price_mngr_loops == self.MAINLOOP_CALL_FILE_MNGR_LOOPS_MULTIPLIER:
            self.mainloop_cntr_price_mngr_loops = 0
            self.price_mngr.loop()

    def call_schedule_loops(self):
        self.mainloop_cntr_schedule_loops += 1
        if self.mainloop_cntr_schedule_loops == self.MAINLOOP_CALL_SCHEDULE_LOOPS_MULTIPLIER:
            self.mainloop_cntr_schedule_loops = 0
            self.schedule_test.loop()

    def call_device_loops(self):
        self.mainloop_cntr_device_loops += 1
        if self.mainloop_cntr_device_loops == self.MAINLOOP_CALL_DEVICE_LOOPS_MULTIPLIER:
            self.mainloop_cntr_device_loops = 0
            self.plug.loop()

    def update_mqtt_status(self):
        """
        Update MQTT client status in the UI
        :return:
        """
        self.mainloop_cntr_mqtt += 1
        if self.mainloop_cntr_mqtt == self.MAINLOOP_UPDATE_MQTT_CLIENT_MULTIPLIER:
            self.mainloop_cntr_mqtt = 0
            new_text = self.mqtt_client.status_strings.get(self.mqtt_client.status, "UNKNOWN")
            self.lbl_status.config(text=new_text)

    def update_device_widgets(self):
        """
        Update device widgets in the UI
        :return:
        """
        self.mainloop_cntr_widgets += 1
        if self.mainloop_cntr_widgets == self.MAINLOOP_UPDATE_DEVICE_WIDGETS_MULTIPLIER:
            self.mainloop_cntr_widgets = 0
            self.plug_widget.update_widget()

    def setup_schedules(self):
        self.schedule_test = HourlySchedule2days("Test schedule")
        self.schedule_test.add_to_device_list(self.plug)

    def setup_devices(self):
        """
        Setup automation devices
        :return:
        """
        self.plug = ShellyPlug(name="Towel dryer",
                               mqtt_publish=self.mqtt_client.my_publish_callback,
                               plug_id="shellyplug-s-80646F840029")
        self.plug.set_mode(ShellyPlug.MODE_MAN)
        self.mqtt_client.add_to_subscription_dict(self.plug.listen_topic, self.plug.process_received_mqtt_data)

    def set_up_ui(self):
        # Set up user interface
        self.protocol("WM_DELETE_WINDOW", self.save_and_finish)
        self.title('Home control')
        self.prepare_ui_elements()
        self.place_ui_elements()
        self.after(self.MAINLOOP_OTHER_INTERVAL_MS, self.mainloop_user)

    def populate_ui_with_el_prices(self, prices_today: dict, prices_tomorrow: dict):
        "Set electrical price data in the user interface"
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
        self.frame_extra_btns = Frame(self)
        self.btn_1 = Button(self.frame_extra_btns, text='TEST 1', command=self.test_btn_1, width=self.BTN_WIDTH)
        self.btn_2 = Button(self.frame_extra_btns, text='TEST 2', command=self.test_btn_2, width=self.BTN_WIDTH)
        self.plug_widget = ShellyPlugWidget(parent=self, device=self.plug)
        self.schedule_widget = Schedule2DaysWidget(parent=self, schedule=self.schedule_test)
        create_schedule_callback = lambda max_total, hours_ahead, max_h, min_h: self.create_schedule(max_total,
                                                                                                     hours_ahead, max_h, min_h)
        self.schedule_creator_widget = HourlyScheduleCreatorWidget(parent=self, fc_to_call=create_schedule_callback)

    def create_schedule(self, max_total: float, hours_ahead: int, max_h: int, min_h: int):
        # TODO: continue here
        prices_today, prices_tomorrow = self.price_mngr.get_prices_today_tomorrow()
        schedule_today, schedule_tomorrow = ScheduleCreator.get_schedule_from_prices(prices_today, prices_tomorrow)
        self.schedule_test.set_schedule_full_day(today_tomorrow=False, schedule=schedule_today)
        self.schedule_test.set_schedule_full_day(today_tomorrow=True, schedule=schedule_tomorrow)


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
        self.plug_widget.grid(row=2, column=0)
        self.schedule_widget.grid(row=3, column=0)
        self.schedule_creator_widget.grid(row=4, column=0)

    def checkbox_value_changed(self, nr: int, day: int):
        """
        TODO: delete, moved to widget code?
        Called every time one of the checkboxes pressed
        :param day: today or tomorrow
        :param nr: checkbox representing which hour in that day
        :return:
        """
        if day == self.KEY_TODAY:
            value = self.checkbox_value_list_today[nr].get()
            self.schedule_test.set_schedule_hour_off_on(today_tomorrow=False, hour=nr, cmd=value)
        elif day == self.KEY_TOMORROW:
            value = self.checkbox_value_list_tomorrow[nr].get()
            self.schedule_test.set_schedule_hour_off_on(today_tomorrow=True, hour=nr, cmd=value)
        else:
            logger.error("Unknown day key")

    def test_btn_1(self):
        subprocess.Popen(['explorer', self.PRICE_FILE_LOCATION])

    def test_btn_2(self):
        logger.info("Inverting plug cmd")
        off_on = False if self.plug._man_run else True
        self.plug.set_manual_run(off_on)

    def save_and_finish(self):
        # Called on close of UI
        logger.info("UI closed")
        # Stpo MQTT client
        self.mqtt_client.stop()
        # Close tkinter UI
        self.destroy()


if __name__ == '__main__':
    main()
