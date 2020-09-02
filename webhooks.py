#!/usr/bin/env python
import os

SERVER = os.environ.get('BOTTLE_SERVER', 'wsgiref')

if SERVER == 'gevent':
    from gevent import monkey
    monkey.patch_all()

import sys
import time
import hmac
import hashlib
import logging
import requests
from functools import wraps
from subprocess import Popen, PIPE
from bottle import HTTPResponse, request, route, run

LUDOLPH_URL = 'http://zabbix.erigones.com:8922/room'

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


def _execute(cmd_id, cmd, stdin=None):
    """Run command"""
    logger.info('[%s] Running %s', cmd_id, ' '.join(cmd))
    start = time.time()
    exc = Popen(cmd, stdin=PIPE, close_fds=True)
    exc.communicate(input=stdin)
    rc = exc.returncode
    duration = time.time() - start

    if rc == 0:
        logger.info('[%s] Command finished OK in %s seconds', cmd_id, duration)
        return True
    else:
        logger.warn('[%s] Command finished with non-zero exit code (%s) in %s seconds', cmd_id, rc, duration)
        return False


def _ludolph_shout(msg):
    """Post message to MUC room via ludolph"""
    logger.info('Sending message to ludolph via %s: "%s"', LUDOLPH_URL, msg)
    return requests.post(LUDOLPH_URL, data={'msg': msg}, timeout=10)


def _verify_github_signature(secret):
    """Verify GitHub signature"""
    payload = request.body.read()
    signature = request.headers.get('X-Hub-Signature', '')
    mac = hmac.new(secret, msg=payload, digestmod=hashlib.sha1)

    return hmac.compare_digest('sha1=' + mac.hexdigest(), signature)


def _verify_gitlab_signature(secret):
    """Verify GitLab token"""
    return secret == request.headers.get('X-Gitlab-Token', None)


def verify_signature(secret, verify_fun=_verify_github_signature):
    """verify webhook signature decorator"""
    def verify_signature_decorator(fun):
        @wraps(fun)
        def wrap(*args, **kwargs):
            if not secret or verify_fun(secret):
                return fun(*args, **kwargs)
            else:
                return HTTPResponse('invalid signature', status=403)

        return wrap
    return verify_signature_decorator


def _identify_commit_github(data):
    try:
        head_commit = data['head_commit']['id']
        cmd_id = head_commit[:8]
    except (TypeError, KeyError):
        head_commit = ''
        cmd_id = str(time.time())

    return cmd_id, head_commit


def _identify_commit_gitlab(data):
    try:
        head_commit = data['checkout_sha']
        cmd_id = head_commit[:8]
    except (TypeError, KeyError):
        head_commit = ''
        cmd_id = str(time.time())

    return cmd_id, head_commit


def _is_file_in_commits(commits, search_string):
    def search_commit(commit_lines):
        return any(search_string in line for line in commit_lines)

    return any(
        search_commit(commit.get('added', [])) or
        search_commit(commit.get('removed', [])) or
        search_commit(commit.get('modified', []))
        for commit in commits
    )


def _is_branch(data, target_branch):
    try:
        branch = data['ref'].split('/')[-1]
    except (TypeError, KeyError):
        return False
    else:
        return branch == target_branch


def verify_branch(target_branch):
    """Check if we are talking about a specific branch"""
    def verify_branch_decorator(fun):
        @wraps(fun)
        def wrap(*args, **kwargs):
            if _is_branch(request.json, target_branch):
                return fun(*args, **kwargs)
            else:
                return HTTPResponse('invalid branch')

        return wrap
    return verify_branch_decorator


@route('/webhooks/docs/user-guide/push', method=('POST',))
@verify_signature('VwfwRuwCrMsnHTyuIGbrc8XdRql')
@verify_branch('master')
def docs_user_guide_push():
    data = request.json
    cmd_id, head_commit = _identify_commit_github(data)

    if not _is_file_in_commits(data.get('commits', ()), 'user-guide/'):
        return 'ok (nothing to do)'

    if _execute(cmd_id, ['sudo', '-u', 'docs', '/home/docs/bin/update-user-guide.sh']):
        _ludolph_shout('https://docs.danubecloud.org/user-guide has been successfully updated on web02.erigones.com')
        return 'ok'
    else:
        _ludolph_shout('Failed to update https://docs.danubecloud.org/user-guide on web02.erigones.com')
        return '!!'


@route('/webhooks/docs/api-reference/push', method=('POST',))
@verify_signature('VwfwRuwCrMsnHTyuIGbrc8XdRql')
@verify_branch('master')
def docs_api_reference_push():
    data = request.json
    cmd_id, head_commit = _identify_commit_github(data)
    commits = data.get('commits', ())

    #if not (_is_file_in_commits(commits, 'api/') or _is_file_in_commits(commits, 'doc/api/')):
    #    return 'ok (nothing to do)'

    if _execute(cmd_id, ['sudo', '-u', 'docs', '/home/docs/bin/update-api-reference.sh']):
        _ludolph_shout('https://docs.danubecloud.org/api-reference has been successfully updated on web02.erigones.com')
        return 'ok'
    else:
        _ludolph_shout('Failed to update https://docs.danubecloud.org/api-reference on web02.erigones.com')
        return '!!'


@route('/webhooks/web/danubecloud.org/push', method=('POST',))
@verify_signature('zLVEnQTdv46PnR5IzaqdJw0mrzHUCKD', verify_fun=_verify_gitlab_signature)
@verify_branch('master')
def web_danubecloud_org_push():
    data = request.json
    cmd_id, head_commit = _identify_commit_gitlab(data)

    if _execute(cmd_id, ['sudo', '-u', 'root', '/root/bin/update-danubecloud-org.sh']):
        _ludolph_shout('https://danubecloud.org has been successfully updated on web02.erigones.com')
        return 'ok'
    else:
        _ludolph_shout('Failed to update https://danubecloud.org on web02.erigones.com')
        return '!!'


run(host=os.environ.get('BOTTLE_HOST', 'localhost'), port=os.environ.get('BOTTLE_PORT', 8080), server=SERVER)
