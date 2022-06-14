import logging
from typing import Optional
import zlib
from paho.mqtt import client as mqtt

from custom_components.xiaomi_cloud_map_extractor.common.connector import Connector

_LOGGER = logging.getLogger(__name__)


# noinspection PyBroadException
class ValetudoLocalConnector(Connector):

    def __init__(self, username, password):
        self.two_factor_auth_url = None
        self._mqttclient = None
        self._username = username
        self._password = password
        self._mqttServer = "raspi.home"
        self._mqttPort = 1883
        self._vacuumIdentifier = "Dreame"
        self._mqttPrefix = "valetudo"
        self._rawMapData = None
        self._vacuumName = None

    def login(self):
        self._mqttclient = mqtt.Client()
        self._mqttclient.on_message = self.on_message
        self._mqttclient.on_connect = self.on_connect
        self._mqttclient.username_pw_set(self._username, self._password)
        self._mqttclient.connect_async(self._mqttServer, self._mqttPort, 60)
        self._mqttclient.loop_start()
        return True

    def on_connect(self, client, userdata, flags, rc):
        self._mqttclient.subscribe(self._mqttPrefix + "/" + self._vacuumIdentifier + "/MapData/map-data")
        self._mqttclient.subscribe(self._mqttPrefix + "/" + self._vacuumIdentifier + "/$name")

    def on_message(self, client, userdata, msg):
        if msg.topic.endswith("$name"):
            self._vacuumName = msg.payload.decode()
        elif msg.topic.endswith("map-data"):
            self._rawMapData = zlib.decompress(msg.payload)

    def get_raw_map_data(self, map_url) -> Optional[bytes]:
        return self._rawMapData

    def get_device_details(self, token, country):
        if self._vacuumName is None:
            return None, None, None, "valetudo"

        return None, None, self._vacuumName, "valetudo"
