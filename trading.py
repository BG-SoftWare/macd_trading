import datetime
import json
import os
from configparser import ConfigParser
from decimal import Decimal

import certifi
import click
import numpy as np
import requests
from binance.websocket.spot.websocket_client import SpotWebsocketClient as spot_ws

import general_logger
from binance_connector import Binance
from databases_connectors.klines_db import DatabaseConnector

os.environ['SSL_CERT_FILE'] = certifi.where()


class Strategy:
    SHORT = "SHORT"
    LONG = "LONG"
    __config = ConfigParser()
    __config.read("config.ini")
    __klines_matching = {
        "1h": 1,
        "2h": 2,
        "4h": 4,
        "8h": 8,
        "12h": 12,
        "1d": 24
    }
    __spot_client_ws = spot_ws(stream_url=__config['main']['wss_url_spot'])
    __db = DatabaseConnector()

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.logger = general_logger.get_logger("Strategy", self.ticker)
        self.macd_config = self.read_macd_config()
        self.__bot = Binance(self.ticker)
        self.__bot.get_pairs_info()
        self.cache = self.get_start_data()
        self.filters_cache = {}
        self._slow_ma = int(self.macd_config[ticker]['slow_ma'])
        self._fast_ma = int(self.macd_config[ticker]['fast_ma'])
        self._signal = int(self.macd_config[ticker]['signal'])
        self._stop_loss = Decimal(self.macd_config[ticker]['stop_loss'])
        self._take_profit = Decimal(self.macd_config[ticker]['take_profit'])

    def macd_analyzer(self):
        """
        Analyzes the current MACD value and opens a position if necessary
        """
        macd_hist = self.macd(self.cache, fast_period=self._fast_ma, slow_period=self._slow_ma,
                              signal_period=self._signal)
        previous_value = macd_hist[-2]
        value = macd_hist[-1]
        if previous_value < 0 <= value:
            self.logger.info("Signal for LONG")
            if self.__bot.open_position:
                self.logger.warning("It have open position already. Change signal without closing position "
                                    "by TP or SL activate close position by signal change")
                self.__bot.close_position(Decimal(self.macd_config[self.ticker]['token_qty']))
            if not self.__bot.open_position:
                self.__bot.open_position(self.LONG, Decimal(self.macd_config[self.ticker]['token_qty']),
                                         Decimal(self._take_profit), Decimal(self._stop_loss))
                self.logger.info("Order have been placed")
            else:
                self.logger.info("Position isn't closed. Can't open new position.")
        elif previous_value > 0 >= value:
            self.logger.info("Signal for SHORT")
            if self.__bot.open_position:
                self.logger.warning("It have open position already. Change signal without closing position "
                                    "by TP or SL activate close position by signal change")
                self.__bot.close_position(Decimal(self.macd_config[self.ticker]['token_qty']))
            if not self.__bot.open_position:
                self.__bot.open_position(self.SHORT, Decimal(self.macd_config[self.ticker]['token_qty']),
                                         Decimal(self._take_profit), Decimal(self._stop_loss))
                self.logger.info("Order have been placed")
            else:
                self.logger.info("Position isn't closed. Can't open new position.")

    @staticmethod
    def ema(close: np.ndarray, period: int) -> np.ndarray:
        """
        Calculates the EMA for the specified series for the specified period
        :param close: Array of klines closure values
        :param period: EMA period
        :return: Array of calculated EMA values
        """
        alpha = 2 / (period + 1)
        ema_calc = np.zeros_like(close)
        ema_calc[0] = float(close[0])
        for i in range(1, close.shape[0]):
            ema_calc[i] = alpha * float(close[i]) + (1 - alpha) * float(ema_calc[i - 1])
        return ema_calc.astype(float)

    def macd(self, klines: np.ndarray, fast_period: int, slow_period: int, signal_period: int) -> np.ndarray:
        """
        Calculates MACD values from the specified EMA durations
        :param klines: Array of klines closure values
        :param fast_period: Period of short EMA
        :param slow_period: Period of long EMA
        :param signal_period: Signal value for EMA
        :return: Array of calculated MACD values
        """
        ema_fast = self.ema(klines, fast_period)
        ema_slow = self.ema(klines, slow_period)
        macd_calc = ema_fast - ema_slow
        signal = self.ema(macd_calc, signal_period)
        hist = macd_calc - signal
        return hist

    def price_handler(self, message: dict) -> None:
        """
        Callback function for WebSockets stream
        :param message: Message from the exchange
        """
        if "result" in message.keys():
            pass
        else:
            if message['k']['x']:
                kline = [message["k"]["t"], message["k"]["o"], message["k"]["c"], message["k"]["T"]]
                result = np.append(self.cache, float(kline[2]))
                result = np.delete(result, 0)
                self.cache = result
                self.macd_analyzer()

    def price_stream(self):
        self.__spot_client_ws.start()
        self.__spot_client_ws.kline(
            symbol=self.ticker,
            id=2,
            interval=self.macd_config[self.ticker]["klines_duration"],
            callback=self.price_handler
        )

    @staticmethod
    def read_macd_config():
        with open("configs/macd_config.json", "r") as config_file:
            macd_config = json.load(config_file)
        return macd_config

    def get_start_data(self) -> np.ndarray:
        """
        Queries the exchange for the last 1000 values of klines for the desired ticker and converts them to NumpyArray
        :return: Received value in the form of NumpyArray
        """
        required_ts = int(datetime.datetime.timestamp(
            datetime.datetime.now() - datetime.timedelta(seconds=datetime.datetime.now().second))
        ) * 1000
        base_klines_url = f"https://api.binance.com/api/v3/klines?symbol={self.ticker}"
        downloading_url = base_klines_url + f"&interval={self.macd_config[self.ticker]['klines_duration']}" \
                                            f"&endTime={required_ts}" \
                                            f"&limit=1000"
        response = requests.get(downloading_url).json()
        clear_klines = [[int(row[0]), row[1], row[4], int(row[6])] for row in response]
        sorted_klines_list = sorted(clear_klines, key=lambda x: x[0])
        return np.asarray([float(close[2]) for close in sorted_klines_list])


@click.command()
@click.argument("ticker")
def run(ticker):
    bot = Strategy(ticker.upper())
    bot.price_stream()


if __name__ == "__main__":
    run()
