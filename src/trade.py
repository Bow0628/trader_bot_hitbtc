import json
import math
from scipy.signal import argrelextrema
from scipy import stats
import numpy as np
import getopt
import ExchangeClient

from time import gmtime, strftime, sleep
from sys import argv, exit

""" 
The main trading executor class. It tries to buy low and sell higher, leveraging variations on BTC/USD.
The class calculates maxima and minima to determine if the current BTC price is below/above historical
maxima/minima. It also records previous buys and sells to profit from price variations. 
"""
class TradingExecutor(object):
    def __init__(self, client, the_symbol, min_trading_balance, ten_to_the_power, max_usd_to_spend_each_buy):
        self.client = client
        self.the_symbol = the_symbol
        self.min_trading_balance = min_trading_balance
        self.ten_to_the_power = ten_to_the_power
        self.max_usd_to_spend_each_buy = max_usd_to_spend_each_buy

    @staticmethod
    def is_big_drop(minn, last_value, ratio, percent):
        print('min val to buy:' + str(TradingExecutor.round_to_currency(minn)) + ', last val:' + str(
            last_value) + ', ratio: ' + str(float(int(ratio * 100000)) / 100000) + ', percent:' + str(percent))
        if ratio > percent:
            return True
        else:
            return False

    @staticmethod
    def round_to_currency(amount):
        return float(int(amount * 100)) / 100

    def get_latest_value(self):
        ticker = self.client.get_ticker(self.the_symbol)
        last_value = float(ticker['last'])
        return last_value

    def wait_order_fulfilled(self, client, client_order_id):
        print('Waiting for order fulfillment. Ill sleep. client_order_id: ' + client_order_id)
        errors = 0
        while True:
            print('.', end='')
            try:
                order = client.get_order(client_order_id, 40000)
                if order.get('status'):
                    the_status = order['status']
                    if the_status == 'filled':
                        print('Order fulfilled. Moving on.')
                        return True
                    if the_status == 'canceled' or the_status == 'expired' or the_status == 'suspended':
                        print('Warning: exceptional order status.' + the_status + ', clientOrderId:' + client_order_id)
                        return False
                elif order.get('error'):
                    print('**Error. ' + str(order['error']))
                    errors = errors + 1
            except ValueError:
                print('Decoding JSON has failed')
                errors = errors + 1
            if errors > 20:
                print('Too many errors. Maybe the order was fulfilled. Moving on.')
                return
            print('[get_latest_value] last value: ' + str(self.get_latest_value()))
            sleep(20)

    """
    Retrieve the median of local minima. Check if the last price is a significant price drop.
    If so, place a buy order.
    """

    def buy_good_value(self, drop_ratio, buy_lower_ratio):
        loop = 0
        minn = 1
        while True:
            if loop > 10 or loop <= 0:
                many_candles = self.client.get_many_candles(self.the_symbol)
                local_minima = argrelextrema(np.array(many_candles), np.less, order=5)
                loop = 0
                for x in local_minima:
                    selected_minima = [many_candles[i] for i in x]

                selected_minima = sorted(selected_minima)[1:]

                print('[buy_good_value] selected_minima (I): ' + str(selected_minima))
                selected_minima = sorted(selected_minima)[0:int(len(selected_minima) / 2)]
                print('[buy_good_value] selected_minima (II): ' + str(selected_minima))
                minn = stats.hmean(selected_minima)
            loop = loop + 1

            last_value = self.get_latest_value()

            ratio = 1 - (last_value / minn)
            is_big_drop = self.is_big_drop(minn, last_value, ratio, drop_ratio)
            if is_big_drop:
                print('**The price is low.')
                my_balance = self.client.get_trading_balance_usd()
                print('my balance: USD$ ' + str(my_balance))
                if my_balance > self.min_trading_balance:
                    amount_to_buy_in_usd = min(TradingExecutor.round_to_currency(my_balance / 10),
                                               self.max_usd_to_spend_each_buy)
                    amount_of_coin_to_buy = max(amount_to_buy_in_usd / last_value, 1 / self.ten_to_the_power)
                    print('amount_of_coin_to_buy: ' + str(amount_of_coin_to_buy))
                    rounded_amount_of_coin_to_buy = float(int(amount_of_coin_to_buy * self.ten_to_the_power)) / \
                                                    self.ten_to_the_power
                    amount_spent_in_usd = TradingExecutor.round_to_currency(rounded_amount_of_coin_to_buy * last_value)
                    print('rounded_amount_of_coin_to_buy: ' + str(rounded_amount_of_coin_to_buy))
                    print('Ill BUY ' + str(rounded_amount_of_coin_to_buy) + ' ' + self.the_symbol + ' at ' +
                          str(last_value) + ', spending US$ ' + str(amount_spent_in_usd))
                    buy_value = TradingExecutor.round_to_currency(last_value - (last_value * buy_lower_ratio))
                    buy_amount = rounded_amount_of_coin_to_buy
                    order = self.client.new_order_alt(self.the_symbol, 'buy', rounded_amount_of_coin_to_buy, buy_value)
                    if order.get('error'):
                        print('Some error happened when placing the order.')
                        sleep(5)
                        return {'order': order, 'someError': True}
                    return {'buy_value': buy_value, 'buy_amount': buy_amount,
                            'rounded_amount_of_coins_bought': rounded_amount_of_coin_to_buy, 'order': order}
            sleep(10)

    """
    Retrieve the median of the local maxima. If the last price is higher, considering a minimum profit, 
    place a new sell order.
    """
    def sell_good_value(self, buy_data, min_profit, trading_fee):

        many_candles = self.client.get_many_candles(self.the_symbol)
        local_maxima = argrelextrema(np.array(many_candles), np.greater, order=5)
        print('[sell_good_value] local_maxima:' + str(local_maxima))
        loop = 0
        for x in local_maxima:
            selected_maxima = [many_candles[i] for i in x]

        selected_maxima = sorted(selected_maxima)[1:]
        selected_maxima = sorted(selected_maxima)[int(len(selected_maxima) / 2):]
        print('[sell_good_value] selected_maxima (II): ' + str(selected_maxima))
        avg_maxima = np.mean(selected_maxima)

        min_sell_value = buy_data['buy_value'] * (1 + min_profit)
        print('Last bought value: ' + str(buy_data['buy_value']) + ', min_sell_value: ' + str(min_sell_value))

        min_sell_value = max(avg_maxima, min_sell_value)

        print('avg_maxima: ' + str(avg_maxima))

        print('min_sell_value: ' + str(min_sell_value) + ', bought value: ' + str(buy_data['buy_value']))
        profit_usd = ((min_sell_value / (1 + trading_fee)) - buy_data['buy_value']) * buy_data['buy_amount']
        profit_usd = TradingExecutor.round_to_currency(profit_usd)
        print(' Calculated profit: ' + str(profit_usd))
        sell_value = min_sell_value
        order = self.client.new_order_alt(self.the_symbol, 'sell', buy_data['buy_amount'], sell_value)
        print('[sell_good_value] order:' + str(order))
        if order.get('error'):
            print('[sell_good_value] Some error happened when placing the order.')
            sleep(5)
            return {'order': order, 'someError': True}
        elif order.get('order') and order['order'].get('status') and (order['order']['status'] == 'new'):
            print('** [sell_good_value] Order placed. Moving on.')
        print('** [sell_good_value] Order placed. Moving on.')
        return {'order': order, 'sell_value': sell_value}


