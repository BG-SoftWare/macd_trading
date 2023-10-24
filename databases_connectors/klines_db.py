from sqlalchemy import DECIMAL
from sqlalchemy import Table, Column, Integer, String, MetaData, BigInteger, bindparam
from sqlalchemy import create_engine, insert, text

with open(".env", "r") as env_file:
    keys = env_file.readlines()


class DatabaseConnector(object):
    CONNECTION_STRING = keys[7].split("=")[1].rstrip()

    meta = MetaData()

    klines = Table(
        "klines", meta,
        Column('id', Integer, primary_key=True),
        Column('ticker', String(50)),
        Column('open_time', BigInteger),
        Column('open', DECIMAL(20, 8)),
        Column('high', DECIMAL(20, 8)),
        Column('low', DECIMAL(20, 8)),
        Column('close', DECIMAL(20, 8)),
        Column('volume', DECIMAL(20, 8)),
        Column('close_time', BigInteger)
    )

    def __init__(self):
        self.engine = create_engine(self.CONNECTION_STRING, pool_pre_ping=True)
        self.meta.bind = self.engine
        self.meta.create_all()

    def insert_data(self, ticker, data):
        conn = self.engine.connect()
        insert_query = insert(self.klines).values(ticker=ticker,
                                                  open_time=bindparam("open_time"),
                                                  open=bindparam("open"),
                                                  high=bindparam("high"),
                                                  low=bindparam("low"),
                                                  close=bindparam("close"),
                                                  volume=bindparam("volume"),
                                                  close_time=bindparam("close_time"))
        conn.execute(insert_query, data)
        conn.close()
        self.engine.dispose()

    def select_klines(self, ticker, ts_start=None, ts_finish=None, count=None):
        conn = self.engine.connect()
        if ts_start is not None and ts_finish is not None:
            query = text(
                """
                SELECT open_time, open, close, close_time
                FROM klines
                WHERE ticker = :ticker AND open_time BETWEEN :ts_start AND :ts_finish
                ORDER BY open_time ASC;
                """
            )
            result = conn.execute(query, ticker=ticker, ts_start=ts_start, ts_finish=ts_finish).fetchall()
        elif ts_finish is not None:
            query = text(
                """
                SELECT open_time, open, close, close_time
                FROM klines
                WHERE ticker = :ticker AND open_time <= :ts_finish
                ORDER BY open_time DESC LIMIT :count;
                """
            )
            result = conn.execute(query, ticker=ticker, ts_finish=ts_finish, count=count)
        else:
            query = text(
                """
                SELECT open_time, open, close, close_time
                FROM klines
                WHERE ticker = :ticker;
                """
            )
            result = conn.execute(query, ticker=ticker).fetchall()
        if result is not None:
            if len(result) > 0:
                return result
        else:
            return []
