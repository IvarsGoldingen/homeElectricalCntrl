from functools import partial
import os
import logging
import tkinter as tk
from tkinter import Label, font, Frame, Checkbutton, BooleanVar
from schedules.hourly_schedule import HourlySchedule2days
from observer_pattern import Observer

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
file_handler = logging.FileHandler(os.path.join("logs", "2_day_widget.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


class Schedule2DaysWidget(tk.Frame, Observer):
    """
    UI widget for HourlySchedule2days object
    Displays 2 day schedule. Each checkbox represents an hour in today and tomorrow. If schecbox active, the device
    associated with the schedule should be turned on.
    """
    # UI constants
    HOUR_WIDTH = 6
    # For determining if checkbox of today or tomorrow pressed
    KEY_TODAY = 1
    KEY_TOMORROW = 2

    def __init__(self, parent, schedule: HourlySchedule2days):
        super().__init__(parent, borderwidth=2, relief="solid")
        # SChedule asociated with the widget
        self.schedule = schedule
        # UI objects containing the checkboxes
        self.frame_list_today, self.lbl_check_box_list_today, self.checkbox_value_list_today, \
            self.checkbox_list_today = [], [], [], []
        self.frame_list_tomorrow, self.lbl_check_box_list_tomorrow, self.checkbox_value_list_tomorrow, \
            self.checkbox_list_tomorrow = [], [], [], []
        self.frame_today, self.frame_tomorrow = Frame(self), Frame(self)
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()

    def _place_widget_elements(self):
        for nr, frame in enumerate(self.frame_list_today):
            self.lbl_check_box_list_today[nr].grid(row=0, column=0)
            self.checkbox_list_today[nr].grid(row=1, column=0)
            frame.grid(row=0, column=nr)
        # checkbox tomorrow list
        for nr, frame in enumerate(self.frame_list_tomorrow):
            self.lbl_check_box_list_tomorrow[nr].grid(row=0, column=0)
            self.checkbox_list_tomorrow[nr].grid(row=1, column=0)
            frame.grid(row=0, column=nr)
        self.lbl_name.grid(row=0, column=0)
        self.lbl_associated_device.grid(row=1, column=0)
        self.frame_today.grid(row=2, column=0)
        self.frame_tomorrow.grid(row=3, column=0)

    def _prepare_widget_elements(self):
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_name = Label(self, text=self.schedule.name, font=bold_font)
        self.lbl_associated_device = Label(self, text="No devices associated with schedule")
        for i in range(24):
            self.frame_list_today.append(Frame(self.frame_today))
            self.checkbox_value_list_today.append(BooleanVar())
            self.checkbox_list_today.append(Checkbutton(self.frame_list_today[i],
                                                        variable=self.checkbox_value_list_today[i],
                                                        onvalue=True,
                                                        offvalue=False,
                                                        command=partial(self.checkbox_value_changed,
                                                                        nr=i, day=self.KEY_TODAY)))
            self.lbl_check_box_list_today.append(Label(self.frame_list_today[i], text=f"{i:02}:00",
                                                       width=self.HOUR_WIDTH))
            self.frame_list_tomorrow.append(Frame(self.frame_tomorrow))
            self.checkbox_value_list_tomorrow.append(BooleanVar())
            self.checkbox_list_tomorrow.append(Checkbutton(self.frame_list_tomorrow[i],
                                                           variable=self.checkbox_value_list_tomorrow[i],
                                                           onvalue=True,
                                                           offvalue=False,
                                                           command=partial(self.checkbox_value_changed,
                                                                           nr=i, day=self.KEY_TOMORROW)))
            self.lbl_check_box_list_tomorrow.append(Label(self.frame_list_tomorrow[i], text=f"{i:02}:00",
                                                          width=self.HOUR_WIDTH))

    def handle_subject_event(self, event_type: str):
        # The subject has notified this of an event
        logger.debug(f"Widget notified of an event {event_type}")
        self.update_widget()

    def update_widget(self):
        self.update_checkboxes()
        self.update_associated_device()

    def update_associated_device(self):
        # Add text to widget which displays which devices does the schedule control
        text = "No devices associated with schedule" if not self.schedule.device_list else \
            f"Associated devices: {', '.join(dev.name for dev in self.schedule.device_list)}"
        self.lbl_associated_device.config(text=text)

    def update_checkboxes(self):
        for checkbox_value, hour_off_on in zip(self.checkbox_value_list_today, self.schedule.schedule_today.values()):
            checkbox_value.set(hour_off_on)
        for checkbox_value, hour_off_on in zip(self.checkbox_value_list_tomorrow,
                                               self.schedule.schedule_tomorrow.values()):
            checkbox_value.set(hour_off_on)

    def add_extra_text_for_hours(self, text_list_today: list, text_list_tomorrow: list):
        logger.debug("Adding extra text for hours")
        if len(text_list_today) != 24 or len(text_list_tomorrow) != 24:
            logger.error("Unexpected additional text list for hours")
            # expected new text for each hour
            return
        for hour, (lbl, extra_text) in enumerate(zip(self.lbl_check_box_list_today, text_list_today)):
            lbl.config(text=f"{hour:02}:00\r{extra_text}")
        for hour, (lbl, extra_text) in enumerate(zip(self.lbl_check_box_list_tomorrow, text_list_tomorrow)):
            lbl.config(text=f"{hour:02}:00\r{extra_text}")

    def checkbox_value_changed(self, nr: int, day: int):
        """
        Called every time one of the checkboxes pressed
        :param day: today or tomorrow
        :param nr: checkbox representing which hour in that day
        :return:
        """
        if day == self.KEY_TODAY:
            value = self.checkbox_value_list_today[nr].get()
            self.schedule.set_schedule_hour_off_on(today_tomorrow=False, hour=nr, cmd=value)
        elif day == self.KEY_TOMORROW:
            value = self.checkbox_value_list_tomorrow[nr].get()
            self.schedule.set_schedule_hour_off_on(today_tomorrow=True, hour=nr, cmd=value)
        else:
            logger.error("Unknown day key")
