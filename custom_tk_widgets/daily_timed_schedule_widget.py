import os
import logging
from functools import partial
import tkinter as tk
from tkinter import Label, Button, font, Text
from schedules.daily_timed_schedule import DailyTimedSchedule

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "daily_timed_schedule_widget.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


class DailyTimedScheduleCreatorWidget(tk.Frame):
    """
    Widget for DailyTimedScheduleCreator
    """
    # UI constants
    BTN_WIDTH = 30
    BTN_WIDTH_SMALL = 14
    LABEL_WIDTH = 20
    TEXT_BOX_WIDTH = 6
    TEXT_BOX_HEIGHT = 1

    def __init__(self, parent, sch: DailyTimedSchedule):
        """
        :param parent: parent view
        :param sch: DailyTimedScheduleCreator associated with the widget
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.sch = sch
        self.btn_apply_settings, self.btn_enable_schedule, self.btn_disable_schedule, self.btn_toggle_repeated, \
            self.btn_turn_off = None, None, None, None, None
        # widget labels
        self.lbl_title, self.lbl_associated_devices = None, None
        # widget labels for setting names
        self.lbl_hour_start, self.lbl_minute_start, self.lbl_on_time = None, None, None
        # widget text boxes for settings
        self.txt_hour_start, self.txt_minute_start, self.txt_on_time = None, None, None
        # Labels for holding actual setting values
        self.lbl_hour_start_act, self.lbl_minute_start_act, self.lbl_on_time_act = None, None, None
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()
        self.update_associated_devices()

    def handle_subject_event(self, event_type: str):
        # The subject has notified this of an event
        logger.debug(f"Widget notified of an event {event_type}")
        if event_type == DailyTimedSchedule.event_name_schedule_change:
            self.update_widget()
        elif event_type == DailyTimedSchedule.event_name_new_device_associated:
            self.update_associated_devices()

    def update_widget(self):
        if not self.sch:
            # If scheudle  not assigned to widget return
            return
        self.update_actual_settings()
        self.update_btn_colors()
        self.update_status()

    def update_status(self):
        text = "ON" if self.sch.command else "OFF"
        self.lbl_status.config(text=text)

    def update_actual_settings(self):
        hour_on, minute_on, on_time_min = self.sch.get_settings()
        self.lbl_hour_start_act.config(text=f" {hour_on}")
        self.lbl_minute_start_act.config(text=f" {minute_on}")
        self.lbl_on_time_act.config(text=f" {on_time_min}")

    def update_associated_devices(self):
        text = "No devices associated with schedule" if not self.sch.device_list else \
            f"Associated devices: {', '.join(dev.name for dev in self.sch.device_list)}"
        self.lbl_associated_devices.config(text=text)

    def apply_settings(self):
        start_hour = self.txt_hour_start.get("1.0", "end-1c")
        start_minute = self.txt_minute_start.get("1.0", "end-1c")
        on_time = self.txt_on_time.get("1.0", "end-1c")
        try:
            start_hour_int = int(start_hour)
            start_minute_int = int(start_minute)
            on_time_int = int(on_time)
            if self.sch:
                self.sch.set_settings(hour_on=start_hour_int, minute_on=start_minute_int, on_time_min=on_time_int)
            self.lbl_title.config(text=self.sch.name)
        except ValueError:
            self.lbl_title.config(text="INVALID INPUT")

    def turn_schedule_off_on(self, off_on: bool):
        if self.sch:
            self.sch.enable_schedule() if off_on else self.sch.disable_schedule()
        else:
            logger.error("No schedule associated with widget")

    def toggle_repeated(self):
        if self.sch:
            self.sch.repeat_daily = not self.sch.repeat_daily
            self.update_btn_colors()
        else:
            logger.error("No schedule associated with widget")

    def update_btn_colors(self):
        if self.sch:
            self.btn_toggle_repeated.config(bg="green") if self.sch.repeat_daily else \
                self.btn_toggle_repeated.config(bg="#f0f0f0")
            if self.sch.schedule_enabled:
                self.btn_enable_schedule.config(bg="green")
                self.btn_disable_schedule.config(bg="#f0f0f0")
            else:
                self.btn_enable_schedule.config(bg="#f0f0f0")
                self.btn_disable_schedule.config(bg="green")
        else:
            logger.error("No schedule associated with widget")

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_title = Label(self, text=self.sch.name, font=bold_font)
        self.lbl_associated_devices = Label(self, text="No associated devices")
        self.lbl_status = Label(self, text="Off")
        self.lbl_hour_start = Label(self, text="START HOUR", width=self.LABEL_WIDTH)
        self.lbl_minute_start = Label(self, text="START MINUTE", width=self.LABEL_WIDTH)
        self.lbl_on_time = Label(self, text="ON TIME (MIN)", width=self.LABEL_WIDTH)
        self.lbl_hour_start_act = Label(self, text="6", width=self.TEXT_BOX_WIDTH)
        self.lbl_minute_start_act = Label(self, text="45", width=self.TEXT_BOX_WIDTH)
        self.lbl_on_time_act = Label(self, text="15", width=self.TEXT_BOX_WIDTH)
        self.txt_hour_start = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_minute_start = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_on_time = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_hour_start.insert("1.0", "6")
        self.txt_minute_start.insert("1.0", "45")
        self.txt_on_time.insert("1.0", "15")
        self.frame_enable_disable = tk.Frame(self)
        self.btn_apply_settings = Button(self, text='APPLY SETTINGS', command=self.apply_settings,
                                         width=self.BTN_WIDTH)
        self.btn_enable_schedule = Button(self.frame_enable_disable, text='ENABLE', command=partial(self.turn_schedule_off_on, True),
                                          width=self.BTN_WIDTH_SMALL)
        self.btn_disable_schedule = Button(self.frame_enable_disable, text='DISABLE', command=partial(self.turn_schedule_off_on, False),
                                           width=self.BTN_WIDTH_SMALL)
        self.btn_toggle_repeated = Button(self, text='REPEATED', command=self.toggle_repeated,
                                          width=self.BTN_WIDTH)
        self.btn_turn_off = Button(self, text='TURN OFF', command=self.sch.turn_devices_off,
                                          width=self.BTN_WIDTH)

    def _place_widget_elements(self):
        self.lbl_title.grid(row=0, column=0, columnspan=3)
        self.lbl_associated_devices.grid(row=1, column=0, columnspan=3)
        self.lbl_status.grid(row=2, column=0, columnspan=3)
        self.lbl_hour_start.grid(row=3, column=0)
        self.lbl_minute_start.grid(row=4, column=0)
        self.lbl_on_time.grid(row=5, column=0)
        self.txt_hour_start.grid(row=3, column=1)
        self.txt_minute_start.grid(row=4, column=1)
        self.txt_on_time.grid(row=5, column=1)
        self.lbl_hour_start_act.grid(row=3, column=2)
        self.lbl_minute_start_act.grid(row=4, column=2)
        self.lbl_on_time_act.grid(row=5, column=2)
        self.btn_apply_settings.grid(row=6, column=0, columnspan=3)
        self.frame_enable_disable.grid(row=7, column=0, columnspan=3)
        self.btn_enable_schedule.grid(row=0, column=0)
        self.btn_disable_schedule.grid(row=0, column=1)
        self.btn_toggle_repeated.grid(row=8, column=0, columnspan=3)
        self.btn_turn_off.grid(row=9, column=0, columnspan=3)
