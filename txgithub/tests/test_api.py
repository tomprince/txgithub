"""
Tests for Twisted GitHub API bindings.
"""
from collections import namedtuple
from twisted.trial.unittest import SynchronousTestCase

from twisted.internet.defer import succeed
from twisted.internet.main import CONNECTION_DONE
from twisted.python import log
from twisted.test.proto_helpers import MemoryReactor

from txgithub.api import GithubApi as GitHubAPI
from txgithub.api import (_GithubPageGetter,
                          _GithubHTTPClientFactory)
from txgithub.constants import HOSTED_BASE_URL

import urlparse


_ConnectSSLArguments = namedtuple("_ConnectSSLArguments",
                                  ["host", "port", "factory", "contextFactory",
                                   "timeout", "interface"])


class TestGithubPageGetter(SynchronousTestCase):
    """
    Tests for L{_GithubPageGetter}.
    """

    def setUp(self):
        self.getter = _GithubPageGetter()

    def test_204_status(self):
        """
        A 204 status code is equivalent to a 200 status code.
        """
        calls = []

        def handleStatus_200():
            calls.append(None)

        self.getter.handleStatus_200 = handleStatus_200
        self.getter.handleStatus_204()

        self.assertEqual(len(calls), 1)


class TestGithubHTTPClientFactory(SynchronousTestCase):
    """
    Tests for L{_GithubHTTPClientFactory}.
    """

    def setUp(self):
        self.url = "gopher://some thing"
        self.factory = _GithubHTTPClientFactory(self.url)

    def test_protocol_is_GithubPageGetter(self):
        """
        The factory builds an instance L{_GithubPageGetter}.
        """
        self.assertIsInstance(self.factory.buildProtocol("ignored address"),
                              _GithubPageGetter)

    def test_quiet_logging(self):
        """
        The factory is configured to suppress log messages about its
        starting and stopping.
        """
        self.assertFalse(self.factory.noisy)


class _GithubApiTestCase(SynchronousTestCase):
    """
    Common setup for L{GithubApi} tests.
    """

    def setUp(self):
        self.reactor = MemoryReactor()

        self.base_url = "https://baseurl"

        self.oauth_token = b"oauth token"
        self.token_header = b"token oauth token"

        self.api = GitHubAPI(self.oauth_token,
                             baseURL=self.base_url,
                             reactor=self.reactor)


class GithubApiTest(_GithubApiTestCase):
    """
    Tests for L{GithubApi}.
    """

    def test_default_url(self):
        """
        A default URL is used if none is specified.
        """
        api = GitHubAPI(self.oauth_token,
                        reactor=self.reactor)
        self.assertEqual(api._baseURL, HOSTED_BASE_URL)

    def test_specified_url(self):
        """
        The specified URL is used.
        """
        self.assertEqual(self.api._baseURL, self.base_url)

    def test_makeHeaders_no_oauth_token(self):
        """
        An empty OAuth token is not allowed.
        """
        with self.assertRaises(AssertionError):
            GitHubAPI("")._makeHeaders()

    def test_makeHeaders(self):
        """
        The provided OAuth token is added to the request headers.
        """
        headers = self.api._makeHeaders()
        self.assertIn(b"Authorization", headers)
        self.assertEqual(headers[b"Authorization"], self.token_header)


