import datetime
import hashlib
import hmac
import logging
import time
from configparser import ConfigParser
from decimal import Decimal
from threading import Event, Thread
from urllib.parse import urlencode

import requests
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient as futures_ws

import general_logger
from databases_connectors.database_connector import DatabaseConnector
from objects.order import Order
from databases_connectors.redis_connector import RedisClient

with open(".env", "r") as env_file:
    keys = env_file.readlines()


class Binance:
    __API_KEY = keys[5].split("=")[1].rstrip()
    __API_SECRET = keys[6].split("=")[1].rstrip()
    __orders_side = {
        "LONG": {"open": "BUY", "close": "SELL"},
        "SHORT": {"open": "SELL", "close": "BUY"}
    }

    MARKET_ORDER = "MARKET"
    STOP_MARKET_ORDER = "STOP_MARKET"
    TAKE_PROFIT_MARKET_ORDER = "TAKE_PROFIT_MARKET"
    RETRY_COUNT = 3

    config = ConfigParser()
    config.read("config.ini")

    __base_url = config['main']['base_url']
    __wss_url = config['main']['wss_url']
    futures_client = UMFutures(key=__API_KEY, secret=__API_SECRET, base_url=__base_url)
    futures_client_ws = futures_ws(stream_url=__wss_url)

    db = DatabaseConnector()
    __redis_client = RedisClient()

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.logger = general_logger.get_logger("Binance Connector", self.ticker)
        self.listen_key = self.__get_listen_key()
        self.__update_listen_key(self.listen_key, interval=35 * 60)
        self.user_data_stream()
        self.__recv_window = 59999
        self.__change_margin_type()
        self.leverage = self.__set_leverage()
        self.open_position = self.__redis_client.check_open_position(self.ticker)
        self.trading_pairs = {}
        self.get_pairs_info()

    def open_position(self, position: str, quantity: Decimal, take_profit: Decimal, stop_loss: Decimal) -> None:
        """
        Opens a position on the exchange and places Stop-loss and Take-profit orders.
        :param position: LONG or SHORT
        :param quantity: The quantity of the asset to be bought or sold
        :param take_profit: Percentage of price change at which the bot will close the position with a profit
        :param stop_loss: Percentage of price change at which the bot will close the position and record losses
        """
        open_result = self.place_order(self.__orders_side[position]['open'], quantity, self.MARKET_ORDER)
        filled_entry_result, status = self.__order_handler(open_result)
        if status:
            self.open_position = True
            entry_order = Order(self.ticker, filled_entry_result['orderId'], self.MARKET_ORDER,
                                position, filled_entry_result['avgPrice'], filled_entry_result['status'],
                                filled_entry_result['updateTime'])
        else:
            self.logger.warning("Position haven't been opened.")
            return None

        if position == "LONG":
            take_profit_price = Decimal(Decimal(entry_order.price) * (1 + (take_profit / 100)))
            stop_loss_price = Decimal(Decimal(entry_order.price) * (1 - (stop_loss / 100)))
        else:
            take_profit_price = Decimal(Decimal(entry_order.price) * (1 - (take_profit / 100)))
            stop_loss_price = Decimal(Decimal(entry_order.price) * (1 + (stop_loss / 100)))

        filtered_take_profit_price = self.__price_filter(take_profit_price)
        filtered_stop_loss_price = self.__price_filter(stop_loss_price)

        tp_result = self.place_order(self.__orders_side[position]['close'], order_type=self.TAKE_PROFIT_MARKET_ORDER)
        sl_result = self.place_order(self.__orders_side[position]['close'], order_type=self.STOP_MARKET_ORDER)
        tp_order = Order(self.ticker, tp_result['orderId'], self.TAKE_PROFIT_MARKET_ORDER,
                         position, filtered_take_profit_price, tp_result['status'], tp_result['updateTime'])
        sl_order = Order(self.ticker, sl_result['orderId'], self.STOP_MARKET_ORDER,
                         position, filtered_stop_loss_price, sl_result['status'], sl_result['updateTime'])
        try:
            self.__save_orders_in_cache(entry_order, tp_order, sl_order)
            self.logger.info("Info about orders has been saved in Redis")
        except Exception as redis_exception:
            self.logger.error("Info about orders hasn't been saved in Redis.", redis_exception)

    def close_position(self, quantity: Decimal) -> None:
        """
        Closes the position partially or completely
        :param quantity: The amount of asset for which the position should be closed
        """
        self.logger.info("Closing position")
        open_position = self.__redis_client.get_order(self.ticker)
        entry_order = Order(self.ticker, open_position['entry_order']['order_id'], self.MARKET_ORDER,
                            open_position['entry_order']['position'], open_position['entry_order']['price'],
                            open_position['entry_order']['status'], open_position['entry_order']['order_time'])
        self.cancel_orders()
        close_result = self.place_order(self.__orders_side[entry_order.position]['close'],
                                        order_type=self.MARKET_ORDER, amount=quantity)
        filled_close_order, close_status = self.__order_handler(close_result)
        if close_status:
            close_order = Order(self.ticker, filled_close_order['orderId'], self.MARKET_ORDER, entry_order.position,
                                filled_close_order['avgPrice'], filled_close_order['status'],
                                filled_close_order['updateTime'])
            self.insert_trade(entry_order, close_order)
            self.open_position = False
            try:
                self.__redis_client.delete_key(self.ticker)
                self.logger.error(f"Deleting key {self.ticker} from Redis. Status: SUCCESS")
            except Exception as redis_exception:
                self.logger.error(f"Deleting key {self.ticker} from Redis. Status: FAILED", redis_exception)
        else:
            self.logger.warning("Position isn't closed.")

    def insert_trade(self, open_order: Order, close_order: Order) -> None:
        """
        Inserts position information into the database
        :param open_order: Position opening order
        :param close_order: Position closing order
        """
        open_trade = self.get_trade(open_order.order_id)
        close_trade = self.get_trade(close_order.order_id)
        try:
            general_fee_amount = Decimal(open_trade[0]['commission']) + Decimal(close_trade[0]['commission'])
            profit = Decimal(close_trade[0]['realizedPnl']) - general_fee_amount
        except IndexError:
            self.logger.info("Some error during handling trades")
            general_fee_amount = 0
            profit = 0
        if close_order.close_reason is not None:
            reason = close_order.close_reason
        else:
            reason = "Change MACD"
        self.__insert_into_db(open_order, close_order, general_fee_amount, profit, reason)

    def __save_orders_in_cache(self, open_order: Order, tp_order: Order, sl_order: Order) -> None:
        """
        Saves open positions to temporary storage (cache)
        :param open_order: Position opening order
        :param tp_order: Take-profit order
        :param sl_order: Stop-loss order
        """
        self.logger.info("Preparation data for saving in Redis")
        entry_cache = {
            "order_id": open_order.order_id,
            "price": str(open_order.price),
            "position": open_order.position,
            "status": open_order.status,
            "order_time": open_order.order_time
        }
        tp_cache = {
            "order_id": tp_order.order_id,
            "price": str(tp_order.price),
            "position": tp_order.position,
            "status": tp_order.status,
            "order_time": open_order.order_time
        }
        sl_cache = {
            "order_id": sl_order.order_id,
            "price": str(sl_order.price),
            "position": sl_order.position,
            "status": sl_order.status,
            "order_time": open_order.order_time
        }
        try:
            self.__redis_client.insert_into_db(self.ticker, {"entry_order": entry_cache,
                                                             "tp_order": tp_cache,
                                                             "sl_order": sl_cache})
        except Exception as redis_exception:
            self.logger.warning("Can't save data about orders in Redis. Status: FAILED", redis_exception)

    def __order_handler(self, order: dict) -> tuple[dict, True] | False:
        counter = 0
        while counter < 5:
            counter += 1
            self.logger.info(f"Get order status. Try #{counter}")
            time.sleep(counter)
            try:
                filled_order = self.get_order_status(order['orderId'])
                if filled_order['status'] == "FILLED":
                    self.logger.info("Status: SUCCESS")
                    return filled_order, True
            except Exception as binance_exception:
                self.logger.error("Some error during request order status", binance_exception)
        return False

    def __insert_into_db(self, open_order: Order, close_order: Order, fee: Decimal,
                         profit: Decimal, reason: str = "Change MACD") -> None:
        """

        :param open_order: Position opening order
        :param close_order: Position closing order
        :param fee: Amount of USDT spent on commissions
        :param profit: The amount of USDT that was actually earned (positive value) or spent (negative value)
        :param reason: Reason for closing the position
        """
        open_position = self.__redis_client.get_order(self.ticker)
        data = {
            "ticker": self.ticker,
            "open_order_id": open_order.order_id,
            "position": open_order.position,
            "open_price": open_order.price,
            "take_profit_price": open_position['tp_order']['price'],
            "stop_loss_price": open_position['sl_order']['price'],
            "close_order_id": close_order.order_id,
            "close_price": close_order.price,
            "close_reason": reason,
            "fee_amount": fee,
            "profit": profit,
            "open_position_time": datetime.datetime.fromtimestamp(open_order.order_time / 1000)
        }
        try:
            self.db.insert_data(data)
        except Exception as sql_exception:
            self.logger.error("Error during insert into MySQL", sql_exception)
        self.logger.info(data)

    def __set_leverage(self) -> str:
        """
        Sets the leverage that is specified in the configuration file
        :return: Leverage value that has been established
        """
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "leverage": 1,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }
                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.post(f"{self.__base_url}/fapi/v1/leverage", data=params,
                                         headers={"X-MBX-APIKEY": self.__API_KEY, "User-Agent": "futures/1.0"})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            raise ConnectionError(response.text)
        else:
            response = response.json()
            return response['leverage']

    def __change_margin_type(self) -> bool | None:
        """
        Checks and, if necessary, changes the type of margin used
        :return: Returns True if the margin type has been changed or None if not
        """
        margin_type = self.__check_margin_type()
        if margin_type.upper() != "ISOLATED":
            counter = 0
            response = None
            while counter < self.RETRY_COUNT:
                try:
                    params = {
                        "symbol": self.ticker,
                        "marginType": "ISOLATED",
                        "timestamp": int(time.time() * 1000),
                        "recvWindow": self.__recv_window
                    }
                    string_for_sign = urlencode(params)
                    params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                                   hashlib.sha256).hexdigest()
                    response = requests.post(f"{self.__base_url}/fapi/v1/marginType", data=params,
                                             headers={"X-MBX-APIKEY": self.__API_KEY, "User-Agent": "futures/1.0"})
                    break
                except BaseException:
                    counter += 1
            if response is None:
                raise ConnectionError("Connection error to Binance")

            if response.status_code != 200:
                raise ConnectionError(response.text)
            else:
                return True

    def __check_margin_type(self) -> str | None:
        """
        Checking the current margin type
        :return: Returns the current margin type or None if the request failed
        """
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }
                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.get(f"{self.__base_url}/fapi/v2/positionRisk?{urlencode(params)}",
                                        headers={"X-MBX-APIKEY": self.__API_KEY})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            raise ConnectionError(response.text)
        else:
            response = response.json()
            return response[0]['marginType']

    def get_pairs_info(self) -> None:
        """
        Creates a dictionary of existing tickers and information about them on the exchange
        """
        result = requests.get(url=f"{self.__base_url}/fapi/v1/exchangeInfo").json()["symbols"]
        trading_pairs = {}
        for ticker in result:
            if ticker["status"] != "BREAK":
                trading_pairs[ticker['symbol']] = {
                    'base_asset': ticker["baseAsset"],
                    'quote_asset': ticker["quoteAsset"],
                    'margin_asset': ticker["marginAsset"],
                    'trigger_protect': ticker["triggerProtect"]
                }
                for symbol_filter in ticker['filters']:
                    filters_names = list(symbol_filter.keys())
                    filters_values = list(symbol_filter.values())
                    filter_type_index = keys.index("filterType")
                    filter_name = filters_values.pop(filter_type_index)
                    filters_names.pop(filter_type_index)
                    updating = {filter_name.lower(): dict(zip(filters_names, filters_values))}
                    trading_pairs[ticker['symbol']].update(updating)
        self.trading_pairs = trading_pairs

    def __price_filter(self, price: Decimal) -> Decimal:
        """
        Processes the price according to the tickSize of a specific ticker
        :param price: Calculated price
        :return: Price after processing, which corresponds to the exchange's filters
        """
        price_filter = self.trading_pairs[self.ticker]['price_filter']
        filtered_price = price.quantize(Decimal(price_filter['tickSize'].rstrip("0")))
        return filtered_price

    def place_order(self, route: str, amount: Decimal | None = None, order_type: str = MARKET_ORDER) -> dict:
        """
        Places an order on the exchange with the specified parameters
        :param route: BUY or SELL
        :param amount: The quantity of the asset to be bought or sold
        :param order_type: MARKET_ORDER or STOP_MARKET_ORDER or TAKE_PROFIT_MARKET_ORDER
        :return: Order's info
        """
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "side": route,
                    "type": order_type,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }
                if amount is not None:
                    params['quantity'] = float(Decimal(amount))

                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.post(f"{self.__base_url}/fapi/v1/order", data=params,
                                         headers={"X-MBX-APIKEY": self.__API_KEY})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            self.logger.warning(f"Binance return status code {response.status_code}")
            self.logger.warning(response.text)
            raise ConnectionError(response.json()["msg"])
        else:
            response = response.json()
            self.logger.info("Order has been created")
            self.logger.info(response)
            return response

    def get_order_status(self, order_id: str) -> dict:
        """
        Request for order status
        :param order_id: Order's ID
        :return: Order's info
        """
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "orderId": order_id,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }
                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.get(f"{self.__base_url}/fapi/v1/order?{urlencode(params)}",
                                        headers={"X-MBX-APIKEY": self.__API_KEY})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            self.logger.warning(f"Binance return status code {response.status_code}")
            self.logger.warning(response.text)
            raise ConnectionError(response.text)
        else:
            response = response.json()
            self.logger.info("Order status was get successfully.")
            return response

    def cancel_orders(self) -> bool | None:
        """
        Cancels the placed order
        :return: True if the order was canceled or Non, if an error occurred
        """
        self.logger.info(f"Trying cancel open orders for ticker {self.ticker}")
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }

                logging.debug(str(params))
                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.delete(f"{self.__base_url}/fapi/v1/allOpenOrders", data=params,
                                           headers={"X-MBX-APIKEY": self.__API_KEY, "User-Agent": "futures/1.0"})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            raise ConnectionError(response.text)
        else:
            self.logger.info(response.json())
            return True

    def get_trade(self, order_id: str) -> dict:
        """
        Request for trade status
        :param order_id: Order's ID
        :return: Trades info
        """
        self.logger.info(f"Trying get trade info for ticker {self.ticker}")
        counter = 0
        response = None
        while counter < self.RETRY_COUNT:
            try:
                params = {
                    "symbol": self.ticker,
                    "orderId": order_id,
                    "timestamp": int(time.time() * 1000),
                    "recvWindow": self.__recv_window
                }
                string_for_sign = urlencode(params)
                params['signature'] = hmac.new(bytes(self.__API_SECRET, "UTF-8"), bytes(string_for_sign, "UTF-8"),
                                               hashlib.sha256).hexdigest()
                response = requests.get(f"{self.__base_url}/fapi/v1/userTrades?{urlencode(params)}",
                                        headers={"X-MBX-APIKEY": self.__API_KEY})
                break
            except BaseException:
                counter += 1
        if response is None:
            raise ConnectionError("Connection error to Binance")

        if response.status_code != 200:
            self.logger.warning(f"Binance return status code {response.status_code}")
            self.logger.warning(response.text)
            raise ConnectionError(response.json()["msg"])
        else:
            trade = response.json()
            self.logger.info("Order status was get successfully.")
            return trade

    def __order_update(self, message: dict) -> None:
        """
        Handler of messages about orders sent via private WebSocket
        :param message: Message containing information about the order
        """
        open_orders = self.__redis_client.get_order(self.ticker)
        entry_order = Order(self.ticker, open_orders['entry_order']['order_id'], self.MARKET_ORDER,
                            open_orders['entry_order']['position'], open_orders['entry_order']['price'],
                            open_orders['entry_order']['status'], open_orders['entry_order']['order_time'])
        if message['o']['i'] == open_orders["tp_order"]["order_id"]:
            if message['o']['X'] == "FILLED":
                self.cancel_orders()
                self.logger.info("Close by Take profit")
                close_order = Order(self.ticker, open_orders["tp_order"]["order_id"], self.TAKE_PROFIT_MARKET_ORDER,
                                    open_orders["tp_order"]["position"], Decimal(message['o']['ap']), "FILLED",
                                    message['o']['T'], "TP")
                self.insert_trade(entry_order, close_order)
        elif message['o']['i'] == open_orders["sl_order"]["order_id"]:
            if message['o']['X'] == "FILLED":
                self.cancel_orders()
                self.logger.info("Close by Stop loss")
                close_order = Order(self.ticker, open_orders["sl_order"]["order_id"], self.STOP_MARKET_ORDER,
                                    open_orders["sl_order"]["position"], Decimal(message['o']['ap']), "FILLED",
                                    message['o']['T'], "SL")
                self.insert_trade(entry_order, close_order)

    def __profile_info_stream_handler(self, message: dict):
        """
        Callback function for WebSockets stream
        :param message: Message from the exchange
        """
        if 'e' in message.keys():
            if message['e'] == 'ORDER_TRADE_UPDATE':
                if message['o']['s'] == self.ticker:
                    self.logger.info(message)
                    if self.open_position:
                        self.__order_update(message)
            if message['e'] == 'ACCOUNT_UPDATE':
                self.logger.info(message)

    def user_data_stream(self):
        self.futures_client_ws.start()
        self.logger.info("User Data Stream have been started")
        self.futures_client_ws.user_data(
            listen_key=self.listen_key,
            id=1,
            callback=self.__profile_info_stream_handler,
        )

    def __get_listen_key(self):
        return self.futures_client.new_listen_key()['listenKey']

    def __update_listen_key(self, listen_key, interval):
        stopped = Event()

        def loop():
            while not stopped.wait(interval):
                self.futures_client.renew_listen_key(listenKey=listen_key)

        Thread(target=loop).start()
        return stopped.set
