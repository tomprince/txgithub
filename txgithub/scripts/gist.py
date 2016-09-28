from __future__ import print_function
import sys
from os import path
from twisted.python import usage
from twisted.internet import defer
from txgithub import api, token


class Options(usage.Options):
    synopsis = "[-t <token>] <files>"
    optParameters = [["token", "t", None, "oauth token"]]

    longdesc = "Posts a gist."

    def parseArgs(self, *files):
        self['files'] = files


@defer.inlineCallbacks
def postGist(reactor, token, files,
             _getToken=token.getToken,
             _githubAPIFactory=api.GithubApi,
             _open=open,
             _stdin=sys.stdin,
             _print=print):
    if not token:
        token = yield _getToken()

    api = _githubAPIFactory(token)

    gistFiles = {}
    if files:
        for name in files:
            with _open(name) as f:
                gistFiles[path.basename(name)] = {"content": f.read()}
    else:
        gistFiles['gistfile1'] = {"content": _stdin.read()}

    response = yield api.gists.create(files=gistFiles)
    _print(response['html_url'])


def _makeRun(_optionsFactory=Options,
             _print=print,
             _exit=sys.exit,
             _postGist=postGist):
    def run(reactor, *argv):
        config = _optionsFactory()
        try:
            config.parseOptions(argv[1:]) # When given no argument, parses sys.argv[1:]
        except usage.UsageError, errortext:
            _print('%s: %s' % (argv[0], errortext))
            _print('%s: Try --help for usage details.' % (argv[0]))
            _exit(1)

        return _postGist(reactor, **config)
    return run

run = _makeRun()
