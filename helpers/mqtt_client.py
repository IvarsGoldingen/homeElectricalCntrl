import paho.mqtt.client as mqtt
import logging
import os
import threading
import time
from queue import Queue
from typing import Callable
from enum import Enum, auto
from helpers.observer_pattern import Subject
import secrets

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "mqtt_client.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def test():
    client = MyMqttClient()
    # client.add_listen_topic("#", test_cb)
    # client.add_listen_topic("shellyplus1-441793ab3fb4/#", test_cb)
    client.add_listen_topic("shellyplus1pm-d48afc417d58/#", test_cb)
    # client.add_listen_topic("shellies/shellyplug-s-80646F840029/#", test_cb)
    client.start(secrets.MQTT_SERVER, secrets.MQTT_PORT, user=secrets.MQTT_USER, psw=secrets.MQTT_PSW)
    device_bool = False
    test_cntr = 0
    try:
        while True:
            time.sleep(0.5)
            client.loop()
            test_cntr += 1
            if test_cntr % 20 == 0:
                if not device_bool:
                    print("turning on")
                    # client.publish("shellyplus1-441793ab3fb4/command/switch:0", "on")
                    client.publish("shellyplus1pm-d48afc417d58/command/switch:0", "on")
                    # get status of shelly relay
                    # client.publish("shellyplus1-441793ab3fb4/command", "status_update")
                    client.publish("shellyplus1pm-d48afc417d58/command", "status_update")
                    # For plug
                    # client.publish("shellies/shellyplug-s-80646F840029/relay/0/command", "on")
                else:
                    print("turning off")
                    # client.publish("shellyplus1-441793ab3fb4/command/switch:0", "off")
                    client.publish("shellyplus1pm-d48afc417d58/command/switch:0", "off")
                device_bool = not device_bool
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught. Exiting gracefully.")
    finally:
        client.stop()


def test_cb(topic: str, payload: str):
    print(f"Callback {topic} {payload}")


