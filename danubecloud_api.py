#!/usr/bin/env python
import os

SERVER = os.environ.get('BOTTLE_SERVER', 'wsgiref')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME', None)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', None)

if not GITHUB_TOKEN or not GITHUB_USERNAME:
    raise SystemError('GITHUB_TOKEN or GITHUB_USERNAME are not configured')

if SERVER == 'gevent':
    from gevent import monkey
    monkey.patch_all()

import sys
import logging
from bottle import route, run, response, json_dumps
from github3 import login

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

GITHUB = login(username=GITHUB_USERNAME, token=GITHUB_TOKEN)
ESDC_REPO = GITHUB.repository('erigones', 'esdc-ce')


def _json_response(data):
    response.content_type = 'application/json'

    return json_dumps(data)


def _get_tags():
    return [tag.as_dict() for tag in ESDC_REPO.tags()]


@route('/api/releases', method=('GET',))
def releases():
    return _json_response(_get_tags())


@route('/api/tags', method=('GET',))
def tags():
    return _json_response(_get_tags())


run(host=os.environ.get('BOTTLE_HOST', 'localhost'), port=os.environ.get('BOTTLE_PORT', 3333), server=SERVER)
