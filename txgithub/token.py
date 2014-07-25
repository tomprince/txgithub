import os
import json
import base64

from twisted.web import client
from twisted.internet import utils

from txgithub.constants import HOSTED_BASE_URL

def createToken(username, password,
                note, note_url,
                scopes, baseURL=None):
    baseURL = baseURL or HOSTED_BASE_URL
    if baseURL[-1] != '/':
        baseURL += '/'

    raw = "%s:%s" % (username, password)
    encoded = base64.b64encode(raw).strip()
    headers = { 'Authorization' : 'Basic ' + encoded }

    postData = json.dumps(dict(
        note = note,
        note_url = note_url,
        scopes = scopes,
        ))
    d = client.getPage(
            url='%sauthorizations' % baseURL,
            method='POST',
            postdata=postData,
            headers=headers
            )
    @d.addCallback
    def extractToken(res):
        result = json.loads(res)
        return result['token']
    return d


def getToken():
    d = utils.getProcessOutput('git', ('config', '--get', 'github.token'), env=os.environ)
    d.addCallback(str.strip)
    return d