class MyMqttClient(Subject):
    """
    Used to publish and subscribe to mqtt topics.
    Mqtt client itself is a subclass which is run on a separate thread.
    This class is an interface that connects the mqtt client with the main program.
    Data exchange is done via Queues.
    """
    # For the observer pattern
    event_name_status_change = "mqtt_status_changed"

    def __init__(self):
        Subject.__init__(self)
        self.status = self.MqttClientThread.STATUS_DISCONNECTED
        # Queues for data exchange with the mqtt client thread
        self.queue_to_mqtt_thread = Queue()
        self.queue_from_mqtt_thread = Queue()
        # A dictionary holding topics to listen to and corresponding callbacks when a message has been published to that
        # topic
        self.subscription_dict = {}

    def start(self, broker_addr: str, port: int, user: str, psw: str):
        # Start the mqtt client thread
        self.mqtt_cl_thread = self.MqttClientThread(broker_addr=broker_addr, port=port, user=user, psw=psw,
                                                    queue_to_mqtt_thread=self.queue_to_mqtt_thread,
                                                    queue_from_mqtt_thread=self.queue_from_mqtt_thread)
        self.mqtt_cl_thread.start()

    def loop(self):
        """
        Has to be called periodically
        """
        self.handle_msgs_from_mqtt_client()

    def handle_msgs_from_mqtt_client(self):
        while not self.queue_from_mqtt_thread.empty():
            msg = self.queue_from_mqtt_thread.get()
            logger.debug(f"MSG from mqtt thread {msg}")
            if msg["msg_type"] == self.mqtt_cl_thread.MsgType.MQTT_CLIENT_STATUS_CHANGE:
                # The mqtt client has connected to or disconnected from the broker
                self.status = msg["data"]
                self.notify_observers(self.event_name_status_change)
            elif msg["msg_type"] == self.mqtt_cl_thread.MsgType.NEW_MQTT_MSG_RECEIVED:
                # New Mqtt message received
                self.forward_mqtt_msg(topic=msg["topic"], msg=msg["msg"])
            else:
                logger.error(f"Unknown message from mqtt thread {msg}")

    def add_listen_topic(self, topic: str, callback: Callable[[str, str], None]):
        # Add a topic to listen to and the method that should be called when a message is published to that topic
        # Should be one for each MQTT device
        self.subscription_dict[topic] = callback
        # The client itself is only interested in the topic, the callback will be called from this class
        self.queue_to_mqtt_thread.put({"msg_type": self.MqttClientThread.MsgType.NEW_LISTEN_TOPIC,
                                       "data": topic})

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

    def publish(self, topic: str, payload: str):
        # Publish data to mqtt broker
        self.queue_to_mqtt_thread.put({"msg_type": self.MqttClientThread.MsgType.PUBLISH_MSG,
                                       "topic": topic, "msg": payload})

    def stop(self):
        # Stop mqtt client
        self.queue_to_mqtt_thread.put({"msg_type": self.MqttClientThread.MsgType.STOP})
        logger.debug("Join start")
        self.mqtt_cl_thread.join()
        logger.debug("Join end")

    def _get_listen_topic(self, topic: str) -> str:
        """
        If a device topic was marked with a '#' at the end to listen to all subtopics, take that off so string
        comparison can be executed
        :param topic:
        :return:
        """
        if topic.endswith("#"):
            topic = topic[:-1]
        else:
            topic = topic
        return topic

    class MqttClientThread(threading.Thread):
        """
        Class that uses paho mqtt.Client
        Runs on a separate thread. Needed for tkinter to run without errors.
        """

        # Connection status constants
        STATUS_DISCONNECTED = 0
        STATUS_CONNECTED = 1

        class MsgType(Enum):
            # Message types that can be exchanged between the client class and the main mqtt class
            MQTT_CLIENT_STATUS_CHANGE = auto()
            NEW_MQTT_MSG_RECEIVED = auto()
            STOP = auto()
            PUBLISH_MSG = auto()
            NEW_LISTEN_TOPIC = auto()

        def __init__(self, broker_addr: str, port: int, user: str, psw: str, queue_to_mqtt_thread: Queue,
                     queue_from_mqtt_thread: Queue):
            super().__init__()
            self.mqtt_client = mqtt.Client()
            self.setup_mqtt_client(user, psw)
            self.queue_to_mqtt_thread = queue_to_mqtt_thread
            self.queue_from_mqtt_thread = queue_from_mqtt_thread
            self.status = self.STATUS_DISCONNECTED
            self.broker_addr = broker_addr
            self.port = port
            # TODO: currently all data is subscribed to when the mqtt client connects. If new topics are added after
            # connection it has to be handled differently
            # A list holding topics to listen to
            self.subscription_list = []

        def setup_mqtt_client(self, user: str, psw: str):
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.reconnect_delay_set(min_delay=10, max_delay=60)  # in seconds
            self.mqtt_client.username_pw_set(user, psw)

        def run(self):
            self.start_mqtt_client()
            self.handle_msgs()

        def handle_msgs(self):
            """
            Handle messages from the main mqtt class
            Loop until stop is given
            """
            run = True
            while run:
                while not self.queue_to_mqtt_thread.empty():
                    data = self.queue_to_mqtt_thread.get()
                    if data["msg_type"] == self.MsgType.NEW_LISTEN_TOPIC:
                        topic = data["data"]
                        self.subscription_list.append(topic)
                    elif data["msg_type"] == self.MsgType.PUBLISH_MSG:
                        topic = data["topic"]
                        payload = data["msg"]
                        self.publish(topic=topic, payload=payload)
                    elif data["msg_type"] == self.MsgType.STOP:
                        self.stop()
                        run = False
                time.sleep(0.5)

        def start_mqtt_client(self):
            logger.info(f"Connecting to MQTT broker. {self.broker_addr}:{self.port}")
            # self.connect(host=self.broker_addr, port=self.port, keepalive=60, bind_address="")
            self.mqtt_client.connect_async(host=self.broker_addr, port=self.port, keepalive=60, bind_address="")
            # start mqtt client loop to monitor messages and handle publishing
            self.mqtt_client.loop_start()

        def publish(self, topic, payload=None, qos=0, retain=False, properties=None):
            # for debug reasons
            self.mqtt_client.publish(topic, payload, qos, retain, properties)

        def on_connect(self, client, userdata, flags, rc):
            """
            Callback for Mqtt client
            """
            logger.info(f"On connect callback, code {rc}")
            if rc == 0:
                self.status = self.STATUS_CONNECTED
                self.queue_from_mqtt_thread.put(
                    {"msg_type": self.MsgType.MQTT_CLIENT_STATUS_CHANGE, "data": self.status})
                self.subscribe_to_device_topics()
            else:
                logger.warning(f"Unable to connect to MQTT broker")

        def on_disconnect(self, client, userdata, rc):
            """
            Callback for Mqtt client
            """
            logger.info(f"Disconnected from MQTT broker, code {rc}")
            self.status = self.STATUS_DISCONNECTED
            self.queue_from_mqtt_thread.put(
                {"msg_type": self.MsgType.MQTT_CLIENT_STATUS_CHANGE, "data": self.status})

        def on_message(self, client, userdata, msg):
            logger.debug(f"Msg received {msg.topic} {str(msg.payload)}")
            # Forward the message to the main mqtt class
            self.queue_from_mqtt_thread.put(
                {"msg_type": self.MsgType.NEW_MQTT_MSG_RECEIVED, "topic": msg.topic, "msg": str(msg.payload)})

        def stop(self):
            logger.info(f"Stopping MQTT broker")
            self.mqtt_client.loop_stop()
            logger.info(f"Stopped MQTT broker")

        def subscribe_to_device_topics(self):
            # Subscribe to all topics in the subscription list
            for topic in self.subscription_list:
                self.mqtt_client.subscribe(topic)
                logger.debug(f"Subscribing to {topic}")

    status_strings = {
        MqttClientThread.STATUS_DISCONNECTED: "MQTT NOT CONNECTED",
        MqttClientThread.STATUS_CONNECTED: "MQTT CONNECTED"
    }


if __name__ == '__main__':
    test()
