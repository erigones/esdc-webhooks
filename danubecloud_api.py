#!/usr/bin/env python
import os
import sys
import logging
from datetime import datetime

from bottle import route, run, request, response, json_dumps, Bottle
from github3 import login
from functools import wraps

SERVER = os.environ.get('BOTTLE_SERVER', 'wsgiref')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME', None)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', None)

if not GITHUB_TOKEN or not GITHUB_USERNAME:
    raise SystemError('GITHUB_TOKEN or GITHUB_USERNAME are not configured')

if SERVER == 'gevent':
    from gevent import monkey
    monkey.patch_all()

# logging to console
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# logging to file
file_logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('request.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(msg)s'))
file_logger.addHandler(file_handler)

# logger.addHandler(file_handler)

GITHUB = login(username=GITHUB_USERNAME, token=GITHUB_TOKEN)
ESDC_REPO = GITHUB.repository('erigones', 'esdc-ce')


def log_to_logger(fn):
    """
    Wrap a Bottle request so that a log line is emitted after it's handled.
    (This decorator can be extended to take the desired logger as a param.)
    """

    @wraps(fn)
    def _log_to_logger(*args, **kwargs):
        request_time = datetime.now()
        actual_response = fn(*args, **kwargs)
        # modify this to log exactly what you need:
        logger.info('%s %s %s %s %s' % (request_time,
                                        request.remote_addr,
                                        request.query_string,
                                        request.get_header('Referer'),
                                        response.status))
        return actual_response

    return _log_to_logger


app = Bottle()
app.install(log_to_logger)


def _json_response(data):
    response.content_type = 'application/json'

    return json_dumps(data)


def _get_tags():
    return [tag.as_dict() for tag in ESDC_REPO.tags()]


@app.route('/api/releases', method=('GET',))
def releases():
    return _json_response(_get_tags())


@app.route('/api/tags', method=('GET',))
def tags():
    return _json_response(_get_tags())


app.run(host=os.environ.get('BOTTLE_HOST', 'localhost'), port=os.environ.get('BOTTLE_PORT', 3333), server=SERVER)
