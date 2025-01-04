import logging
import os
from datetime import datetime, timezone
import requests
import secrets
from helpers.data_storage_interface import DataStoreInterface
from helpers.sensor import Sensor
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
file_handler = logging.FileHandler(os.path.join("../logs", "grafana.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test_fc():
    grafana_cloud = GrafanaCloud(endpoint=secrets.GRAFANA_ENDPOINT,
                                 username=secrets.GRAFANA_USERNAME,
                                 password=secrets.GRAFANA_API_TOKEN,
                                 source_tag="home_data")
    # logger.debug(grafana_cloud._get_payload_from_plc_data(plc_data, data_prefix='rigens', bar_label="label", source='source'))
    # print(grafana_cloud._get_payload_from_shelly_data("Plug_1", True, 5, 11.1, 22.2))
    test_sensor_list(grafana_cloud)
    # data_payload = "home_test,source=ib_home_tests t1=22.5,h1=50.0,co2=550.0"
    # grafana_cloud._post_to_cloud(data_payload)
    # test_periodical_log(grafana_cloud, data_payload)

def test_sensor_list(grafana_cloud):
    s1 = Sensor(name="s1", value=12, group_name="g1")
    s2 = Sensor(name="s2", value=12, group_name="g1")
    s3 = Sensor(name="s3", value=12, group_name="g2")
    s4 = Sensor(name="s4", value=12, group_name="g2")
    s5 = Sensor(name="s5", value=12, group_name="g3")
    sensor_list = (s1,s2,s3,s4,s5)
    print(grafana_cloud._get_payload_from_sensor_data(sensor_list))
    # grafana_cloud.insert_sensor_list_data(sensor_list)

class GrafanaCloud(DataStoreInterface):
    """
    Class for sending data to Grafana cloud using http requests
    """



    def __init__(self, endpoint: str, username: str, password: str, source_tag: str) -> None:
        self._url = endpoint
        self._username = username
        self._password = password
        self._source_tag = source_tag

    def insert_shelly_data(self, name: str, off_on: bool, status: int,
                           power: float = DataStoreInterface.NO_DATA_VALUE,
                           energy: float = DataStoreInterface.NO_DATA_VALUE,
                           voltage: float = DataStoreInterface.NO_DATA_VALUE,
                           current: float = DataStoreInterface.NO_DATA_VALUE):
        """
        Insert data from a shelly smart device
        :param name:
        :param off_on:
        :param status:
        :param power:
        :param energy:
        :param voltage:
        :param current:
        :return:
        """
        payload = self._get_payload_from_shelly_data(name, off_on, status, power, energy, voltage, current)
        self._post_to_cloud(payload)

    def _get_payload_from_shelly_data(self, name: str, off_on: bool, status: int,
                                      power: float = DataStoreInterface.NO_DATA_VALUE,
                                      energy: float = DataStoreInterface.NO_DATA_VALUE,
                                      voltage: float = DataStoreInterface.NO_DATA_VALUE,
                                      current: float = DataStoreInterface.NO_DATA_VALUE) -> str:
        """
        Return payload for posting to Grafana
        For shelly devices, create payload like this:
        shelly_dev_name,source=source_tag data1=1.1,data2=2.2
        """
        # Payload with data that is always present
        payload = f"{name.replace(' ', '_')},source={self._source_tag} off_on={int(off_on)},status={status}"
        # Add optional data to the payload
        payload = payload + self._get_metric_str("power", power)
        payload = payload + self._get_metric_str("energy", energy)
        payload = payload + self._get_metric_str("voltage", voltage)
        payload = payload + self._get_metric_str("current", current)
        return payload

    def _get_metric_str(self,metric_name:str,metric_value:float):
        # Return metric string for the payload if it has a value
        if metric_value == DataStoreInterface.NO_DATA_VALUE:
            # There is no value for this metric, return nothing
            return ""
        # Metrics are comma seerated
        return f",{metric_name}={metric_value:.2f}"

    def insert_sensor_list_data(self, sensor_list: list[Sensor]):
        payload = self._get_payload_from_sensor_data(sensor_list)
        self._post_to_cloud(payload)

    def _get_payload_from_sensor_data(self, sensor_list: list[Sensor]) -> str:
        """
        Return payload for posting to Grafana
        For sensor, create payload like this:
        groupname1,source=source_tag sensor1=1.1,sensor1=2.2
        groupname2,source=source_tag sensor1=1.1,sensor1=2.2
        """
        group_old = sensor_list[0].group_name
        first_in_group = True
        payload = f"{group_old.replace(' ', '_')},source={self._source_tag} "
        for s in sensor_list:
            try:
                if s.group_name != group_old:
                    group_old = s.group_name
                    # New sensor group, add in new line
                    payload = payload + f"\n{s.group_name.replace(' ', '_')},source={self._source_tag} "
                    first_in_group = True
                if first_in_group:
                    # First metric without comma
                    payload = payload + f"{s.name.replace(' ', '_')}={s.value:.2f}"
                    first_in_group = False
                else:
                    # Next metrics with comma
                    payload = payload + f",{s.name.replace(' ', '_')}={s.value:.2f}"
            except Exception as e:
                logger.error(e)
                logger.error(f"Sensor{s}, value {s.value}")
        return payload

    def insert_current_hour_price(self, current_price: float, timestamp: datetime):
        payload = self._get_payload_from_hourly_price(current_price,timestamp)
        self._post_to_cloud(payload)

    def _get_payload_from_hourly_price(self, current_price: float, timestamp: datetime) -> str:
        """
        :param current_price - for hour in timestamp:
        :param timestamp - must be UTC:
        Return payload for posting to Grafana
        For price, create payload like this:
        electricity,source=source_tag price=10.0 timestamp_ns
        """
        payload = f"electricity,source={self._source_tag} price={current_price:.2f}"
        payload = self._add_timestamp_to_payload(payload, timestamp)
        return payload

    def _add_timestamp_to_payload(self, payload:str, timestamp: datetime = None) -> str:
        if timestamp:
            payload = payload + f" {self._get_timestamp_from_dt(timestamp)}"
        return payload

    def _get_timestamp_from_dt(self, timestamp: datetime) -> str:
        self._check_difference_from_current_time(timestamp)
        timestamp_s = timestamp.timestamp()
        timestamp_ns = int(timestamp_s * 1_000_000_000)
        return f"{timestamp_ns}"

    def _check_difference_from_current_time(self, timestamp: datetime):
        """
        To warn that data muight not be logged
        :param timestamp:
        :return:
        """
        now = datetime.now(timezone.utc)
        time_dif = now - timestamp
        time_dif_min = abs(time_dif.total_seconds() / 60)
        if time_dif_min >= 10:
            logger.warning(
                f"Attempt to cloud log timestamp that is too far from current time, value might be rejected. "
                f"Dif.:{time_dif_min} min")

    def _post_to_cloud(self, payload: str):
        try:
            logger.debug(f"Posting to cloud: {payload}")
            response = requests.post(f'{self._url}',
                                     headers={'Content-Type': 'text/plain'},
                                     data=payload,
                                     auth=(f"{self._username}", f"{self._password}")
                                     )
            self._check_response(response, payload)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception when posting to Grafana {e}")

    def _check_response(self, response: requests.Response, payload: str):
        if response.ok:
            logger.debug(f"Request succeeded with status code: {response.status_code}")
        else:
            logger.error(f"Grafana request failed with status code: {response.status_code}")
            logger.error(f"Grafana response content: {response.text}")
            logger.error(f"Attempted payload: {payload}")

    def stop(self):
        """Nothing to stop since uses http requests"""
        pass

    def insert_prices(self, prices: dict, date: datetime.date):
        raise NotImplementedError("Grafana cloud does not implement this method, use insert_current_hour_price instead")

if __name__ == "__main__":
    test_fc()
