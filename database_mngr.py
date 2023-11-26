import sqlite3
import os
from datetime import datetime, timedelta
from devices.deviceTypes import DeviceType


def main_fc():
    db_mngr = DbMngr()
    #db_mngr.create_all_tables()
    insert_new_device_in_dev_table(db_mngr)
    # insert_fake_devices(db_mngr)
    # insert_fake_prices(db_mngr)
    # insert_fake_shelly_data(db_mngr)
    db_mngr.stop()

def insert_new_device_in_dev_table(db_mngr):
    # device name must be equal to the name in the program for logging to work properly
    # db_mngr.insert_device(dev_type=DeviceType.SHELLY_PLUG.value,
    #                       name="Plug 1",
    #                       plug_id="shellyplug-s-80646F840029",
    #                       active=True)
    db_mngr.insert_device(dev_type=DeviceType.SHELLY_PLUG.value,
                          name="Plug 2",
                          plug_id="shellyplug-s-C8C9A3B8E92E",
                          active=True)

def insert_fake_devices(db_mngr):
    db_mngr.insert_device(dev_type=DeviceType.FAKE.value, name="sample_device1", plug_id="111", active=True)
    db_mngr.insert_device(dev_type=DeviceType.FAKE.value, name="sample_device2", plug_id="222", active=True)
    db_mngr.insert_device(dev_type=DeviceType.FAKE.value, name="sample_device3", plug_id="333", active=True)

def insert_fake_prices(db_mngr):
    fake_prices = {hour: hour * 12.55 for hour in range(24)}
    tomorrows_date = datetime.today().date() + timedelta(days=1)
    db_mngr.insert_prices(fake_prices, tomorrows_date)

def insert_fake_shelly_data(db_mngr):
    db_mngr.insert_shelly_data("sample_device1", True, 111.0, 6, energy=440.01)
    db_mngr.insert_shelly_data("sample_device11", True, 111.0, 6, energy=440.01)
    db_mngr.insert_shelly_data("sample_device2", True, 222.0, 6, energy=440.01)
    db_mngr.insert_shelly_data("sample_device2", True, 222.0, 6, energy=440.01)
    db_mngr.insert_shelly_data("sample_device2", True, 222.0, 6, energy=440.01)
    db_mngr.insert_shelly_data("sample_device3", True, 333.0, 6, energy=440.01)


class DbMngr:
    """
    Class for storing home automation related data in database
    Project has 3 tables:
    devices - list of devices used in the project
    prices - electricity prices
    shelly_data - data containing shelly smartplug data
    TODO: Auto delete data older than
    """
    def __init__(self, db_name: str = "home_data.db", db_loc: str = "C:\\py_related\\home_el_cntrl\\db"):
        """
        :param db_name: database name
        :param db_loc: database location
        """
        self.db_name = db_name
        self.db_loc = db_loc
        db_w_path = os.path.join(db_loc, db_name)
        self.conn = sqlite3.connect(db_w_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def create_all_tables(self):
        "Create tables in db"
        self.create_table_of_devices()
        self.create_table_for_prices()
        self.create_table_for_shelly_data()

    def insert_shelly_data(self, name:str, off_on: bool, power: float, status:int, energy: float):
        """
        :param name: Shelly plug name
        :param off_on: devices state on or off
        :param power: current power - received from MQTT
        :param status: status from the device class
        :param energy: current energy - received from MQTT
        :return:
        """
        current_time = datetime.now()
        formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        date_str = str(current_time.date())
        # when inserting, get the device ID using the device name
        self.cursor.execute('INSERT INTO shelly_data '
                            '(device_id, record_time, date, off_on, power, device_status, energy) '
                            'VALUES ((SELECT device_id FROM devices WHERE name = ?), '
                            '?, ?, ?, ?, ?, ?)',
                            (name,formatted_time, date_str, off_on, power, status, energy))
        self.conn.commit()

    def insert_prices(self, prices: dict, date: datetime.date):
        """
        :param prices: price dictionary
        :param date: date of price dictionary
        :return:
        """
        date_str = str(date)
        for hour, value in prices.items():
            self.cursor.execute('INSERT INTO prices (date, hour, price) VALUES (?, ?, ?)', (date_str, hour, value))
        self.conn.commit()

    def insert_device(self, dev_type: DeviceType, name: str, plug_id: str = "", active: bool = True):
        """
        :param dev_type: Type of device
        :param name: Device name - for UI only
        :param plug_id: For shelly plugs, used to identify them in the MQTT server
        :param active: Active or not
        :return:
        """
        self.conn.execute("INSERT INTO devices (type, name, plug_id, active) VALUES (?, ?, ? ,?)",
                          (dev_type, name, plug_id, active))
        self.conn.commit()

    def create_table_of_devices(self):
        """
        Create a table for devices present in home automation
        :return:
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS devices (
                              device_id INTEGER PRIMARY KEY,
                              type INTEGER,
                              name TEXT,
                              plug_id TEXT,
                              active BOOLEAN
                           )''')
        self.conn.commit()

    def create_table_for_prices(self):
        """
        Create a table for prices
        Not possible to add dublicate values of a date and hour
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS prices (
                              id INTEGER PRIMARY KEY,
                              date DATE,
                              hour INTEGER,
                              price FLOAT,
                              UNIQUE(date, hour) ON CONFLICT IGNORE
                           )''')
        # Date and hour will be used to get data from the table so create index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS prices_index ON prices(date, hour)")
        self.conn.commit()

    def create_table_for_shelly_data(self):
        """
        Create a table for shelly plug data
        Device id connected to the device table
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS shelly_data (
                              id INTEGER PRIMARY KEY,
                              device_id INTEGER,
                              record_time DATETIME,
                              date DATE,
                              off_on BOOLEAN,
                              power FLOAT,
                              device_status INTEGER,
                              energy FLOAT,
                              FOREIGN KEY(device_id) REFERENCES devices(device_id)
                           )''')
        # Device id and date will be used to get data from the table so create index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS shelly_data_index ON shelly_data(device_id, date)")
        self.conn.commit()

    def stop(self):
        self.conn.close()


if __name__ == '__main__':
    main_fc()
