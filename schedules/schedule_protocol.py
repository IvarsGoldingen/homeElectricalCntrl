from typing import Protocol
from devices.device import Device

class ScheduleWithDevice(Protocol):
    def add_device(self, device: Device) -> None:
        ...