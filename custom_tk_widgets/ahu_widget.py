import tkinter as tk
from tkinter import Label, Button, font
from vallux_ahu import ValloxAhu
from observer_pattern import Observer
import webbrowser


class AhuWidget(tk.Frame, Observer):
    """
    UI widget for Ahu object
    Displays sensors data and allows new data req or opening the web view
    """
    # UI constants
    BTN_WIDTH = 30
    LABEL_WIDTH = 15

    def __init__(self, parent, ahu: ValloxAhu):
        """
        :param parent: parent view
        :param device: Device the widget is connected to
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.ahu = ahu
        # widget buttons
        self.btn_req_data, self.btn_open_web, = None, None
        # widget labels
        self.lbl_device_name = None
        self.lbl_fan_speed, self.lbl_rh, self.lbl_co2, self.lbl_t_indoor_air, \
            self.lbl_t_outdoor_air, self.lbl_t_supply_air, self.lbl_t_exhaust_air = None, None, None, None, None, \
            None, None
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()

    def _prepare_widget_elements(self):
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_device_name = Label(self, text="AHU", font=bold_font)
        self.lbl_fan_speed = Label(self, text="FAN SPEED", width=self.BTN_WIDTH)
        self.lbl_rh = Label(self, text="RH", width=self.LABEL_WIDTH)
        self.lbl_co2 = Label(self, text="CO2", width=self.LABEL_WIDTH)
        self.lbl_t_indoor_air = Label(self, text="T INDOOR", width=self.LABEL_WIDTH)
        self.lbl_t_outdoor_air = Label(self, text="T OUTDOOR", width=self.LABEL_WIDTH)
        self.lbl_t_supply_air = Label(self, text="T SUPPLY", width=self.LABEL_WIDTH)
        self.lbl_t_exhaust_air = Label(self, text="T EXHAUST", width=self.LABEL_WIDTH)
        self.btn_req_data = Button(self, text='REQ NEW DATA', command=self.ahu.req_new_data, width=self.BTN_WIDTH)
        self.btn_open_web = Button(self, text='OPEN WEB', command=self.open_web_page, width=self.BTN_WIDTH)

    def open_web_page(self):
        webbrowser.open(self.ahu.ip, new=2)

    def _place_widget_elements(self):
        self.lbl_device_name.grid(row=0, column=0, columnspan=2)
        self.lbl_fan_speed.grid(row=1, column=0, columnspan=2)
        self.lbl_rh.grid(row=2, column=0)
        self.lbl_co2.grid(row=2, column=1)
        self.lbl_t_indoor_air.grid(row=3, column=0)
        self.lbl_t_outdoor_air.grid(row=3, column=1)
        self.lbl_t_supply_air.grid(row=4, column=0)
        self.lbl_t_exhaust_air.grid(row=4, column=1)
        self.btn_req_data.grid(row=5, column=0, columnspan=2)
        self.btn_open_web.grid(row=6, column=0, columnspan=2)

    def handle_subject_event(self, event_type: str, *args, **kwargs):
        self.update_widget()

    def update_widget(self):
        self.lbl_fan_speed.config(text=f"FAN SPEED {self.ahu.fan_speed} %")
        self.lbl_rh.config(text=f"RH {self.ahu.rh} %")
        self.lbl_co2.config(text=f"CO2 {self.ahu.co2} PPM")
        self.lbl_t_indoor_air.config(text=f"T° IN {self.ahu.t_indoor_air} °C")
        self.lbl_t_outdoor_air.config(text=f"T° OUT {self.ahu.t_outdoor_air} °C")
        self.lbl_t_supply_air.config(text=f"T° SUP. {self.ahu.t_supply_air} °C")
        self.lbl_t_exhaust_air.config(text=f"T° EXH. {self.ahu.t_exhaust_air} °C")
