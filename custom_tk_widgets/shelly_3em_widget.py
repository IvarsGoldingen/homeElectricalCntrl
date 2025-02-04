import tkinter as tk
from tkinter import Label, Button, font
from devices.shelly3emEnergyMeterMqtt import ShellyEnergyMeter3em
from helpers.observer_pattern import Observer


class ShellyEmWidget(tk.Frame, Observer):
    """
    UI widget for Shelly Energy meter object
    Displays electricity data for each phase
    """
    # UI constants
    BTN_WIDTH = 30
    LABEL_WIDTH = 10

    def __init__(self, parent, device: ShellyEnergyMeter3em):
        """
        :param parent: parent view
        :param device: energy meter object the widget is assigned to
        """
        super().__init__(parent, borderwidth=2, relief="solid")
        self.em = device
        # widget buttons
        self.btn_open_web = None
        # widget labels
        self.lbl_device_name = None
        self.lbl_online_status = None
        # Prepare labels for holding meter data
        (self.lbl_ph1_heading, self.lbl_ph1_v, self.lbl_ph1_a, self.lbl_ph1_freq, self.lbl_ph1_pwr, self.lbl_ph1_pf,
         self.lbl_ph1_energy) = (None, None, None, None, None, None, None)
        (self.lbl_ph2_heading, self.lbl_ph2_v, self.lbl_ph2_a, self.lbl_ph2_freq, self.lbl_ph2_pwr, self.lbl_ph2_pf,
         self.lbl_ph2_energy) = (None, None, None, None, None, None, None)
        (self.lbl_ph3_heading, self.lbl_ph3_v, self.lbl_ph3_a, self.lbl_ph3_freq, self.lbl_ph3_pwr, self.lbl_ph3_pf,
         self.lbl_ph3_energy) = (None, None, None, None, None, None, None)
        self._prepare_widget_elements()
        self._place_widget_elements()
        self.update_widget()

    def _prepare_widget_elements(self) -> None:
        # Create a custom font with bold style
        bold_font = font.Font(family="Helvetica", size=12, weight="bold")
        self.lbl_device_name = Label(self, text=self.em.name, font=bold_font)
        # Prepare phase 1 labels
        self.lbl_ph1_heading = Label(self, text="PH1", width=self.LABEL_WIDTH)
        self.lbl_ph1_v = Label(self, text="V", width=self.LABEL_WIDTH)
        self.lbl_ph1_a = Label(self, text="A", width=self.LABEL_WIDTH)
        self.lbl_ph1_freq = Label(self, text="FREQ", width=self.LABEL_WIDTH)
        self.lbl_ph1_pwr = Label(self, text="PWR", width=self.LABEL_WIDTH)
        self.lbl_ph1_pf = Label(self, text="PF", width=self.LABEL_WIDTH)
        self.lbl_ph1_energy = Label(self, text="NRGY", width=self.LABEL_WIDTH)
        # Prepare phase 2 labels
        self.lbl_ph2_heading = Label(self, text="PH2", width=self.LABEL_WIDTH)
        self.lbl_ph2_v = Label(self, text="V", width=self.LABEL_WIDTH)
        self.lbl_ph2_a = Label(self, text="A", width=self.LABEL_WIDTH)
        self.lbl_ph2_freq = Label(self, text="FREQ", width=self.LABEL_WIDTH)
        self.lbl_ph2_pwr = Label(self, text="PWR", width=self.LABEL_WIDTH)
        self.lbl_ph2_pf = Label(self, text="PF", width=self.LABEL_WIDTH)
        self.lbl_ph2_energy = Label(self, text="NRGY", width=self.LABEL_WIDTH)
        # Prepare phase 3 labels
        self.lbl_ph3_heading = Label(self, text="PH3", width=self.LABEL_WIDTH)
        self.lbl_ph3_v = Label(self, text="V", width=self.LABEL_WIDTH)
        self.lbl_ph3_a = Label(self, text="A", width=self.LABEL_WIDTH)
        self.lbl_ph3_freq = Label(self, text="FREQ", width=self.LABEL_WIDTH)
        self.lbl_ph3_pwr = Label(self, text="PWR", width=self.LABEL_WIDTH)
        self.lbl_ph3_pf = Label(self, text="PF", width=self.LABEL_WIDTH)
        self.lbl_ph3_energy = Label(self, text="NRGY", width=self.LABEL_WIDTH)
        self.lbl_online_status = Label(self, text="OFFLINE")

    def _place_widget_elements(self) -> None:
        self.lbl_device_name.grid(row=0, column=0, columnspan=3)
        # Place phase 1 labels
        self.lbl_ph1_heading.grid(row=1, column=0)
        self.lbl_ph1_v.grid(row=2, column=0)
        self.lbl_ph1_a.grid(row=3, column=0)
        self.lbl_ph1_freq.grid(row=4, column=0)
        self.lbl_ph1_pwr.grid(row=5, column=0)
        self.lbl_ph1_pf.grid(row=6, column=0)
        self.lbl_ph1_energy.grid(row=7, column=0)
        # Place phase 2 labels
        self.lbl_ph2_heading.grid(row=1, column=1)
        self.lbl_ph2_v.grid(row=2, column=1)
        self.lbl_ph2_a.grid(row=3, column=1)
        self.lbl_ph2_freq.grid(row=4, column=1)
        self.lbl_ph2_pwr.grid(row=5, column=1)
        self.lbl_ph2_pf.grid(row=6, column=1)
        self.lbl_ph2_energy.grid(row=7, column=1)
        # Place phase 3 labels
        self.lbl_ph3_heading.grid(row=1, column=2)
        self.lbl_ph3_v.grid(row=2, column=2)
        self.lbl_ph3_a.grid(row=3, column=2)
        self.lbl_ph3_freq.grid(row=4, column=2)
        self.lbl_ph3_pwr.grid(row=5, column=2)
        self.lbl_ph3_pf.grid(row=6, column=2)
        self.lbl_ph3_energy.grid(row=7, column=2)
        self.lbl_online_status.grid(row=8, column=0, columnspan=3)

    def handle_subject_event(self, event_type: str, *args, **kwargs) -> None:
        # On any event update widget
        self.update_widget()

    def update_widget(self) -> None:
        # Get data from associated object
        # Update phase 1 data
        self.lbl_ph1_v.config(text=f"{self.em.sensor_data.voltage[1].value} V")
        self.lbl_ph1_a.config(text=f"{self.em.sensor_data.current[1].value} A")
        self.lbl_ph1_freq.config(text=f"{self.em.sensor_data.freq[1].value} Hz")
        self.lbl_ph1_pwr.config(text=f"{self.em.sensor_data.power[1].value} W")
        self.lbl_ph1_pf.config(text=f"{self.em.sensor_data.pf[1].value} CosFi")
        self.lbl_ph1_energy.config(text=f"{self.em.sensor_data.energy[1].value:.2f} kWh")
        # Update phase 2 data
        self.lbl_ph2_v.config(text=f"{self.em.sensor_data.voltage[2].value} V")
        self.lbl_ph2_a.config(text=f"{self.em.sensor_data.current[2].value} A")
        self.lbl_ph2_freq.config(text=f"{self.em.sensor_data.freq[2].value} Hz")
        self.lbl_ph2_pwr.config(text=f"{self.em.sensor_data.power[2].value} W")
        self.lbl_ph2_pf.config(text=f"{self.em.sensor_data.pf[2].value} CosFi")
        self.lbl_ph2_energy.config(text=f"{self.em.sensor_data.energy[2].value:.2f} kWh")
        # Update phase 3 data
        self.lbl_ph3_v.config(text=f"{self.em.sensor_data.voltage[3].value} V")
        self.lbl_ph3_a.config(text=f"{self.em.sensor_data.current[3].value} A")
        self.lbl_ph3_freq.config(text=f"{self.em.sensor_data.freq[3].value} Hz")
        self.lbl_ph3_pwr.config(text=f"{self.em.sensor_data.power[3].value} W")
        self.lbl_ph3_pf.config(text=f"{self.em.sensor_data.pf[3].value} CosFi")
        self.lbl_ph3_energy.config(text=f"{self.em.sensor_data.energy[3].value:.2f} kWh")
        new_text = "ONLINE" if self.em.state_online else "OFFLINE"
        self.lbl_online_status.config(text=new_text)
