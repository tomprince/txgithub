from __future__ import print_function

import getpass
import sys
from twisted.python import usage

from txgithub import token


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


def createToken(reactor, username, password, note, url, scopes,
                _createToken=token.createToken,
                _print=print):
    d = _createToken(
        username, password,
        note=note, note_url=url,
        scopes=scopes)
    d.addCallback(_print)
    return d


def _makeRun(_optionsFactory=Options,
             _createToken=createToken,
             _print=print,
             _exit=sys.exit,
             _getpass=getpass.getpass):
    def run(reactor, *argv):
        config = _optionsFactory()
        try:
            config.parseOptions(argv[1:]) # When given no argument, parses sys.argv[1:]
        except usage.UsageError, errortext:
            _print('%s: %s' % (argv[0], errortext))
            _print('%s: Try --help for usage details.' % (argv[0]))
            _exit(1)

        config['password'] = _getpass("github password: ")

        return _createToken(reactor, **config)
    return run

run = _makeRun()