class GithubApiMakeRequestTests(_GithubApiTestCase):
    """
    Tests for L{GithubApi.makeRequest} and L{GithubApi.makeRequestAllPages}.
    """

    def setUp(self):
        super(GithubApiMakeRequestTests, self).setUp()
        self.log_events = []
        log.addObserver(self.got_log_event)

    def tearDown(self):
        log.removeObserver(self.got_log_event)

    def got_log_event(self, event):
        """
        A log observer that records events' messages.
        """
        self.log_events.append(event['message'])

    def connectSSL_call(self):
        self.assertEqual(len(self.reactor.sslClients), 1)
        return _ConnectSSLArguments(*self.reactor.sslClients[-1])

    def factory_from_makeRequest(self, *args, **kwargs):
        self.api.makeRequest(*args, **kwargs)
        return self.connectSSL_call().factory

    def test_tls_connection(self):
        """
        Requests are made over TLS, to the host in the requested URL.
        """
        self.api.makeRequest([])
        args = self.connectSSL_call()
        self.assertEqual(args.host,
                         urlparse.urlparse(self.base_url).netloc)
        self.assertEqual(args.port, 443)

    def test_uses_GithubHTTPClientFactory(self):
        """
        Requests are made via L{_GithubHTTPClientFactory}
        """
        self.assertIsInstance(self.factory_from_makeRequest([]),
                              _GithubHTTPClientFactory)

    def test_timeout(self):
        """
        Requests have a timeout.
        """
        # just hard coded for now
        self.assertEqual(self.factory_from_makeRequest([]).timeout, 30)

    def test_agent_set(self):
        """
        Requests set an agent.
        """
        # just hard coded for now
        self.assertEqual(self.factory_from_makeRequest([]).agent, "txgithub")

    def test_redirects_not_followed(self):
        """
        Redirects are not followed automatically.
        """
        # just hard coded for now
        self.assertFalse(self.factory_from_makeRequest([]).followRedirect)

    def test_constructs_url(self):
        """
        The request URL contains the specified path components
        """
        factory = self.factory_from_makeRequest(["a", "b", "c"])
        self.assertEqual(factory.url, self.base_url + "a/b/c")

    def test_constructs_url_with_page(self):
        """
        The request URL contains the specified path components and
        page number.
        """
        factory = self.factory_from_makeRequest(["a", "b", "c"], page=1)
        self.assertEqual(factory.url, self.base_url + "a/b/c?page=1")

    def test_default_GET(self):
        """
        The default method is GET.
        """
        self.assertEqual(self.factory_from_makeRequest([]).method, "GET")

    def test_json_body(self):
        """
        Request bodies are JSON serialized when present.
        """
        factory = self.factory_from_makeRequest([], post={"some": "data"})
        self.assertEqual(factory.postdata, '{"some": "data"}')

    def complete_response(self, factory):
        """
        Ensure that C{factory}'s C{deferred} fires.  C{factory}'s
        C{page} method should have been called with the request's
        body.
        """
        protocol = factory.buildProtocol("ignored")
        protocol.connectionLost(CONNECTION_DONE)

    def test_last_response_headers(self):
        """
        The last completed response's headers are saved.
        """
        headers = {u"header": [u"value"]}

        factory = self.factory_from_makeRequest([])
        factory.response_headers = headers

        factory.page("")
        self.complete_response(factory)
        self.assertIs(self.api.last_response_headers, headers)

    def test_check_ratelimit_almost_exhausted(self):
        """
        A log message is generated when the number of remaining requests
        reported by GitHub drops below the threshold.
        """
        factory = self.factory_from_makeRequest([])
        factory.response_headers = {'x-ratelimit-remaining': ['1']}

        # clear other logged events
        del self.log_events[:]

        factory.page("")
        self.complete_response(factory)

        self.assertTrue(self.api.rateLimitWarningIssued)
        self.assertEqual(self.log_events,
                         [('warning: only 1 Github'
                           ' API requests remaining'
                           ' before rate-limiting',)])

    def test_check_ratelimit_not_exhausted(self):
        """
        No log message is generated when the number of remaining
        requests exceeds the threshold.
        """
        factory = self.factory_from_makeRequest([])
        factory.response_headers = {'x-ratelimit-remaining': ['1000']}

        # clear other logged events
        del self.log_events[:]

        factory.page("")
        self.complete_response(factory)

        self.assertFalse(self.api.rateLimitWarningIssued)
        self.assertFalse(self.log_events)

    def test_json_deserialize(self):
        """
        The body of the response is deserialized as JSON.
        """
        response_deferred = self.api.makeRequest([])

        factory = self.connectSSL_call().factory
        factory.response_headers = {}

        factory.page(b'{"body": "value"}')

        self.complete_response(factory)

        result = self.successResultOf(response_deferred)
        self.assertEqual(result, {u"body": u"value"})

    def assert_makeRequestAllPages_downloads(self, pages, headers):
        """
        Assert all C{pages} have been downloaded.
        """
        page_headers = iter(zip(pages, headers))
        calls = []

        def fake_makeRequest(url_args, page):
            calls.append((url_args, page))
            page, headers = next(page_headers)
            self.api.last_response_headers = headers
            return succeed([page])

        self.api.makeRequest = fake_makeRequest
        data = self.successResultOf(self.api.makeRequestAllPages([]))

        self.assertEqual(calls, [([], i) for i in range(len(pages))])
        self.assertEqual(data, pages)

    def test_makeRequestAllPages_single_page(self):
        """
        A single page resource is retrieved and returned.
        """
        pages = [{"page": 1}]
        headers = [{}]
        self.assert_makeRequestAllPages_downloads(pages, headers)

    def test_makeRequestAllPages_multiple_pages(self):
        """
        All pages of a multi-page resource are retrieved and returned
        together.
        """
        pages = [{"page": 1}, {"page": 2}, {"page": 3}]
        headers = [{"link": ['<https://something>; rel="next"']},
                   {"link": ['<https://else>; rel="next", '
                             '<https://something>; rel="last"']},
                   {"link": ['<https://else>; rel="last"']}]
        self.assert_makeRequestAllPages_downloads(pages, headers)


