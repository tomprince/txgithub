"""
Tests for L{txgithub.scripts.create_token}
"""
from collections import namedtuple
from twisted.python import usage
from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.defer import Deferred

from txgithub.scripts import create_token


class OptionsTestCase(SynchronousTestCase):
    """
    Tests for L{create_token.Options}
    """

    def setUp(self):
        self.username = "username"
        self.config = create_token.Options()

    def test_username_argument(self):
        """
        Username is an argument.
        """
        username = self.username
        self.config.parseOptions([self.username])
        self.assertEqual(self.config['username'], username)

    def assert_option(self, option_inputs, option_name, expected_value):
        """
        Assert that the input C{option_inputs} is parsed into
        C{expected_value} and available in C{self.config} under
        C{option_name}.
        """
        self.config.parseOptions(option_inputs + [self.username])
        self.assertEqual(self.config[option_name], expected_value)

    def test_note_ok(self):
        """
        --note is an option.
        """
        note = 'some note'
        self.assert_option(['--note=' + note], 'note', note)

    def test_n_ok(self):
        """
        -n is short for --note.
        """
        note = 'some note'
        self.assert_option(['-n', note], 'note', note)

    def test_url_ok(self):
        """
        --url is an option.
        """
        url = 'some url'
        self.assert_option(['--url=' + url], 'url', url)

    def test_u_ok(self):
        """
        -u is an option.
        """
        url = 'some url'
        self.assert_option(['-u', url], 'url', url)

    def test_single_scope_ok(self):
        """
        --scope is an option.
        """
        scope = 'scope'
        self.assert_option(['--scope=' + scope], 'scopes', [scope])

    def test_single_s_ok(self):
        """
        -s is short for --scope.
        """
        scope = 'scope'
        self.assert_option(['-s', scope], 'scopes', [scope])

    def test_multiple_scope_ok(self):
        """
        Multiple --scope options are collected.
        """
        scope1 = 'scope1'
        scope2 = 'scope2'
        self.assert_option(['--scope=' + scope1,
                            '--scope=' + scope2],
                           'scopes',
                           [scope1, scope2])

    def test_multiple_s_ok(self):
        """
        Multiple -s options are collected.
        """
        scope1 = 'scope1'
        scope2 = 'scope2'
        self.assert_option(['-s', scope1,
                            '-s', scope2],
                           'scopes',
                           [scope1, scope2])


_CreateTokenCalls = namedtuple(
    '_CreateTokenCalls',
    ['username', 'password', 'note', 'note_url', 'scopes'])


class CreateTokenTests(SynchronousTestCase):
    """
    Tests for L{txgithub.scripts.createToken}
    """

    def setUp(self):
        self.createToken_calls = []
        self.print_calls = []
        self.createToken_deferred = Deferred()

        self.username = "username"
        self.password = "password"
        self.note = "note"
        self.url = "note url"
        self.scopes = "scopes"

    def fake_print(self, *args):
        """
        A fake L{print} that records its arguments.
        """
        self.print_calls.append(args)

    def fake_createToken(self, username, password, note, note_url, scopes):
        """
        A fake L{create_token.createToken} that records it arguments.
        """
        self.createToken_calls.append(
            _CreateTokenCalls(username, password, note, note_url, scopes))
        return self.createToken_deferred

    def test_createToken_ok(self):
        """
        L{create_token.createToken} calls its create token
        implementation and prints the output
        """
        token_deferred = create_token.createToken(
            "reactor",
            self.username,
            self.password,
            self.note,
            self.url,
            self.scopes,
            _createToken=self.fake_createToken,
            _print=self.fake_print)

        self.assertEqual(len(self.createToken_calls), 1)
        [call] = self.createToken_calls

        self.assertEqual(call.username, self.username)
        self.assertEqual(call.password, self.password)
        self.assertEqual(call.note, self.note)
        self.assertEqual(call.note_url, self.url)
        self.assertEqual(call.scopes, self.scopes)

        token_deferred.callback("token")
        self.successResultOf(token_deferred)

        self.assertEqual(self.print_calls, [("token",)])


class _FakeOptionsRecorder(object):
    """
    Records actions on L{_FakeOptions}
    """

    def __init__(self):
        self.parseOptions_calls = []
        self.parseOptions_raises = None


class _FakeOptions(dict):
    """
    A fake L{Options} implementation.
    """

    def __init__(self, recorder):
        self._recorder = recorder

    def parseOptions(self, argv):
        self._recorder.parseOptions_calls.append(argv)
        if self._recorder.parseOptions_raises:
            raise self._recorder.parseOptions_raises


class _SystemExit(Exception):
    """
    A fake L{SystemExit}.
    """


class RunTests(SynchronousTestCase):
    """
    Tests for L{txgithub.scripts.create_token.run}.
    """

    def setUp(self):
        self.argv0 = "argv0"

        self.recorder = _FakeOptionsRecorder()
        self.options = _FakeOptions(self.recorder)

        self.createToken_calls = []
        self.createToken_returns = "create token returns"
        self.print_calls = []
        self.exit_calls = []
        self.getpass_calls = []
        self.getpass_returns = None

        self.run = create_token._makeRun(_optionsFactory=lambda: self.options,
                                         _createToken=self.fake_createToken,
                                         _print=self.fake_print,
                                         _exit=self.fake_exit,
                                         _getpass=self.fake_getpass)

    def fake_createToken(self, reactor, **kwargs):
        """
        A fake L{create_token.createToken} that records its arguments.
        """

        self.createToken_calls.append(kwargs)
        return self.createToken_returns

    def fake_print(self, *args):
        """
        A fake L{print} that records its arguments.
        """
        self.print_calls.append(args)

    def fake_exit(self, code):
        """
        A fake L{sys.exit} that records its arguments.
        """
        self.exit_calls.append(code)
        raise _SystemExit

    def fake_getpass(self, prompt):
        """
        A fake L{getpass.getpass} that records its arguments.
        """
        self.getpass_calls.append(prompt)
        return self.getpass_returns

    def test_run_usage_error(self):
        """
        A usage error results in a help message and an exit code of 1
        """
        errortext = "error text"
        first_line = ': '.join([self.argv0, errortext])

        self.recorder.parseOptions_raises = usage.UsageError(errortext)

        self.assertRaises(_SystemExit,
                          self.run, "reactor", self.argv0, "bad args")

        self.assertEqual(self.recorder.parseOptions_calls, [("bad args",)])

        self.assertEqual(len(self.print_calls), 2)
        self.assertEqual(self.print_calls[0], (first_line,))
        self.assertIn("--help", self.print_calls[1][0])

        self.assertEqual(len(self.exit_calls), 1)
        [code] = self.exit_calls
        self.assertEqual(code, 1)

        self.assertNot(self.createToken_calls)

    def test_run_ok(self):
        """
        The user is prompted for their password, and their command
        line arguments are passed to the create token implementation.
        """
        reactor = "reactor"
        self.getpass_returns = "password"

        result = self.run(reactor, self.argv0, "good args")

        self.assertEqual(self.recorder.parseOptions_calls, [("good args",)])
        self.assertEqual(len(self.getpass_calls), 1)

        self.assertIs(self.options["password"], self.getpass_returns)

        self.assertEqual(len(self.createToken_calls), 1)
        [kwargs] = self.createToken_calls

        self.assertEqual(kwargs, dict(self.options))

        self.assertEqual(result, self.createToken_returns)
