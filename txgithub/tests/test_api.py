"""
Tests for Twisted GitHub API bindings.
"""
from twisted.trial.unittest import SynchronousTestCase

from twisted.internet.defer import succeed

from txgithub.api import GithubApi as GitHubAPI


class TestReposEndpoint(SynchronousTestCase):
    """
    Unit tests for ReposEndpoint.
    """

    def _mock_makeRequest(self, *args, **kwargs):
        try:
            self._github_requests.append({'args': args, 'kwargs': kwargs})
            response = self._github_responses.pop()
            return succeed(response)
        except IndexError:
            return succeed({})

    def setUp(self):
        super(TestReposEndpoint, self).setUp()
        self._github_responses = []
        self._github_requests = []
        self.github = GitHubAPI(oauth2_token='fake-token')
        self.github.makeRequest = self._mock_makeRequest
        self.repos = self.github.repos

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