class _EndpointTestCase(SynchronousTestCase):
    """
    Common code to for Endpoint tests.

    Establishes request mocker and creates an API object.
    """

    def _mock_makeRequest(self, *args, **kwargs):
        try:
            self._github_requests.append({'args': args, 'kwargs': kwargs})
            response = self._github_responses.pop()
            return succeed(response)
        except IndexError:
            return succeed({})

    def setUp(self):
        self._github_responses = []
        self._github_requests = []
        self.github = GitHubAPI(oauth2_token='fake-token')
        self.github.makeRequest = self._mock_makeRequest

    def assertRequestEqual(self, request, method, post):
        self.assertEqual(method, request['kwargs']['method'])
        self.assertEqual(post, request['kwargs']['post'])


class TestReposEndpoint(_EndpointTestCase):
    """
    Unit tests for ReposEndpoint.
    """

    def setUp(self):
        super(TestReposEndpoint, self).setUp()
        self.repos = self.github.repos

    def test_same_repos_object(self):
        """
        The L{ReposEndpoint} is lazily created once.
        """
        self.assertIs(self.github.repos, self.repos)

    def assert_getEvents_downloads(self, events, expected_events,
                                   repo_user, repo_name, until_id=None):
        """
        Given C{events}, assert all C{expected_events} have been
        downloaded.  All other args are passed
        L{ReposEndpoint.getEvents}.
        """
        events_iter = iter(events)
        calls = []

        def fake_makeRequest(path, page):
            calls.append((path, page))
            event = next(events_iter, None)
            return succeed([] if event is None else [event])

        self.github.makeRequest = fake_makeRequest
        data = self.successResultOf(self.repos.getEvents(
            repo_user, repo_name, until_id))

        self.assertEqual(calls, [
            (["repos", repo_user, repo_name, "events"], i)
            for i in range(len(expected_events) + 1)])
        self.assertEqual(data, expected_events)

    def test_getEvents_ok(self):
        """
        By default all events are downloaded and returned.
        """
        events = [{"id": 1}, {"id": 2}, {"id": 3}]
        expected_events = events
        self.assert_getEvents_downloads(events, expected_events,
                                        "user", "repo")

    def test_getEvents_until_id(self):
        """
        Only events before C{until_id} are downloaded
        """
        events = [{"id": 1}, {"id": 2}, {"id": 3}]
        expected_events = [{"id": 1}]
        self.assert_getEvents_downloads(events, expected_events,
                                        "user", "repo", until_id=2)

    def test_getHooks_ok(self):
        """
        L{GithubApi.getHooks} returns all hooks
        """
        makeRequestAllPages_returns = "makeRequestAllPages"
        calls = []

        def fake_makeRequestAllPages(path):
            calls.append(path)
            return makeRequestAllPages_returns

        self.github.makeRequestAllPages = fake_makeRequestAllPages

        self.assertIs(self.repos.getHooks("user", "name"),
                      makeRequestAllPages_returns)
        self.assertEqual(calls, [["repos", "user", "name", "hooks"]])

    def test_getHook_ok(self):
        """
        getHook return the info for a single hook.
        """
        self._github_responses = [{'hook': 'data'}]
        d = self.repos.getHook('repo', 'name', 123)

        result = self.successResultOf(d)

        self.assertEqual({'hook': 'data'}, result)
        request = self._github_requests[0]
        self.assertEqual('GET', request['kwargs']['method'])
        self.assertEqual(
            ['repos', 'repo', 'name', 'hooks', '123'],
            request['args'][0])

    def test_editHook_no_options(self):
        """
        editHook can be used for updating only the hook configuration,
        without updating events lists or active state.
        """
        self._github_responses = [{'updated': 'hook'}]
        config = {'url': 'some_url', 'content_type': 'json'}
        d = self.repos.editHook('repo', 'name', 123, 'web', config)

        result = self.successResultOf(d)

        self.assertEqual({'updated': 'hook'}, result)
        request = self._github_requests[0]
        self.assertEqual('PATCH', request['kwargs']['method'])
        self.assertEqual(
            ['repos', 'repo', 'name', 'hooks', '123'],
            request['args'][0])
        self.assertEqual(
            {
                'config': {'content_type': 'json', 'url': 'some_url'},
                'name': 'web',
            },
            request['kwargs']['post'])

    def test_createHook_ok(self):
        """
        L{GithubApi.createHook} creates a hook according to the
        specification.
        """
        config = {'url': 'some_url', 'content_type': 'json'}
        self.repos.createHook("user", "repo",
                              name="web",
                              config=config,
                              events=["push"],
                              active=True)

        request = self._github_requests[0]
        self.assertEqual(
            ['repos', 'user', 'repo', 'hooks'],
            request['args'][0])
        self.assertEqual(
            {
                'name': 'web',
                'active': True,
                'events': ['push'],
                'config': {'content_type': 'json', 'url': 'some_url'},
                'name': 'web',
            },
            request['kwargs']['post'])

    def test_editHook_with_options(self):
        """
        editHook can update the hooks state together with the list of
        active events.
        """
        config = {'url': 'some_url', 'content_type': 'json'}
        self.repos.editHook('repo', 'name', 123, 'web', config,
            active=False,
            events=['push'],
            add_events=['status'],
            remove_events=[],
            )

        request = self._github_requests[0]
        self.assertEqual(
            {
                'name': 'web',
                'active': False,
                'events': ['push'],
                'add_events': ['status'],
                'remove_events': [],
                'config': {'content_type': 'json', 'url': 'some_url'},
                'name': 'web',
            },
            request['kwargs']['post'])

    def test_testHook_ok(self):
        """
        testHook just triggers the test and returns nothing.
        """
        self._github_responses = ['']
        d = self.repos.testHook('repo', 'name', 123)

        result = self.successResultOf(d)

        self.assertEqual('', result)
        request = self._github_requests[0]
        self.assertEqual('POST', request['kwargs']['method'])
        self.assertEqual(
            ['repos', 'repo', 'name', 'hooks', '123', 'tests'],
            request['args'][0])

    def test_deleteHook_ok(self):
        """
        L{GithubApi.deleteHook} deletes the specified hook.
        """
        self.repos.deleteHook("user", "repo", 123)

        request = self._github_requests[0]
        self.assertEqual('DELETE', request['kwargs']['method'])
        self.assertEqual(
            ['repos', 'user', 'repo', 'hooks', '123'],
            request['args'][0])

    def test_getStatuses_ok(self):
        """
        getStatuses will return the raw dictionary returned by GitHub.
        """
        self._github_responses = [{'response': 1}]
        d = self.repos.getStatuses('repo', 'name', 'sha123')

        result = self.successResultOf(d)

        self.assertEqual({'response': 1}, result)
        request = self._github_requests[0]
        self.assertEqual('GET', request['kwargs']['method'])

    def test_createStatus_default(self):
        """
        When no target_url, description, or context is provided, createStatus()
        creates a status without them.
        as description.
        """
        d = self.repos.createStatus(
            'repo', 'name', 'sha123', 'success')

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        request = self._github_requests[0]
        self.assertEqual('POST', request['kwargs']['method'])
        self.assertNotIn('description', request['kwargs']['post'])
        self.assertNotIn('target_url', request['kwargs']['post'])
        self.assertNotIn('context', request['kwargs']['post'])

    def test_createStatus_explicit(self):
        """
        When no target_url and description is provided, createStatus()
        creates a status linking to API url and having the state name
        as description.
        """
        d = self.repos.createStatus(
            'repo', 'name', 'sha123', 'success',
            description="desc", context="test-context",
            target_url="http://example.com/")

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        request = self._github_requests[0]
        self.assertEqual('POST', request['kwargs']['method'])
        self.assertEqual('desc', request['kwargs']['post']['description'])
        self.assertEqual('http://example.com/',
                         request['kwargs']['post']['target_url'])
        self.assertEqual('test-context', request['kwargs']['post']['context'])


