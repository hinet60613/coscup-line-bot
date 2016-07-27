# -*- coding: utf-8 -*-

from flask import Flask, request
from flask import Response

import coscupbot
import logging
import os
import sys

app = Flask(__name__)

credentials = {
    'channel_id': os.getenv("CHANNEL_ID"),
    'channel_secret': os.getenv("CHANNEL_SECRET"),
    'channel_mid': os.getenv("CHANNEL_MID"),
}

bot = None


@app.route('/')
def hello_world():
    return 'Hello, Coscup bot.'


@app.route('/callback', methods=['POST'])
def line_call_back():
    bot.process_new_event(request.get_data().decode("utf-8"))
    return "OK"


@app.route('/edison')
def edison():
    ret = bot.get_edison_request()
    if ret is None:
        ret = '{}'
    resp = Response(response=ret,
                    status=200,
                    mimetype="application/json")

    return resp


def init_logger():
    """
    Init logger. Default use INFO level. If 'DEBUG' is '1' in env use DEBUG level.
    :return:
    """
    root = logging.getLogger()
    ch = logging.StreamHandler(sys.stdout)
    level = logging.INFO
    if os.getenv("DEBUG") == '1':
        level = logging.DEBUG
    root.setLevel(level)
    ch.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s: - %(funcName)s(): - %(lineno)d: - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def get_wit_tokens():
    ret = {}
    if 'WIT_ZHTW_TOKEN' in os.environ:
        ret['zh_TW'] = os.environ['WIT_ZHTW_TOKEN']
    return ret


if __name__ == '__main__':
    init_logger()
    logging.info('Init bot use credentials. %s' % credentials)
    redis_url = os.getenv('REDIS', 'redis://localhost:6379')
    bot = coscupbot.CoscupBot(credentials, get_wit_tokens(), redis_url)
    ip = os.getenv("IP")
    port = os.getenv("PORT")
    app.run(host=ip, port=port)
