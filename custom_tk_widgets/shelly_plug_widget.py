from tkinter import Label
from devices.shellyPlugMqtt import ShellyPlug
from custom_tk_widgets.device_widget import DeviceWidget

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
        self.lbl_energy.config(text=f"{self.device.energy} kWh")
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