from functools import partial
import os
import tkinter as tk
from tkinter import Label, Button, font
from devices.device import Device
from helpers.observer_pattern import Observer
import logging
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
file_handler = logging.FileHandler(os.path.join("../logs", "device_widget.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)

class DeviceWidget(tk.Frame, Observer):
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

    def handle_subject_event(self, event_type: str, *args, **kwargs):
        logger.debug(f"Device widget received event: {event_type}")
        self.update_widget()

    def update_widget(self):
        logger.debug(f"Updating widget {self.device.name}")
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