class TestGistsEndpoint(_EndpointTestCase):
    """
    Tests for L{GistsEndpoint}
    """

    def setUp(self):
        super(TestGistsEndpoint, self).setUp()
        self.gists = self.github.gists

    def test_same_gists_object(self):
        """
        The L{GistsEndpoint} is lazily created once.
        """
        self.assertIs(self.github.gists, self.gists)

    def test_create(self):
        """
        Creating a gist with the default options results in a public
        gist with no description.
        """
        gistFiles = {"something.txt": {"content": "some contents"}}

        self.successResultOf(self.gists.create(files=gistFiles))

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='POST',
                                post={"files": gistFiles, "public": True})

    def test_create_with_description(self):
        """
        A description can be given when creating a gist.
        """
        gistFiles = {"something.txt": {"content": "some contents"}}

        self.successResultOf(self.gists.create(files=gistFiles,
                                               description="a description"))

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='POST',
                                post={"files": gistFiles,
                                      "description": "a description",
                                      "public": True})

    def test_create_private(self):
        """
        A private gist can be created.
        """
        gistFiles = {"something.txt": {"content": "some contents"}}

        self.successResultOf(self.gists.create(files=gistFiles,
                                               public=False))

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='POST',
                                post={"files": gistFiles,
                                      "public": False})


