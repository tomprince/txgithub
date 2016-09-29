from __future__ import print_function
from sys import exit, stdin
from os import path
from twisted.python import usage
from twisted.internet import defer
from txgithub.api import GithubApi
from txgithub.token import getToken

__all__ = ["Options", "postGist", "run"]


_print = print
_open = open


class Options(usage.Options):
    synopsis = "[-t <token>] <files>"
    optParameters = [["token", "t", None, "oauth token"]]

    longdesc = "Posts a gist."

    def parseArgs(self, *files):
        self['files'] = files


@defer.inlineCallbacks
def postGist(reactor, token, files):
    if not token:
        token = yield getToken()

    github = GithubApi(token)

    gistFiles = {}
    if files:
        for name in files:
            with _open(name) as f:
                gistFiles[path.basename(name)] = {"content": f.read()}
    else:
        gistFiles['gistfile1'] = {"content": stdin.read()}

    response = yield github.gists.create(files=gistFiles)
    _print(response['html_url'])


def run(reactor, *argv):
    config = Options()
    try:
        config.parseOptions(argv[1:]) # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        _print('%s: %s' % (argv[0], errortext))
        _print('%s: Try --help for usage details.' % (argv[0]))
        exit(1)

    return postGist(reactor, **config)
