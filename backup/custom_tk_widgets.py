"""
Come classes that extend Tkinter View to display custom objects of a home automation devices
"""
import os
import logging
from functools import partial
import tkinter as tk
from tkinter import Label, Button, font, Frame, Checkbutton, BooleanVar
from devices.shellyPlugMqtt import ShellyPlug
from devices.device import Device
from schedules.hourly_schedule import HourlySchedule2days

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "tk_custom_widgets.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


class Schedule2DaysWidget(tk.Frame):
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
        #UI objects containing the checkboxes
        self.frame_list_today, self.lbl_check_box_list_today, self.checkbox_value_list_today, \
            self.checkbox_list_today = [], [], [], []
        self.frame_list_tomorrow, self.lbl_check_box_list_tomorrow, self.checkbox_value_list_tomorrow, \
            self.checkbox_list_tomorrow = [], [], [], []
        self.frame_today, self.frame_tomorrow = Frame(self), Frame(self)
        self._prepare_widget_elements()
        self._place_widget_elements()
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
        logger.debug(f"Adding prices {len(text_list_today)}    {len(text_list_tomorrow)}")
        if len(text_list_today) != 24 or len(text_list_tomorrow) != 24:
            # expected new text for each hour
            return
        logger.debug("Adding prices 2")
        for hour, (lbl, extra_text) in enumerate(zip(self.lbl_check_box_list_today, text_list_today)):
            lbl.config(text=f"{hour:02}:00\r{extra_text}")
        for hour, (lbl, extra_text) in enumerate(zip(self.lbl_check_box_list_tomorrow, text_list_tomorrow)):
            lbl.config(text=f"{hour:02}:00\r{extra_text}")

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


class DeviceWidget(tk.Frame):
    """
    UI widget for Device object
    Displays its status and allows manual control
    """
    # UI constants
    BTN_WIDTH = 15

    def __init__(self, parent, device: Device):
        """
        :param parent: parent view
        :param device: Device the widget is connected to
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.device = device
        # widget buttons
        self.btn_auto, self.btn_man, self.btn_man_on, self.btn_man_off = None, None, None, None
        # widget labels
        self.lbl_device_name, self.lbl_status = None, None
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_status = Label(self, text="DEVICE STATUS")
        self.lbl_device_name = Label(self, text=self.device.name, font=bold_font)
        self.btn_auto = Button(self, text='AUTO', command=partial(self.device.set_mode, auto_man=Device.MODE_AUTO),
                               width=self.BTN_WIDTH)
        self.btn_man = Button(self, text='MAN', command=partial(self.device.set_mode, auto_man=Device.MODE_MAN),
                              width=self.BTN_WIDTH)
        self.btn_man_on = Button(self, text='ON', command=partial(self.device.set_manual_run, off_on=True),
                                 width=self.BTN_WIDTH)
        self.btn_man_off = Button(self, text='OFF', command=partial(self.device.set_manual_run, off_on=False),
                                  width=self.BTN_WIDTH)

    def _place_widget_elements(self):
        self.lbl_device_name.grid(row=0, column=0, columnspan=2)
        self.lbl_status.grid(row=1, column=0, columnspan=2)
        self.btn_auto.grid(row=2, column=0)
        self.btn_man.grid(row=2, column=1)
        self.btn_man_on.grid(row=3, column=0)
        self.btn_man_off.grid(row=3, column=1)

    def update_widget(self):
        self.update_status_label()
        self.update_btn_colors()

    def update_status_label(self):
        # Update status message of device
        new_text = self.device.status_strings.get(self.device.get_status(), "UNKNOWN")
        self.lbl_status.config(text=new_text)

    def update_btn_colors(self):
        # Highlight the button green that corresponds to the current device command
        if not self.device.auto_man:
            self.btn_auto.config(bg="green")
            self.btn_man.config(bg="gray")
        else:
            self.btn_auto.config(bg="gray")
            self.btn_man.config(bg="yellow")
        # Highlight the button green that corresponds to the current device command
        if self.device.get_cmd_given():
            self.btn_man_on.config(bg="green")
            self.btn_man_off.config(bg="gray")
        else:
            self.btn_man_on.config(bg="gray")
            self.btn_man_off.config(bg="green")


class ShellyPlugWidget(DeviceWidget):
    def __init__(self, parent, device: ShellyPlug):
        """
        Same as device widget but shows some extra data received from MQTT
        """
        # Labels for extra data of the shelly smart plug device
        self.lbl_power, self.lbl_energy, self.lbl_shelly_info, self.lbl_state_actual = None, None, None, None
        super().__init__(parent, device=device)

    def update_widget(self):
        super().update_widget()
        self.update_extra_data()

    def update_extra_data(self):
        self.lbl_temp.config(text=f"{self.device.temperature} °C")
        self.lbl_pwr.config(text=f"{self.device.power} W")
        self.lbl_energy.config(text=f"{self.device.energy} Wh")
        new_text = "OFFLINE"
        if self.device.state_online:
            new_text = "Socket ON" if self.device.state_off_on else "Socket OFF"
        self.lbl_state_actual.config(text=new_text)

    def _prepare_widget_elements(self):
        super()._prepare_widget_elements()
        self.lbl_temp = Label(self, text="TEMPERATURE")
        self.lbl_pwr = Label(self, text="POWER")
        self.lbl_energy = Label(self, text="ENERGY")
        self.lbl_state_actual = Label(self, text="STATE ACTUAL")

    def _place_widget_elements(self):
        super()._place_widget_elements()
        self.lbl_temp.grid(row=4, column=0, columnspan=2)
        self.lbl_pwr.grid(row=5, column=0, columnspan=2)
        self.lbl_energy.grid(row=6, column=0, columnspan=2)
        self.lbl_state_actual.grid(row=7, column=0, columnspan=2)
