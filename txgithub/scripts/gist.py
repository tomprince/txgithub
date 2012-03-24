import sys
from os import path
from twisted.python import usage
from twisted.internet import defer

class Options(usage.Options):
    synopsis = "[-t <token>] <files>"
    optParameters = [["token", "t", None, "oauth token"]]

    longdesc = "Posts a gist."

    def parseArgs(self, *files):
        self['files'] = files

@defer.inlineCallbacks
def postGist(reactor, token, files):
    if not token:
        from txgithub import token
        token = yield token.getToken()

    from txgithub import api
    api = api.GithubApi(token)

    gistFiles = {}
    if files:
        for name in files:
            with open(name) as f:
                gistFiles[path.basename(name)] = {"content": f.read()}
    else:
        gistFiles['gistfile1'] = {"content": sys.stdin.read()}

    response = yield api.gists.create(files=gistFiles)
    print response['html_url']


def run(reactor, *argv):
    config = Options()
    try:
        config.parseOptions(argv[1:]) # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        print '%s: %s' % (argv[0], errortext)
        print '%s: Try --help for usage details.' % (argv[0])
        sys.exit(1)

    return postGist(reactor, **config)
