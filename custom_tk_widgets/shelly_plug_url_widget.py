from tkinter import Label
from devices.shellyPlugUrlControlled import URLControlledShellyPlug
from custom_tk_widgets.device_widget import DeviceWidget


class ShellyPlugUrlWidget(DeviceWidget):
    def __init__(self, parent, device: URLControlledShellyPlug):
        """
        Same as device widget but shows some extra data received from the URL
        """
        # Labels for extra data of the shelly smart plug device
        self.lbl_state_actual = None
        super().__init__(parent, device=device)

    def update_widget(self):
        super().update_widget()
        self.update_extra_data()

    def update_extra_data(self):
        new_text = "OFFLINE"
        if self.device.state_online:
            new_text = "Socket ON" if self.device.state_off_on else "Socket OFF"
        self.lbl_state_actual.config(text=new_text)

    def _prepare_widget_elements(self):
        super()._prepare_widget_elements()
        self.lbl_state_actual = Label(self, text="STATE ACTUAL")

    def _place_widget_elements(self):
        super()._place_widget_elements()
        self.lbl_state_actual.grid(row=4, column=0, columnspan=2)
