import os
import logging
import tkinter as tk
from tkinter import Label, Button, font, Text
from typing import Callable
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
file_handler = logging.FileHandler(os.path.join("../logs", "hourly_schedule_widget.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


class HourlyScheduleCreatorWidget(tk.Frame):
    """
    Widget for creating schedules according to electricity price
    """
    # UI constants
    BTN_WIDTH = 15
    LABEL_WIDTH = 15
    TEXT_BOX_WIDTH = 15
    TEXT_BOX_HEIGHT = 1

    def __init__(self, parent, fc_to_call: Callable[[float, int, int, int], None]):
        """
        :param parent: parent view
        :param fc_to_call: method to call for schedule creation. Variables are max_total_float, hours_ahead_int,
        max_h_int, min_h_int see the schedule creator class
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.callable = fc_to_call
        self.btn_get_schedule = None
        # widget labels
        self.lbl_title = None
        # widget labels for setting names
        self.lbl_max_total_cost, self.lbl_h_ahead_to_calc, self.lbl_max_h, self.lbl_min_h = None, None, None, None
        # widget text boxes for settings
        self.txt_max_total_cost, self.txt_h_ahead_to_calc, self.txt_max_h, self.txt_min_h = None, None, None, None
        self._prepare_widget_elements()
        self._place_widget_elements()

    def get_user_input_and_call_fc(self):
        max_total_str = self.txt_max_total_cost.get("1.0", "end-1c")
        hours_ahead_str = self.txt_h_ahead_to_calc.get("1.0", "end-1c")
        max_h_str = self.txt_max_h.get("1.0", "end-1c")
        min_h_str = self.txt_min_h.get("1.0", "end-1c")
        try:
            max_total_float = float(max_total_str)
            hours_ahead_int = int(hours_ahead_str)
            max_h_int = int(max_h_str)
            min_h_int = int(min_h_str)
            self.callable(max_total_float, hours_ahead_int, max_h_int, min_h_int)
            self.lbl_title.config(text="SCHEDULE CREATOR")
        except ValueError:
            self.lbl_title.config(text="INVALID INPUT")

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_title = Label(self, text="SCHEDULE CREATOR", font=bold_font)
        self.lbl_max_total_cost = Label(self, text="MAX TOTAL COST", width=self.LABEL_WIDTH)
        self.lbl_h_ahead_to_calc = Label(self, text="HOURS AHEAD", width=self.LABEL_WIDTH)
        self.lbl_max_h = Label(self, text="MAX H ON", width=self.LABEL_WIDTH)
        self.lbl_min_h = Label(self, text="MIN H ON", width=self.LABEL_WIDTH)
        self.txt_max_total_cost = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_h_ahead_to_calc = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_max_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_min_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_max_total_cost.insert("1.0", "40.0")
        self.txt_h_ahead_to_calc.insert("1.0", "12")
        self.txt_max_h.insert("1.0", "10")
        self.txt_min_h.insert("1.0", "6")
        self.btn_get_schedule = Button(self, text='CREATE', command=self.get_user_input_and_call_fc,
                                       width=self.BTN_WIDTH)

    def _place_widget_elements(self):
        self.lbl_title.grid(row=0, column=0, columnspan=2)
        self.lbl_max_total_cost.grid(row=1, column=0)
        self.lbl_h_ahead_to_calc.grid(row=2, column=0)
        self.lbl_max_h.grid(row=3, column=0)
        self.lbl_min_h.grid(row=4, column=0)
        self.txt_max_total_cost.grid(row=1, column=1)
        self.txt_h_ahead_to_calc.grid(row=2, column=1)
        self.txt_max_h.grid(row=3, column=1)
        self.txt_min_h.grid(row=4, column=1)
        self.btn_get_schedule.grid(row=5, column=0, columnspan=2)
