from functools import partial
import tkinter as tk
from tkinter import Label, Button, font, Text
from schedules.auto_schedule_creator import AutoScheduleCreator
import logging
import os
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
file_handler = logging.FileHandler(os.path.join("../logs", "auto_creator.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


class AutoHourlyScheduleCreatorWidget(tk.Frame):
    """
    Widget for AutoHourlyScheduleCreator
    """
    # UI constants
    BTN_WIDTH = 30
    LABEL_WIDTH = 20
    TEXT_BOX_WIDTH = 6
    TEXT_BOX_HEIGHT = 1

    def __init__(self, parent, auto_schedule_creator: AutoScheduleCreator, display_price_per_kwh: bool = True):
        """
        :param parent: parent view
        :param fc_to_call: method to call with the results
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        # Default price comes as price per MWh
        self.display_price_per_kwh = display_price_per_kwh
        self.auto_schedule_creator = auto_schedule_creator
        self.btn_create_now, self.btn_apply_settings, self.btn_toggle_enabled = None, None, None
        # widget labels
        self.lbl_title, self.lbl_associated_schedule = None, None
        # widget labels for setting names
        self.lbl_max_total_cost, self.lbl_h_period_split, self.lbl_max_h, self.lbl_min_h, self.lbl_calc_h, \
            self.lbl_calc_min = None, None, None, None, None, None
        # widget text boxes for settings
        self.txt_max_total_cost, self.txt_h_period_split, self.txt_max_h, self.txt_min_h, \
            self.txt_calc_h, self.txt_calc_min = None, None, None, None, None, None
        # Labels for holding actual setting values
        self.lbl_max_total_cost_act, self.lbl_h_period_split_act, self.lbl_max_h_act, self.lbl_min_h_act, \
            self.lbl_calc_h_act, self.lbl_calc_min_act = None, None, None, None, None, None
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()

    def update_widget(self):
        if not self.auto_schedule_creator:
            # If creator not assigned to widget return
            return
        self.update_actual_settings()
        self.update_btn_colors()
        self.update_associated_schedule()

    def update_actual_settings(self):
        period_split_h, max_total_cost, max_hours_to_run, min_hours_to_run, calculation_time_h, \
            calculation_time_min = self.auto_schedule_creator.get_parameters()
        max_total_cost = max_total_cost / 1000 if self.display_price_per_kwh else max_total_cost
        max_total_cost = round(max_total_cost, 2) if self.display_price_per_kwh else round(max_total_cost, 1)
        self.lbl_max_total_cost_act.config(text=f" {max_total_cost}")
        self.lbl_h_period_split_act.config(text=f" {period_split_h}")
        self.lbl_max_h_act.config(text=f" {max_hours_to_run}")
        self.lbl_min_h_act.config(text=f" {min_hours_to_run}")
        self.lbl_calc_h_act.config(text=f" {calculation_time_h}")
        self.lbl_calc_min_act.config(text=f" {calculation_time_min}")

    def update_associated_schedule(self):
        name = self.auto_schedule_creator.get_schedule_name()
        self.lbl_associated_schedule.config(text=f"Associated schedule: {name}")

    def update_btn_colors(self):
        off_on = self.auto_schedule_creator.get_auto_create_enabled()
        if off_on:
            self.btn_toggle_enabled.config(bg="green")
        else:
            self.btn_toggle_enabled.config(bg="#f0f0f0")

    def set_parameters_from_user_input(self):
        max_total_str = self.txt_max_total_cost.get("1.0", "end-1c")
        period_split_str = self.txt_h_period_split.get("1.0", "end-1c")
        max_h_str = self.txt_max_h.get("1.0", "end-1c")
        min_h_str = self.txt_min_h.get("1.0", "end-1c")
        calc_h_str = self.txt_calc_h.get("1.0", "end-1c")
        calc_min_str = self.txt_calc_min.get("1.0", "end-1c")
        try:
            max_total_float = float(max_total_str)
            # Program uses prices per MWh, if UI set to per kWh, convert
            max_total_float = max_total_float*1000 if self.display_price_per_kwh else max_total_float
            period_split_int = int(period_split_str)
            max_h_int = int(max_h_str)
            min_h_int = int(min_h_str)
            calc_h_int = int(calc_h_str)
            calc_min_int = int(calc_min_str)
            self.auto_schedule_creator.set_parameters(period_split=period_split_int,
                                                      max_total_cost=max_total_float,
                                                      max_periods_to_run=max_h_int,
                                                      min_periods_to_run=min_h_int,
                                                      calculation_time_h=calc_h_int,
                                                      calculation_time_min=calc_min_int)
            self.lbl_title.config(text="SCHEDULE CREATOR")
            self.update_widget()
        except ValueError:
            logger.error("Invalid parameters")
            logger.error(f"max_total_str {max_total_str}, period_split_int {period_split_str}, max_h_str {max_h_str},"
                         f" min_h_str {min_h_str}, calc_h_int {calc_h_str}, calc_min_int {calc_min_str}")
            self.lbl_title.config(text="INVALID INPUT")

    def generate_schedule_now(self):
        self.auto_schedule_creator.execute_schedule_generation()

    def toggle_auto_create(self):
        # Enable or disable auto creation of schedules
        if self.auto_schedule_creator:
            # Only if a schedule creator assigned to this
            self.auto_schedule_creator.set_auto_create_enabled(not self.auto_schedule_creator.get_auto_create_enabled())
            self.update_btn_colors()

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_title = Label(self, text="SCHEDULE CREATOR", font=bold_font)
        self.lbl_associated_schedule = Label(self, text="No schedules associated with creator")
        self.lbl_max_total_cost = Label(self, text="MAX TOTAL COST", width=self.LABEL_WIDTH)
        self.lbl_h_period_split = Label(self, text="SPLIT INTERVAL", width=self.LABEL_WIDTH)
        self.lbl_max_h = Label(self, text="MAX H ON", width=self.LABEL_WIDTH)
        self.lbl_min_h = Label(self, text="MIN H ON", width=self.LABEL_WIDTH)
        self.lbl_calc_h = Label(self, text="CALCULATION HOUR", width=self.LABEL_WIDTH)
        self.lbl_calc_min = Label(self, text="CALCULATION MINUTE", width=self.LABEL_WIDTH)
        self.txt_max_total_cost = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_h_period_split = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_max_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_min_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_calc_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_calc_min = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.lbl_max_total_cost_act = Label(self, text="0.00", width=self.TEXT_BOX_WIDTH)
        self.lbl_h_period_split_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_max_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_min_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_max_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_min_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_calc_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_calc_min_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.txt_max_total_cost.insert("1.0", "300.0")
        self.txt_h_period_split.insert("1.0", "6")
        self.txt_max_h.insert("1.0", "5")
        self.txt_min_h.insert("1.0", "2")
        self.txt_calc_h.insert("1.0", "16")
        self.txt_calc_min.insert("1.0", "50")
        self.btn_create_now = Button(self, text='CREATE NOW', command=self.generate_schedule_now,
                                     width=self.BTN_WIDTH)
        self.btn_apply_settings = Button(self, text='APPLY SETTINGS', command=self.set_parameters_from_user_input,
                                         width=self.BTN_WIDTH)
        self.btn_toggle_enabled = Button(self, text='TOGGLE AUTO CREATE',
                                         command=partial(self.toggle_auto_create),
                                         width=self.BTN_WIDTH)

    def _place_widget_elements(self):
        self.lbl_title.grid(row=0, column=0, columnspan=3)
        self.lbl_associated_schedule.grid(row=1, column=0, columnspan=3)
        self.lbl_max_total_cost.grid(row=2, column=0)
        self.lbl_h_period_split.grid(row=3, column=0)
        self.lbl_max_h.grid(row=4, column=0)
        self.lbl_min_h.grid(row=5, column=0)
        self.lbl_calc_h.grid(row=6, column=0)
        self.lbl_calc_min.grid(row=7, column=0)
        self.txt_max_total_cost.grid(row=2, column=1)
        self.txt_h_period_split.grid(row=3, column=1)
        self.txt_max_h.grid(row=4, column=1)
        self.txt_min_h.grid(row=5, column=1)
        self.txt_calc_h.grid(row=6, column=1)
        self.txt_calc_min.grid(row=7, column=1)
        self.lbl_max_total_cost_act.grid(row=2, column=2)
        self.lbl_h_period_split_act.grid(row=3, column=2)
        self.lbl_max_h_act.grid(row=4, column=2)
        self.lbl_min_h_act.grid(row=5, column=2)
        self.lbl_calc_h_act.grid(row=6, column=2)
        self.lbl_calc_min_act.grid(row=7, column=2)
        self.btn_create_now.grid(row=8, column=0, columnspan=3)
        self.btn_apply_settings.grid(row=9, column=0, columnspan=3)
        self.btn_toggle_enabled.grid(row=10, column=0, columnspan=3)
