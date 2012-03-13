#! /usr/bin/env python

import json
import urllib2
import base64
import getpass
import readline
assert readline # here for side-effects

def main():
    username = raw_input("github username: ")
    password = getpass.getpass("github password: ")

    raw = "%s:%s" % (username, password)
    encoded = base64.b64encode(raw).strip()
    headers = { 'Authorization' : 'Basic ' + encoded }

    postData = json.dumps(dict(
        note = 'Highscore',
        note_url = 'https://github.com/djmitche/highscore',
        scopes = 'public_repo',
    ))
    req = urllib2.Request('https://api.github.com/authorizations',
            data=postData,
            headers=headers)
    fp = urllib2.urlopen(req)
    result = json.load(fp)
    token = result['token']
    print("oauth2_token=%r" % (token,))

main()
