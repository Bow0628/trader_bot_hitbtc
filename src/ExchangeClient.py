import time
import json

import requests

"""
  The ExchangeClient class wraps a number of Hitbtc API calls.
"""
class ExchangeClient(object):
    def __init__(self, url, public_key, secret):
        self.url = url + "/api/2"
        self.session = requests.session()
        self.session.auth = (public_key, secret)
        self.steps_in_past = 2

    def get_symbol(self, symbol_code):
        """Get symbol."""
        return self.session.get("%s/public/symbol/%s" % (self.url, symbol_code)).json()

    def get_orderbook(self, symbol_code):
        """Get orderbook. """
        return self.session.get("%s/public/orderbook/%s" % (self.url, symbol_code)).json()

    def get_address(self, currency_code):
        """Get address for deposit."""
        return self.session.get("%s/account/crypto/address/%s" % (self.url, currency_code)).json()

    def get_account_balance(self):
        """Get main balance."""
        return self.session.get("%s/account/balance" % self.url).json()

    def get_candles(self, symbol_code):
        """Get main balance."""
        return self.session.get("%s/public/candles/%s?period=M3" % (self.url, symbol_code)).json()

    def get_candles_alt(self, symbol_code, period):
        """Get main balance."""
        while True:
            try: 
                return self.session.get("%s/public/candles/%s?period=%s" % (self.url, symbol_code, period)).json()
            except ConnectionError:
                print('[get_candles_alt] ConnectionError')
                time.sleep(10)

    def get_ticker(self, symbol_code):
        """Get main balance."""
        while True:
            try: 
                return self.session.get("%s/public/ticker/%s" % (self.url, symbol_code)).json()
            except requests.exceptions.ConnectionError:
                print('[get_ticker] ConnectionError')
            except json.decoder.JSONDecodeError:
                print('[get_ticker] JSONDecodeError')
            time.sleep(10)

    def get_trading_balance(self):
        """Get trading balance."""
        return self.session.get("%s/trading/balance" % self.url).json()

    def get_trading_balance_usd(self):
        usd_balance = 0.0
        balances = self.get_trading_balance()
        for balance in balances:
            if balance['currency'] == 'USD':
                usd_balance = float(balance['available'])
        return usd_balance

    def transfer(self, currency_code, amount, to_exchange):
        return self.session.post("%s/account/transfer" % self.url, data={
                'currency': currency_code, 'amount': amount,
                'type': 'bankToExchange' if to_exchange else 'exchangeToBank'
            }).json()

    def new_order(self, client_order_id, symbol_code, side, quantity, price=None):
        """Place an order."""
        data = {'symbol': symbol_code, 'side': side, 'quantity': quantity}

        if price is not None:
            data['price'] = price

        return self.session.put("%s/order/%s" % (self.url, client_order_id), data=data).json()

    def new_order_alt(self, symbol_code, side, quantity, price=None):
        """Place an order."""
        data = {'symbol': symbol_code, 'side': side, 'quantity': quantity, 'timeInForce': 'GTC'}

        if price is not None:
            data['price'] = price

        return self.session.post("%s/order" % (self.url), data=data).json()

    def get_order(self, client_order_id, wait=None):
        """Get order info."""
        while True:
            try: 
                data = {'wait': wait} if wait is not None else {}
                return self.session.get("%s/order/%s" % (self.url, client_order_id), params=data).json()
            except requests.exceptions.ConnectionError:
                print('[get_order] ConnectionError')
            except json.decoder.JSONDecodeError:
                print('[get_order] JSONDecodeError')
            time.sleep(10)

    def cancel_order(self, client_order_id):
        """Cancel order."""
        return self.session.delete("%s/order/%s" % (self.url, client_order_id)).json()

    def withdraw(self, currency_code, amount, address, network_fee=None):
        """Withdraw."""
        data = {'currency': currency_code, 'amount': amount, 'address': address}

        if network_fee is not None:
            data['networkfee'] = network_fee

        return self.session.post("%s/account/crypto/withdraw" % self.url, data=data).json()

    def get_transaction(self, transaction_id):
        """Get transaction info."""
        return self.session.get("%s/account/transactions/%s" % (self.url, transaction_id)).json()

    def get_three_candles(self,symbol_code):
        data = self.get_candles_alt(symbol_code,'M1')
        thelen = len(data)
        return  [data[thelen-6*self.steps_in_past-1]['close'],data[thelen-4*self.steps_in_past-1]['close'],data[thelen-2*self.steps_in_past-1]['close'],data[thelen-self.steps_in_past-1]['close']]

    def get_many_candles(self,symbol_code):
        data = self.get_candles_alt(symbol_code,'M1')
        result = [float(i['close']) for i in data]
        return result

    def get_many_min_candles(self,symbol_code):
        data = self.get_many_candles(symbol_code)
        return sorted(data)[:4]

