import paho.mqtt.client as mqtt
import logging
import os
from typing import Callable
from observer_pattern import Subject
import secrets

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("logs", "mqtt_client.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def test():
    client = MyMqttClient(secrets.MQTT_SERVER, secrets.MQTT_PORT, user=secrets.MQTT_USER, psw=secrets.MQTT_PSW)
    client.start()
    client.subscribe("shellies/shellyplug-s-80646F840029/#")
    device_bool = False
    while True:
        usr_in = input("input")
        if not device_bool:
            print("turning on")
            client.publish("shellies/shellyplug-s-80646F840029/relay/0/command", "on")
        else:
            print("turning off")
            client.publish("shellies/shellyplug-s-80646F840029/relay/0/command", "off")
        device_bool = not device_bool


class MyMqttClient(mqtt.Client, Subject):
    """
    Class that inherits from paho mqtt.Client
    Used to monitor certain topics on the mqtt broker and publish as well if needed
    """
    event_name_status_change = "mqtt_status_changed"


    # Connection status constants
    STATUS_DISCONNECTED = 0
    STATUS_CONNECTED = 1

    status_strings = {
        STATUS_DISCONNECTED: "MQTT NOT CONNECTED",
        STATUS_CONNECTED: "MQTT CONNECTED"
    }

    def __init__(self, broker_addr: str, port: int, user: str, psw: str):
        mqtt.Client.__init__(self)
        Subject.__init__(self)
        self.reconnect_delay_set(min_delay=10, max_delay=60) # in seconds
        self.status = self.STATUS_DISCONNECTED
        self.broker_addr = broker_addr
        self.port = port
        self.username_pw_set(user, psw)
        # A dictionary holding topics to listen to and corresponging callbacks when a message has been published to that
        # topic
        self.subscription_dict = {}

    def start(self):
        logger.info(f"Connecting to MQTT broker. {self.broker_addr}:{self.port}")
        # self.connect(host=self.broker_addr, port=self.port, keepalive=60, bind_address="")
        self.connect_async(host=self.broker_addr, port=self.port, keepalive=60, bind_address="")
        # start mqtt client loop to monitor messages and handle publishing
        self.loop_start()

    def stop(self):
        logger.info(f"Stopping MQTT broker")
        self.loop_stop()

    def add_to_subscription_dict(self, topic: str, callback: Callable[[str, str], None]):
        # Add a topic to listen to and the method that should be called when a message is published to that topic
        # Should be one for each MQTT device
        self.subscription_dict[topic] = callback

    def subscribe_to_device_topics(self):
        # Subscribe to all topics in the subscription dictionary
        for key in self.subscription_dict.keys():
            self.subscribe(key)
            logger.debug(f"Subscribing to {key}")

    def my_publish_callback(self, topic, msg):
        # TODO: Could not use publish directly. Investigate why that was the case
        self.publish(topic, msg)

    def publish(self, topic, payload=None, qos=0, retain=False, properties=None):
        # for debug reasons
        super().publish(topic, payload, qos, retain, properties)

    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"On connect callback, code {rc}")
        if rc == 0:
            self.status = self.STATUS_CONNECTED
            self.notify_observers(self.event_name_status_change)
            self.subscribe_to_device_topics()
        else:
            # TODO: handle automatic reconnection attempt after delay
            logger.warning(f"Unable to connect to MQTT broker")

    def on_disconnect(self, client, userdata, rc):
        logger.info(f"Disconnected from MQTT broker, code {rc}")
        self.status = self.STATUS_DISCONNECTED
        self.notify_observers(self.event_name_status_change)

    def on_message(self, client, userdata, msg):
        logger.debug(msg.topic + " " + str(msg.payload))
        # Forward the message to the appropriate device
        self.forward_mqtt_msg(topic=msg.topic, msg=str(msg.payload))

    def forward_mqtt_msg(self, topic: str, msg: str):
        """
        Check if the received MQTT message belongs to a topic being listened to by a device. If so, call the callback
        method
        :param topic: message topic
        :param msg: message payload
        :return:
        """
        for listen_topic, callback in self.subscription_dict.items():
            listen_topic_beginning = self._get_listen_topic(listen_topic)
            if topic.startswith(listen_topic_beginning):
                callback(topic, msg)

    def _get_listen_topic(self, topic: str) -> str:
        """
        If a device topic was marked with a '#' at the end to listen to all subtopics, take that off so string
        comparisson can be executed
        :param topic:
        :return:
        """
        if topic.endswith("#"):
            topic = topic[:-1]
        else:
            topic = topic
        return topic


if __name__ == '__main__':
    test()
