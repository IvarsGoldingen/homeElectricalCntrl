from tkinter import Label
from devices.shellyPlusPM import ShellyPlusPM
from custom_tk_widgets.device_widget import DeviceWidget


class ShellyPlusPmWidget(DeviceWidget):
    def __init__(self, parent, device: ShellyPlusPM):
        """
        Same as device widget but shows some extra data received from MQTT
        """
        # Labels for extra data of the shelly smart plug device
        self.lbl_input_state, self.lbl_temp, self.lbl_state_actual = None, None, None
        super().__init__(parent, device=device)

    def update_widget(self):
        super().update_widget()
        self.update_extra_data()

    def update_extra_data(self):
        self.lbl_temp.config(text=f"{self.device.temperature} °C")
        input_state_str = "ON" if self.device.di_off_on else "OFF"
        self.lbl_input_state.config(text=f"Input {input_state_str}")
        self.lbl_voltage_current.config(text=f"{self.device.voltage:.1f} V\t{self.device.current:.2f} A")
        self.lbl_power_energy.config(text=f"{self.device.power_w:.1f} W\t{self.device.energy_kWh:.3f} kWh")
        new_text = "OFFLINE"
        if self.device.state_online:
            new_text = "Socket ON" if self.device.state_off_on else "Socket OFF"
        self.lbl_state_actual.config(text=new_text)

    def _prepare_widget_elements(self):
        super()._prepare_widget_elements()
        self.lbl_temp = Label(self, text="TEMPERATURE")
        self.lbl_voltage_current = Label(self, text="V and I")
        self.lbl_power_energy = Label(self, text="Power and energy")
        self.lbl_input_state = Label(self, text="INPUT STATE")
        self.lbl_state_actual = Label(self, text="STATE ACTUAL")

    def _place_widget_elements(self):
        super()._place_widget_elements()
        self.lbl_temp.grid(row=4, column=0, columnspan=2)
        self.lbl_voltage_current.grid(row=5, column=0, columnspan=2)
        self.lbl_power_energy.grid(row=6, column=0, columnspan=2)
        self.lbl_input_state.grid(row=7, column=0, columnspan=2)
        self.lbl_state_actual.grid(row=8, column=0, columnspan=2)