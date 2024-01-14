import sqlite3
import os
from datetime import datetime, timedelta, timezone
from devices.deviceTypes import DeviceType


def main_fc():
    db_mngr = DbMngr()
    db_mngr.create_table_of_sensors()
    db_mngr.create_table_of_sensor_data()
    db_mngr.insert_sensor(name="ahu_t_in")
    db_mngr.insert_sensor_data(name="ahu_t_in", value=12.49)
    # db_mngr.create_all_tables()
    # insert_new_device_in_dev_table(db_mngr)
    # insert_fake_devices(db_mngr)
    # insert_fake_prices(db_mngr)
    # insert_fake_shelly_data(db_mngr)
    # db_mngr.delete_column(table_name='shelly_data', column_to_delete='record_time')
    # db_mngr.rename_column(table_name='shelly_data', column_to_rename='record_time_new', new_name='record_time')
    # db_mngr.fix_date_time_price_table()
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
    shelly_data - data containing shelly smartplug data - linked to the devices table
    sensors - list of sensors used in the project
    sensor_data - read sensor values - linked to sensors table
    TODO: Auto delete data older than
    """

    def __init__(self, db_name: str = "home_data.db",
                 db_loc: str = "C:\\py_related\\home_el_cntrl\\db"):
        """
        :param db_name: database name
        :param db_loc: database location
        """
        self.db_name = db_name
        self.db_loc = db_loc
        db_w_path = os.path.join(db_loc, db_name)
        self.conn = sqlite3.connect(db_w_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def show_last_ten_rows(self, table_name):
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
        """
        # Execute a SELECT query to retrieve the last 10 rows from a table (replace 'your_table' with the actual table name)
        self.cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 10")
        # Fetch the last 10 rows from the result set
        rows = self.cursor.fetchall()
        # Iterate through the rows and print the data
        for row in rows:
            print(row)

    def fix_date_time_price_table(self):
        """
        Time in table was saved in GMT+2. Change so it is GMT.
        """
        # get data to be changed
        self.cursor.execute(f"SELECT id, date, hour FROM prices ORDER BY id")
        rows = self.cursor.fetchall()
        date_format = "%Y-%m-%d"
        for row in rows:
            id, date_str, hour = row
            new_date_str = date_str
            new_hour = hour - 2
            if new_hour < 0:
                new_hour = 24 + new_hour
                date_new_obj = datetime.strptime(date_str, date_format) - timedelta(days=1)
                new_date_str = str(date_new_obj.date())
            self.cursor.execute('UPDATE prices SET date = ?, hour = ? WHERE id = ?',
                                (new_date_str, new_hour, id))
        self.conn.commit()

    def insert_new_column(self, table_name, row_name):
        # record_time_new
        self.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {row_name} TEXT")
        self.conn.commit()

    def create_all_tables(self):
        # Create tables in db
        self.create_table_of_devices()
        self.create_table_for_prices()
        self.create_table_for_shelly_data()
        self.create_table_of_sensors()
        self.create_table_of_sensor_data()

    def insert_shelly_data(self, name: str, off_on: bool, power: float, status: int, energy: float):
        """
        :param name: Shelly plug name
        :param off_on: devices state on or off
        :param power: current power - received from MQTT
        :param status: status from the device class
        :param energy: current energy - received from MQTT
        :return:
        """
        current_time = datetime.now(timezone.utc)
        formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        date_str = str(current_time.date())
        # when inserting, get the device ID using the device name
        self.cursor.execute('INSERT INTO shelly_data '
                            '(device_id, record_time, date, off_on, power, device_status, energy) '
                            'VALUES ((SELECT device_id FROM devices WHERE name = ?), '
                            '?, ?, ?, ?, ?, ?)',
                            (name, formatted_time, date_str, off_on, power, status, energy))
        self.conn.commit()

    def insert_sensor_data(self, name: str, value: float):
        """
        :param name: Shelly plug name
        :param value:
        :return:
        """
        current_time = datetime.now(timezone.utc)
        formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        date_str = str(current_time.date())
        # when inserting, get the device ID using the device name
        self.cursor.execute('INSERT INTO sensor_data '
                            '(device_id, record_time, date, value) '
                            'VALUES ((SELECT device_id FROM sensors WHERE name = ?), '
                            '?, ?, ?)',
                            (name, formatted_time, date_str, value))
        self.conn.commit()

    def insert_prices(self, prices: dict, date: datetime.date):
        """
        :param prices: price dictionary
        :param date: date of price dictionary
        :return:
        """
        dif_from_utc = self.get_dif_from_utc()
        date_str_today = str(date)
        date_str_yesterday = str(date - timedelta(days=1))
        for hour, value in prices.items():
            hour_utc = hour - dif_from_utc
            if hour_utc < 0:
                hour_utc = 24 + hour_utc
                date_str_to_use = date_str_yesterday
            else:
                date_str_to_use = date_str_today
            self.cursor.execute('INSERT INTO prices (date, hour, price) VALUES (?, ?, ?)',
                                (date_str_to_use, hour_utc, value))
        self.conn.commit()

    @staticmethod
    def get_dif_from_utc():
        # get dif from UTC time
        local_time = datetime.now()
        # Get the UTC time
        utc_time = datetime.utcnow()
        # Calculate the time difference between local timezone and UTC
        time_difference = local_time - utc_time
        return round(time_difference.total_seconds() / 3600)

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

    def insert_sensor(self,  name: str, sensor_type: int = 0, active: bool = True):
        """
        @param name: name of sensor
        @param sensor_type: not yet implemented
        @param active: Active or not
        """
        self.conn.execute("INSERT INTO sensors (type, name, active) VALUES (?, ? ,?)",
                          (sensor_type, name, active))
        self.conn.commit()

    def create_table_for_prices(self):
        """
        Create a table for prices
        Not possible to add duplicate values of a date and hour
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

    def create_table_of_sensors(self):
        """
        Create a table for sensors present in home automation
        :return:
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sensors (
                              device_id INTEGER PRIMARY KEY,
                              type INTEGER,
                              name TEXT,
                              active BOOLEAN
                           )''')
        self.conn.commit()

    def create_table_of_sensor_data(self):
        """
        Create a table for sensor data
        Device id connected to the sensor table
        :return:
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
                              id INTEGER PRIMARY KEY,
                              device_id INTEGER,
                              record_time DATETIME,
                              date DATE,
                              value FLOAT,
                              FOREIGN KEY(device_id) REFERENCES sensors(device_id)
                           )''')
        # Device id and date will be used to get data from the table so create index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS sensor_data_index ON sensor_data(device_id, date)")
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

    def create_correct_datetime_column_shelly_data(self):
        """
        Time in table was saved in GMT+2. Change so it is GMT.
        """
        self.insert_new_column("shelly_data", "record_time_new")
        self.cursor.execute(f"SELECT id, record_time FROM shelly_data ORDER BY id")
        date_format = "%Y-%m-%d %H:%M:%S"
        # Fetch the last 10 rows from the result set
        rows = self.cursor.fetchall()
        print(f"Total number of rows {len(rows)}")
        for row in rows:
            id, date_str = row
            datetime_object = datetime.strptime(date_str, date_format)
            datetime_corrected = datetime_object + timedelta(hours=-2)
            datetime_str_corrected = datetime_corrected.strftime(date_format)
            date_str_corrected = str(datetime_corrected.date())
            self.cursor.execute('UPDATE shelly_data SET date = ?, record_time_new = ? WHERE id = ?',
                                (date_str_corrected, datetime_str_corrected, id))
        self.conn.commit()

    def delete_column(self, table_name: str = 'shelly_data', column_to_delete: str = 'record_time'):
        # Delete a column by first createing a new table without the column to delete, then deleting the old table,
        # then renamin the new table to have the original name
        columns = [col[1] for col in self.cursor.execute(f"PRAGMA table_info({table_name})").fetchall() if
                   col[1] != column_to_delete]
        self.cursor.execute(f'''
            CREATE TABLE new_{table_name} AS
            SELECT 
                {', '.join(columns)}
            FROM {table_name}
        ''')
        self.cursor.execute(f'DROP TABLE {table_name}')
        # Rename the new table to the original table name
        self.cursor.execute(f'ALTER TABLE new_{table_name} RENAME TO {table_name}')
        # Commit the changes to the database
        self.conn.commit()

    def rename_column(self, table_name: str = 'shelly_data', column_to_rename: str = 'record_time_new',
                      new_name: str = 'record_time'):
        # After fixing the date, delete the old row and rename the temporary one.
        # Can only be done by deleting the table
        # Create a new table without the specified column and with the renamed column
        # Get column names excluding the one to be deleted
        columns = [col[1] for col in self.cursor.execute(f"PRAGMA table_info({table_name})").fetchall() if
                   col[1] != column_to_rename]
        # Create a new table without the specified column and with the renamed column
        self.cursor.execute(f'''
            CREATE TABLE new_{table_name} AS
            SELECT 
                {', '.join(columns)},
                {column_to_rename} AS {new_name}
            FROM {table_name}
        ''')
        # Drop the old table
        self.cursor.execute(f'DROP TABLE {table_name}')
        # Rename the new table to the original table name
        self.cursor.execute(f'ALTER TABLE new_{table_name} RENAME TO {table_name}')
        # Commit the changes to the database
        self.conn.commit()

    def stop(self):
        self.conn.close()


if __name__ == '__main__':
    main_fc()
