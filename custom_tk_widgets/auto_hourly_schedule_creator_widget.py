from functools import partial
import tkinter as tk
from tkinter import Label, Button, font, Text
from schedules.auto_schedule_creator import AutoScheduleCreator


class AutoHourlyScheduleCreatorWidget(tk.Frame):
    """
    """
    # UI constants
    BTN_WIDTH = 30
    LABEL_WIDTH = 20
    TEXT_BOX_WIDTH = 6
    TEXT_BOX_HEIGHT = 1

    def __init__(self, parent, auto_schedule_creator: AutoScheduleCreator):
        """
        :param parent: parent view
        :param fc_to_call: method to call with the results
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.auto_schedule_creator = auto_schedule_creator
        self.btn_create_now, self.btn_apply_settings, self.btn_enable_auto, self.btn_disable_auto = None, None, \
            None, None
        # widget labels
        self.lbl_title, self.lbl_associated_schedule = None, None
        # widget labels for setting names
        self.lbl_max_total_cost, self.lbl_h_ahead_to_calc, self.lbl_max_h, self.lbl_min_h = None, None, None, None
        # widget text boxes for settings
        self.txt_max_total_cost, self.txt_h_ahead_to_calc, self.txt_max_h, self.txt_min_h = None, None, None, None
        # Labels for holding actual setting values
        self.lbl_max_total_cost_act, self.lbl_h_ahead_to_calc_act, self.lbl_max_h_act, self.lbl_min_h_act = None, \
            None, None, None
        self._prepare_widget_elements()
        self._place_widget_elements()

    def update_widget(self):
        if not self.auto_schedule_creator:
            return
        self.update_actual_settings()
        self.update_btn_colors()
        self.update_associated_device()

    def update_actual_settings(self):
        auto_create_period, max_total_cost, max_hours_to_run, min_hours_to_run = self.auto_schedule_creator\
            .get_parameters()
        self.lbl_max_total_cost_act.config(text=f" {max_total_cost}")
        self.lbl_h_ahead_to_calc_act.config(text=f" {auto_create_period}")
        self.lbl_max_h_act.config(text=f" {max_hours_to_run}")
        self.lbl_min_h_act.config(text=f" {min_hours_to_run}")

    def update_associated_device(self):
        name = self.auto_schedule_creator.get_schedule_name()
        self.lbl_associated_schedule.config(text=f"{name}")

    def update_btn_colors(self):
        off_on = self.auto_schedule_creator.get_auto_create_enabled()
        if off_on:
            self.btn_enable_auto.config(bg="green")
            self.btn_disable_auto.config(bg="#f0f0f0")
        else:
            self.btn_enable_auto.config(bg="#f0f0f0")
            self.btn_disable_auto.config(bg="green")

    def set_parameters_from_user_input(self):
        max_total_str = self.txt_max_total_cost.get("1.0", "end-1c")
        hours_ahead_str = self.txt_h_ahead_to_calc.get("1.0", "end-1c")
        max_h_str = self.txt_max_h.get("1.0", "end-1c")
        min_h_str = self.txt_min_h.get("1.0", "end-1c")
        try:
            max_total_float = float(max_total_str)
            hours_ahead_int = int(hours_ahead_str)
            max_h_int = int(max_h_str)
            min_h_int = int(min_h_str)
            self.auto_schedule_creator.set_parameters(max_total_cost=max_total_float,
                                                      auto_create_period=hours_ahead_int,
                                                      max_hours_to_run=max_h_int,
                                                      min_hours_to_run=min_h_int)
            self.lbl_title.config(text="SCHEDULE CREATOR")
        except ValueError:
            self.lbl_title.config(text="INVALID INPUT")

    def generate_schedule_now(self):
        self.auto_schedule_creator.execute_schedule_generation()

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_title = Label(self, text="SCHEDULE CREATOR", font=bold_font)
        self.lbl_associated_schedule = Label(self, text="No schedules associated with creator")
        self.lbl_max_total_cost = Label(self, text="MAX TOTAL COST", width=self.LABEL_WIDTH)
        self.lbl_h_ahead_to_calc = Label(self, text="AUTO CREATE INTERVAL", width=self.LABEL_WIDTH)
        self.lbl_max_h = Label(self, text="MAX H ON", width=self.LABEL_WIDTH)
        self.lbl_min_h = Label(self, text="MIN H ON", width=self.LABEL_WIDTH)
        self.txt_max_total_cost = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_h_ahead_to_calc = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_max_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.txt_min_h = Text(self, width=self.TEXT_BOX_WIDTH, height=self.TEXT_BOX_HEIGHT)
        self.lbl_max_total_cost_act = Label(self, text="0.00", width=self.TEXT_BOX_WIDTH)
        self.lbl_h_ahead_to_calc_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_max_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.lbl_min_h_act = Label(self, text="0", width=self.TEXT_BOX_WIDTH)
        self.txt_max_total_cost.insert("1.0", "40.0")
        self.txt_h_ahead_to_calc.insert("1.0", "12")
        self.txt_max_h.insert("1.0", "10")
        self.txt_min_h.insert("1.0", "6")
        self.btn_create_now = Button(self, text='CREATE NOW', command=self.generate_schedule_now,
                                     width=self.BTN_WIDTH)
        self.btn_apply_settings = Button(self, text='APPLY SETTINGS', command=self.set_parameters_from_user_input,
                                         width=self.BTN_WIDTH)
        self.btn_enable_auto = Button(self, text='ENABLE AUTO CREATE',
                                      command=partial(self.auto_schedule_creator.set_auto_create_enabled, off_on=True),
                                      width=self.BTN_WIDTH)
        self.btn_disable_auto = Button(self, text='DISABLE AUTO CREATE',
                                       command=partial(self.auto_schedule_creator.set_auto_create_enabled,
                                                       off_on=False),
                                       width=self.BTN_WIDTH)

    def _place_widget_elements(self):
        self.lbl_title.grid(row=0, column=0, columnspan=3)
        self.lbl_associated_schedule.grid(row=1, column=0, columnspan=3)
        self.lbl_max_total_cost.grid(row=2, column=0)
        self.lbl_h_ahead_to_calc.grid(row=3, column=0)
        self.lbl_max_h.grid(row=4, column=0)
        self.lbl_min_h.grid(row=5, column=0)
        self.txt_max_total_cost.grid(row=2, column=1)
        self.txt_h_ahead_to_calc.grid(row=3, column=1)
        self.txt_max_h.grid(row=4, column=1)
        self.txt_min_h.grid(row=5, column=1)
        self.lbl_max_total_cost_act.grid(row=2, column=2)
        self.lbl_h_ahead_to_calc_act.grid(row=3, column=2)
        self.lbl_max_h_act.grid(row=4, column=2)
        self.lbl_min_h_act.grid(row=5, column=2)
        self.btn_create_now.grid(row=6, column=0, columnspan=3)
        self.btn_apply_settings.grid(row=7, column=0, columnspan=3)
        self.btn_enable_auto.grid(row=8, column=0, columnspan=3)
        self.btn_disable_auto.grid(row=9, column=0, columnspan=3)
