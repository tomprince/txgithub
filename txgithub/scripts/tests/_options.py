"""
Fake L{twisted.python.usage.Options} implementation.
"""
from twisted.trial.unittest import SynchronousTestCase


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


class _OptionsTestCaseMixin(SynchronousTestCase):
    """
    A mixin that eases testing L{twisted.python.options.Options}

    @ivar required_args: The required arguments for the
        L{twisted.python.options.Options} under test.
    @type required_args: An iterable of L{str}

    @ivar config: The L{twisted.python.options.Options} instance under
        test, obtained from L{options_factory}

    @ivar options_factory: A factory that returns
        L{twisted.python.options.Options} to test.
    @type options_factory: A no-argument L{callable} that returns
        L{twisted.python.options.Options}
    """
    required_args = ()

    def setUp(self):
        super(_OptionsTestCaseMixin, self).setUp()

        self.config = self.options_factory()

    def assert_option(self, option_inputs, option_name, expected_value):
        """
        Assert that the input C{option_inputs} is parsed into
        C{expected_value} and available in C{self.config} under
        C{option_name}.
        """
        self.config.parseOptions(option_inputs + list(self.required_args))
        self.assertEqual(self.config[option_name], expected_value)


class _FakeOptionsTestCaseMixin(SynchronousTestCase):
    """
    A mixin that provides a fake L{twisted.python.options.Options}
    implementation.

    @ivar argv0: A fake C{argv[0]}
    @type argv0: L{str}

    @ivar options_recorder: An object that records and orchestrates
        C{self.options}
    @type options_recorder: L{_FakeOptionsRecorder}

    @ivar options: The fake L{twisted.python.options.Options}
        instance.
    @type options: L{_FakeOptions}
    """

    argv0 = "argv0"

    def setUp(self):
        super(_FakeOptionsTestCaseMixin, self).setUp()
        self.options_recorder = _FakeOptionsRecorder()
        self.options = _FakeOptions(self.options_recorder)


class _FakeSystemExitTestCaseMixin(SynchronousTestCase):
    """
    A mixin that provides a fake implementation of L{sys.exit}

    @ivar exit_calls: A list of exit codes with which the fake
        L{sys.exit} was called.
    @type exit_calls: L{list}
    """

    def setUp(self):
        super(_FakeSystemExitTestCaseMixin, self).setUp()
        self.exit_calls = []

    def fake_exit(self, code):
        """
        A fake L{sys.exit} that records its arguments.

        @raises: L{_SystemExit}
        """
        self.exit_calls.append(code)
        raise _SystemExit


class _FakePrintTestCaseMixin(SynchronousTestCase):
    """
    A mixin that provides a fake implementation of L{print}

    @ivar print_calls: A list of arguments with which the fake
        L{print} was called.
    @type print_calls: L{list}
    """

    def setUp(self):
        super(_FakePrintTestCaseMixin, self).setUp()
        self.print_calls = []

    def fake_print(self, *args):
        """
        A fake L{print} that records its arguments.
        """
        self.print_calls.append(args)
