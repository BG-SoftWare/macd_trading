import datetime

from sqlalchemy import DECIMAL
from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, Enum, BigInteger
from sqlalchemy import create_engine, insert

with open(".env", "r") as env_file:
    keys = env_file.readlines()


class DatabaseConnector(object):
    CONNECTION_STRING = keys[0].split("=")[1].rstrip()

    meta = MetaData()

    trading = Table(
        "trading", meta,
        Column('id', Integer, primary_key=True),
        Column('ticker', String(50)),
        Column('open_order_id', BigInteger),
        Column('position', String(10)),
        Column('open_price', DECIMAL(20, 8)),
        Column('take_profit_price', DECIMAL(20, 8)),
        Column('stop_loss_price', DECIMAL(20, 8)),
        Column('close_order_id', BigInteger),
        Column('close_price', DECIMAL(20, 8)),
        Column('close_reason', Enum("TP", "SL", "Change MACD")),
        Column('fee_amount', DECIMAL(20, 8)),
        Column('profit', DECIMAL(20, 8)),
        Column('open_position_time', DateTime),
        Column('close_position_time', DateTime, default=datetime.datetime.now)
    )

    def __init__(self):
        self.engine = create_engine(self.CONNECTION_STRING, pool_pre_ping=True)
        self.meta.bind = self.engine
        self.meta.create_all()

    def insert_data(self, data):
        conn = self.engine.connect()
        conn.execute(insert(self.trading), data)
        conn.close()
        self.engine.dispose()
