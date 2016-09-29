"""
Tests for L{txgithub.scripts.gist}
"""
import io
from collections import namedtuple
from twisted.python import usage
from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.defer import Deferred, succeed

from txgithub.scripts import gist

from . _options import (_OptionsTestCaseMixin,
                        _FakeOptionsTestCaseMixin,
                        _FakePrintTestCaseMixin,
                        _FakeSystemExitTestCaseMixin,
                        _SystemExit)


class OptionsTestCase(_OptionsTestCaseMixin):
    """
    Tests for L{gist.Options}
    """
    files = ('files',)
    required_args = files
    options_factory = gist.Options

    def test_single_file_ok(self):
        """
        Files is an argument.
        """
        self.config.parseOptions(self.files)
        self.assertEqual(self.config['files'], self.files)

    def test_files_ok(self):
        """
        Multiple files are collected.
        """
        self.config.parseOptions(["file1", "file2"])
        self.assertEqual(self.config['files'], ("file1", "file2"))

    def test_token_ok(self):
        """
        --token is an option.
        """
        token = 'some token'
        self.assert_option(['--token=' + token], 'token', token)

    def test_t_ok(self):
        """
        -t is short for --token
        """
        token = 'some token'
        self.assert_option(['-t', token], 'token', token)


class RecordsFakeGistsEndpoint(object):
    """
    Records and orchestrates L{FakeGistsEndpoint}.
    """

    def __init__(self):
        self.create_calls = []
        self.create_returns = Deferred()


class FakeGistsEndpoint(object):
    """
    A fake implementation of L{txgithub.api.GithubApi} that records
    calls.
    """

    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, files):
        self._recorder.create_calls.append(files)
        return self._recorder.create_returns


class RecordsFakeGithubAPI(object):
    """
    Records and orchestrates L{FakeGithubAPI}.
    """

    def __init__(self):
        self.init_calls = []


class FakeGithubAPI(object):
    """
    A fake implementation of L{txgithub.api.GithubApi} that records
    calls.
    """

    def __init__(self, recorder, gists):
        self._recorder = recorder
        self.gists = gists

    def _init(self, token):
        self._recorder.init_calls.append(token)
        return self


class PostGistTests(SynchronousTestCase):
    """
    Tests for L{gist.postGist}.
    """

    def setUp(self):
        self.token = "token"
        self.getToken_call_count = 0
        self.getToken_returns = succeed(self.token)

        self.gists_recorder = RecordsFakeGistsEndpoint()
        self.gists = FakeGistsEndpoint(self.gists_recorder)

        self.api_recorder = RecordsFakeGithubAPI()
        self.fake_api = FakeGithubAPI(self.api_recorder, self.gists)

        self.content = u"content"

        self.stdin = io.StringIO(self.content)

        self.open_calls = []
        self.open_returns = io.StringIO(self.content)

        self.print_calls = []

        self.patch(gist, "getToken", self.fake_getToken)
        self.patch(gist, "GithubApi", self.fake_api._init)
        self.patch(gist, "_open", self.fake_open)
        self.patch(gist, "stdin", self.stdin)
        self.patch(gist, "_print", self.fake_print)

    def fake_getToken(self):
        """
        A fake get token implementation that records its calls.
        """
        self.getToken_call_count += 1
        return self.getToken_returns

    def fake_open(self, filename):
        """
        A fake L{open} that records its calls.
        """
        self.open_calls.append(filename)
        return self.open_returns

    def fake_print(self, *args):
        """
        A fake L{print} that records its calls.
        """
        self.print_calls.append(args)

    def test_getToken_by_default(self):
        """
        When no token is provided, the get token implementation is
        called to retrieve one.
        """
        gist.postGist("reactor", token="", files=["something"])
        self.assertEqual(self.getToken_call_count, 1)
        self.assertEqual(self.api_recorder.init_calls, [self.token])

    def test_token_used(self):
        """
        The provided token is used to connect to GitHub.
        """
        token = "my token"
        gist.postGist("reactor", token=token, files=["something"])
        self.assertEqual(self.getToken_call_count, 0)
        self.assertEqual(self.api_recorder.init_calls, [token])

    def test_stdin_gist(self):
        """
        When no files are provided, the gist is read from stdin.
        """
        gist.postGist("reactor", token=self.token, files=())
        self.assertEqual(self.gists_recorder.create_calls, [
            {
                "gistfile1": {
                    "content": self.content,
                },
            }
        ])
        self.assertEqual(self.stdin.tell(), len(self.content))

    def test_files_used(self):
        """
        The filenames provided are read and comprise the gist's content.
        """
        filename = "some file"

        gist.postGist("reactor", token=self.token, files=[filename])

        self.assertEqual(self.open_calls, [filename])
        self.assertTrue(self.open_returns.closed)

        self.assertEqual(self.gists_recorder.create_calls, [
            {
                "some file": {
                    "content": self.content,
                },
            }
        ])

    def test_response_printed(self):
        """
        The URL in the API's response is printed.
        """
        url = "https://something"
        response = gist.postGist("reactor", token=self.token, files=[])

        self.gists_recorder.create_returns.callback(
            {
                "html_url": url,
            }
        )
        self.successResultOf(response)

        self.assertEqual(self.print_calls, [(url,)])


_PostGistCall = namedtuple("_PostGistCall",
                           ["reactor", "token", "files"])


class RunTests(_FakeOptionsTestCaseMixin,
               _FakeSystemExitTestCaseMixin,
               _FakePrintTestCaseMixin):
    """
    Tests for L{txgithub.scripts.gist.run}
    """

    def setUp(self):
        super(RunTests, self).setUp()
        self.postGist_calls = []
        self.postGist_returns = "postGist return value"

        self.patch(gist, "Options", lambda: self.options)
        self.patch(gist, "_print", self.fake_print)
        self.patch(gist, "exit", self.fake_exit)
        self.patch(gist, "postGist", self.fake_postGist)

    def fake_postGist(self, reactor, token, files):
        """
        A fake L{gist.postGist} implementation that records its calls.
        """
        self.postGist_calls.append(_PostGistCall(reactor, token, files))
        return self.postGist_returns

    def test_run_usage_error(self):
        """
        A usage error results in a help message and an exit code of 1.
        """

        errortext = "error text"
        first_line = ': '.join([self.argv0, errortext])

        self.options_recorder.parseOptions_raises = usage.UsageError(errortext)

        self.assertRaises(_SystemExit,
                          gist.run, "reactor", self.argv0, "bad args")

        self.assertEqual(self.options_recorder.parseOptions_calls,
                         [("bad args",)])

        self.assertEqual(len(self.print_calls), 2)
        self.assertEqual(self.print_calls[0], (first_line,))
        self.assertIn("--help", self.print_calls[1][0])

        self.assertEqual(len(self.exit_calls), 1)
        [code] = self.exit_calls
        self.assertEqual(code, 1)

        self.assertNot(self.postGist_calls)

    def test_run_ok(self):
        """
        The post gist implementation is called with the options
        specified on the command line.
        """
        reactor = "reactor"
        self.options["token"] = "the token"
        self.options["files"] = ("file1",)

        result = gist.run(reactor, self.argv0, "good args")

        self.assertEqual(self.options_recorder.parseOptions_calls,
                         [("good args",)])

        self.assertEqual(len(self.postGist_calls), 1)
        [call] = self.postGist_calls
        self.assertIs(call.reactor, reactor)
        self.assertEqual(call.token, self.options["token"])
        self.assertEqual(call.files, self.options["files"])

        self.assertIs(result, self.postGist_returns)
