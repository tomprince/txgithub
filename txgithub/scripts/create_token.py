from __future__ import print_function

import sys
from twisted.python import usage

class Options(usage.Options):
    optParameters = [["note", "n", "txgithub", "token note"],
            ["url", "u", "https://github.com/tomprince/txgithub", "token note url"]
            ]

    longdesc = "Create a new github oauth2 token."

    def __init__(self):
        usage.Options.__init__(self)
        self['scopes'] = []

    def opt_scope(self, scope):
        self['scopes'].append(scope)
    opt_s = opt_scope

    def parseArgs(self, username):
        self['username'] = username

def createToken(reactor, username, password, note, url, scopes):
    from txgithub import token
    d = token.createToken(username, password,
            note=note, note_url=url,
            scopes = scopes
            )
    d.addCallback(print)
    return d

def run(reactor, *argv):
    config = Options()
    try:
        config.parseOptions(argv[1:]) # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        print('%s: %s' % (argv[0], errortext))
        print('%s: Try --help for usage details.' % (argv[0]))
        sys.exit(1)

    import getpass
    config['password'] = getpass.getpass("github password: ")

    return createToken(reactor, **config)
