# -*- coding: utf-8 -*-

import logging
import logging.config
import os
from functools import wraps

from flask import Flask, request
from flask import Response, jsonify
from flask import render_template, send_from_directory

import coscupbot
from coscupbot import utils

app = Flask(__name__)

BOT_TYPE = os.getenv("BOT_TYPE")

credentials = \
    {
        'TRIAL':
            {
                'channel_id': os.getenv("CHANNEL_ID"),
                'channel_secret': os.getenv("CHANNEL_SECRET"),
                'channel_mid': os.getenv("CHANNEL_MID")
            },
        'BUSINESS':
            {
                'channel_secret': os.getenv("CHANNEL_SECRET"),
                'channel_token': os.getenv("CHANNEL_TOKEN")
            }
    }.get(BOT_TYPE)

sheet_credentials = {
    'credential_path': os.getenv('SHEET_CREDENTIAL_PATH'),
    'name': os.getenv('SHEET_NAME')
}

bot = None

PRODUCTION = '0'

ADMIN_ID = None
ADMIN_PWD = None


def init_logger():
    """
    Init logger. Default use INFO level. If 'DEBUG' is '1' in env use DEBUG level.
    :return:
    """
    logging.config.fileConfig("./logging.conf")
    root = logging.getLogger()
    level = logging.INFO
    if os.getenv("DEBUG") == '1':
        level = logging.DEBUG
    root.setLevel(level)


def get_wit_tokens():
    ret = {}
    if 'WIT_ZHTW_TOKEN' in os.environ:
        ret['zh-TW'] = os.environ['WIT_ZHTW_TOKEN']
    if 'WIT_ENUS_TOKEN' in os.environ:
        ret['en-US'] = os.environ['WIT_ENUS_TOKEN']
    return ret


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == ADMIN_ID and password == ADMIN_PWD


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


init_logger()
logging.info('Init bot use credentials. %s' % credentials)
logging.info('Init bot use sheet credentials. %s' % sheet_credentials)
redis_url = os.getenv('REDIS', 'redis://localhost:6379')
bot = coscupbot.CoscupBot(BOT_TYPE, credentials, sheet_credentials, get_wit_tokens(), redis_url)
ip = os.getenv("IP")
port = os.getenv("PORT")
PRODUCTION = os.getenv('PRODUCTION', 0)
ADMIN_ID = os.environ['ADMIN_ID']
ADMIN_PWD = os.environ['ADMIN_PWD']


def create_new_app():
    app = Flask(__name__)
    return app


app = create_new_app()


@app.route('/')
def hello_world():
    return 'Hello, Coscup bot.'


@app.route('/callback', methods=['POST'])
def line_call_back():
    try:
        if PRODUCTION == '1':
            if not bot.bot_api.client.validate_signature(request.headers.get('X-Line-Channelsignature'),
                                                     request.get_data().decode("utf-8")):
                return "NOT PASS"
        bot.process_new_event(request.get_data().decode("utf-8"))
    except Exception as ex:
        logging.error(ex)
    return "OK"


@app.route('/edison')
@requires_auth
def edison():
    ret_json = {}
    ret = bot.get_edison_request()
    if ret:
        ret_json = ret
    return jsonify(ret_json)


@app.route('/edisondone', methods=['POST'])
@requires_auth
def edison_done():
    data = request.get_data().decode("utf-8")
    bot.take_photo_done(data)
    return 'OK'


@app.route('/triggerrealtime')
@requires_auth
def trigger_broadcast_realtime():
    result = bot.broadcast_realtime_message()
    return str(result)


@app.route('/syncbackend')
@requires_auth
def sync_backend():
    '''
    Reget all data from google sheet.
    :return:
    '''
    if bot.sync_backend_data():
        return 'OK'
    return 'FAIL'

@app.route('/clearnumtakephoto/<mid>')
@requires_auth
def clear_num_of_photo(mid):
    bot.clear_take_photo_count(mid)
    return 'OK'

@app.route('/cleargrounddata/<mid>')
@requires_auth
def clear_ground_data(mid):
    bot.clear_ground_data(mid)
    return 'OK'

@app.route('/groundstatus/<mid>')
@requires_auth
def get_gorund_status(mid):
    return jsonify(bot.get_ground_game_status(mid))


@app.route('/groundcheckin/<sp_id>/<mid>')
@requires_auth
def manual_check_in(sp_id, mid):
    return jsonify(bot.ground_game_check_in(sp_id, mid))

@app.route('/status')
@requires_auth
def get_bot_status():
    return jsonify(bot.get_status())

@app.route('/isfriend/<mid>')
@requires_auth
def is_friend(mid):
    return jsonify(bot.is_bot_friend(mid))

@app.route('/disableedison')
@requires_auth
def disable_edison():
    bot.disable_take_photo()
    return "OK"


@app.route('/enableedison')
@requires_auth
def enable_edison():
    bot.enable_take_photo()
    return "OK"

@app.route('/sp/')
def sp_index():
    return jsonify(statue=True, message="Welcome, traveller! >_O")

@app.route('/sp/img/<path:path>')
def send_img(path):
    return send_from_directory('img', path)

@app.route('/sp/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/sp/<sp_id>')
def sp_with_id(sp_id):
    return render_template('index.html', sp_id=sp_id)

@app.route('/sp/<sp_id>/<mid>')
def sp_check_in(sp_id, mid):
    ret = bot.ground_game_check_in(sp_id, mid)
    if 'error' in ret:
        return render_template('check_in_failed.html', err_msg=ret['error'])
    else:
        left = len(ret['status'])-sum(ret['status'].values())
        for sp_key in coscupbot.utils.SponsorKeyDic:
            if sp_key is not coscupbot.utils.FINAL_SPONSOR:
                ret['status'][coscupbot.utils.SponsorKeyDic[sp_key]['booth']] = ret['status'][sp_key]
            ret['status'].pop(sp_key)
        if left is not 0:
            if sp_id is coscupbot.utils.FINAL_SPONSOR:
                return render_template('finished.html', check_in_data=ret)
            else:
                return render_template('check_in.html', check_in_data=ret, left=left, sp_key_dict=utils.SponsorKeyDic)
        else:
            return render_template('finished.html', check_in_data=ret)

@app.route('/sp/test')
def css_test():
    return render_template('test.html')

if __name__ == '__main__':
    app.run()