def main(_argv):
    args_ok = False
    opts = ()
    try:
        opts, _ = getopt.getopt(_argv, "p:s:")
        args_ok = True
    except getopt.GetoptError:
        pass

    if list(filter(lambda x: x[0] == '-p', opts)).__len__() == 0 or \
            list(filter(lambda x: x[0] == '-s', opts)).__len__() == 0:
        args_ok = False

    if not args_ok:
        print('Usage: trade.py -s <public_key> -s <secret>')
        exit(2)
    public_key = list(filter(lambda x: x[0] == '-p', opts))[0][1]
    secret = list(filter(lambda x: x[0] == '-s', opts))[0][1]
    the_symbol = 'BTCUSD'

    with open('config.json') as config_file:
        config_data = json.load(config_file)

    min_trading_balance = config_data['min_trading_balance']

    max_usd_to_spend_each_buy = config_data['max_usd_to_spend_each_buy']
    trading_fee = config_data['trading_fee']
    min_profit = config_data['min_profit']
    drop_ratio = config_data['drop_ratio']
    buy_lower_ratio = config_data['buy_lower_ratio']

    client = ExchangeClient.ExchangeClient("https://api.hitbtc.com", public_key, secret)

    while True:
        print('Starting program.' + strftime("%Y-%m-%d %H:%M:%S", gmtime()))

        symbol = client.get_symbol(the_symbol)
        print('Symbol: ' + str(symbol))
        quantity_increment = float(symbol['quantityIncrement'])
        log_quantity_increment_int = int(math.log10(quantity_increment))
        ten_to_the_power = int(math.pow(10, log_quantity_increment_int * -1))
        print('quantity_increment_int: ' + str(log_quantity_increment_int) + ', ten_to_the_power:' +
              str(ten_to_the_power))

        usd_balance = client.get_trading_balance_usd()
        if usd_balance < min_trading_balance:
            raise ValueError('The current USD balance is too low to trade.', str(usd_balance))

        logic = TradingExecutor(client, the_symbol, min_trading_balance, ten_to_the_power, max_usd_to_spend_each_buy)

        buy_data = logic.buy_good_value(drop_ratio, buy_lower_ratio)
        print(buy_data)
        if buy_data.get('someError'):
            raise ValueError('Some error happening trying to place the BUY order.')
        logic.wait_order_fulfilled(client, buy_data['order']['clientOrderId'])
        sell_data = logic.sell_good_value(buy_data, min_profit, trading_fee)
        print(sell_data)
        if sell_data.get('someError'):
            raise ValueError('Some error happening trying to place the SELL order.')
        logic.wait_order_fulfilled(client, sell_data['order']['clientOrderId'])
        sleep(30)


if __name__ == "__main__":
    main(argv[1:])
