import json

from redis import Redis


class RedisClient:
    def __init__(self):
        with open(".env", "r") as config_file:
            keys = config_file.readlines()
        self.REDIS_HOST = keys[1].split("=")[1].rstrip()
        self.REDIS_PORT = int(keys[2].split("=")[1].rstrip())
        self.REDIS_PASSWORD = keys[3].split("=")[1].rstrip()
        self.REDIS_DB = int(keys[4].split("=")[1].rstrip())
        self.redis_client = Redis(host=self.REDIS_HOST, port=self.REDIS_PORT,
                                  password=self.REDIS_PASSWORD, db=self.REDIS_DB)

    def insert_into_db(self, name, data):
        self.redis_client.set(name, json.dumps(data))

    def get_order(self, ticker):
        order = json.loads(self.redis_client.get(ticker))
        return order

    def delete_key(self, ticker):
        self.redis_client.delete(ticker)

    def check_open_position(self, ticker):
        orders = self.redis_client.get(ticker)
        if orders is not None:
            return True
        else:
            return False

    def update_info(self, ticker, data):
        exists_info = self.get_order(ticker)
        new_keys = data.keys()
        for key in new_keys:
            exists_info[key] = data[key]
        self.insert_into_db(ticker, exists_info)