class TestPullsEndpoint(_EndpointTestCase):
    """
    Unit tests on PullsEndpoint
    """

    def setUp(self):
        super(TestPullsEndpoint, self).setUp()
        self.pulls = self.github.pulls

    def test_same_pulls_object(self):
        """
        The L{PullsEndpoint} is lazily created once.
        """
        self.assertIs(self.github.pulls, self.pulls)

    def test_edit_fails_when_empty(self):
        """
        edit raises a ValueError when no parameters are provided.
        """
        with self.assertRaises(ValueError):
            self.pulls.edit('repo', 'name', 'number')

    def test_edit_title(self):
        """
        edit, when given only the title, only updates the title.
        """
        d = self.pulls.edit(
            'repo', 'name', 'number', title='some title')

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='PATCH',
                                post={'title': 'some title'})

    def test_edit_body(self):
        """
        edit, when given only the body, only updates the title.
        """
        d = self.pulls.edit(
            'repo', 'name', 'number', body='some body')

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='PATCH',
                                post={'body': 'some body'})

    def test_edit_fails_with_bad_state(self):
        """
        edit raises a ValueError when given an invalid state
        """
        with self.assertRaises(ValueError) as cm:
            self.pulls.edit(
                'repo', 'name', 'number', state='blub')
        self.assertIn('open', cm.exception.message)
        self.assertIn('closed', cm.exception.message)

    def test_edit_state(self):
        """
        edit, when given only the state, only updates the state.
        """
        d = self.pulls.edit(
            'repo', 'name', 'number', state='open')

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='PATCH',
                                post={'state': 'open'})

    def test_edit_all(self):
        """
        edit, when given all parameters, updates all of them.
        """
        d = self.pulls.edit(
            'repo', 'name', 'number',
            title="some title", body="some body", state="closed")

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='PATCH',
                                post={'title': 'some title',
                                      'body': 'some body',
                                      'state': 'closed'})


class TestIssueCommentsEndpoint(_EndpointTestCase):
    """
    Unit tests for IssueCommentsEndpoint.
    """

    def setUp(self):
        super(TestIssueCommentsEndpoint, self).setUp()
        self.comments = self.github.comments

    def test_same_comments_object(self):
        """
        The L{PullsEndpoint} is lazily created once.
        """
        self.assertIs(self.github.comments, self.comments)

    def test_create(self):
        """
        create posts the supplied body.
        """
        d = self.comments.create('repo', 'name', 'number',
                                 'some body')

        self.successResultOf(d)

        self.assertEqual(1, len(self._github_requests))
        self.assertRequestEqual(self._github_requests[0],
                                method='POST',
                                post={'body': 'some body'})


class TestReviewCommentsEndpoint(_EndpointTestCase):
    """
    Unit tests for ReviewCommentsEndpoint.
    """
    def setUp(self):
        super(TestReviewCommentsEndpoint, self).setUp()
        self.reviews = self.github.reviews

    def test_getRepoComments(self):
        """
        All review comments for a repo are retrieved.
        """
        makeRequestAllPages_returns = "makeRequestAllPages"
        calls = []

        def fake_makeRequestAllPages(path):
            calls.append(path)
            return makeRequestAllPages_returns

        self.github.makeRequestAllPages = fake_makeRequestAllPages

        self.assertIs(self.reviews.getRepoComments("user", "name"),
                      makeRequestAllPages_returns)
        self.assertEqual(
            calls, [["repos", "user", "name", "pulls", "comments"]])

    def test_getPullRequestComments(self):
        """
        All comments for a pull request are retrieved.
        """
        makeRequestAllPages_returns = "makeRequestAllPages"
        calls = []

        def fake_makeRequestAllPages(path):
            calls.append(path)
            return makeRequestAllPages_returns

        self.github.makeRequestAllPages = fake_makeRequestAllPages

        self.assertIs(self.reviews.getPullRequestComments("user", "name", 123),
                      makeRequestAllPages_returns)
        self.assertEqual(
            calls, [["repos", "user", "name", "pulls", "123", "comments"]])

    def test_getComment(self):
        """
        The specified comment is retrieved.
        """
        self._github_responses = [{"comment": "body"}]
        d = self.reviews.getComment("repo", "name", 123)

        result = self.successResultOf(d)

        self.assertEqual({"comment": "body"}, result)
        request = self._github_requests[0]
        self.assertEqual(
            ['repos', 'repo', 'name', 'pulls', 'comments', '123'],
            request['args'][0])

    def test_createComment(self):
        """
        A review comment is created according to the specification.
        """
        self._github_responses = [{"comment": "body"}]
        d = self.reviews.createComment(
            "repo", "name",
            pull_number=123,
            body="Nice change",
            commit_id="6dcb09b5b57875f334f61aebed695e2e4193db5e",
            path="file1.txt",
            position=4)

        result = self.successResultOf(d)

        self.assertEqual({"comment": "body"}, result)
        request = self._github_requests[0]
        self.assertEqual(request['args'][0],
                         ['repos', 'repo', 'name', 'pulls', '123', "comments"])
        self.assertEqual("POST", request["kwargs"]["method"])
        self.assertEqual({
            "body": "Nice change",
            "commit_id": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
            "path": "file1.txt",
            "position": 4
        }, request["kwargs"]["data"])

    def test_replyToComment(self):
        """
        A reply to the specified comment is created.
        """
        self._github_responses = [{"comment": "body"}]
        d = self.reviews.replyToComment(
            "repo", "name",
            pull_number=123,
            body="Nice change",
            in_reply_to=4)

        result = self.successResultOf(d)

        self.assertEqual({"comment": "body"}, result)
        request = self._github_requests[0]
        self.assertEqual(request['args'][0],
                         ['repos', 'repo', 'name', 'pulls', '123', "comments"])
        self.assertEqual("POST", request["kwargs"]["method"])
        self.assertEqual({
            "body": "Nice change",
            "in_reply_to": 4,
        }, request["kwargs"]["data"])

    def test_editComment(self):
        """
        The specified comment is edited.
        """
        self._github_responses = [{"comment": "body"}]
        d = self.reviews.editComment(
            "repo", "name",
            comment_id=123,
            body="Nice change")

        result = self.successResultOf(d)

        self.assertEqual({"comment": "body"}, result)
        request = self._github_requests[0]
        self.assertEqual(request['args'][0],
                         ['repos', 'repo', 'name', 'pulls', "comments", "123"])
        self.assertEqual("POST", request["kwargs"]["method"])
        self.assertEqual({"body": "Nice change"}, request["kwargs"]["data"])

    def test_deleteComment(self):
        """
        The specified comment is deleted.
        """
        self._github_responses = [None]
        d = self.reviews.deleteComment(
            "repo", "name",
            comment_id=123)

        result = self.successResultOf(d)

        self.assertEqual(None, result)
        request = self._github_requests[0]
        self.assertEqual(request['args'][0],
                         ['repos', 'repo', 'name', 'pulls', "comments", "123"])
        self.assertEqual("DELETE", request["kwargs"]["method"])
