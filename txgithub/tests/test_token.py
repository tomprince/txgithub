"""
Tests for Twisted GitHub API bindings.
"""
from collections import namedtuple
import json
import urlparse
from twisted.internet.defer import Deferred
from twisted.trial.unittest import SynchronousTestCase

from txgithub.constants import HOSTED_BASE_URL
from txgithub.token import createToken


_GetPageCalls = namedtuple("_GetPageCalls",
                           ["url", "method", "postdata", "headers"])


class TestGithubPageGetter(SynchronousTestCase):
    """
    Tests for L{createToken}.
    """

    def setUp(self):
        self.getPage_calls = []
        self.getPage_deferred = Deferred()

        self.user = "user"
        self.password = "password"
        self.note = "note"
        self.note_url = "note url"
        self.scopes = "scopes"

        self.body = ('{"note": "note", "scopes": "scopes",'
                     ' "note_url": "note url"}')
        self.headers = {'Authorization': 'Basic dXNlcjpwYXNzd29yZA=='}

    def fake_getPage(self, url, method, postdata, headers):
        """
        A fake L{twisted.web.client.getPage} implementation.
        """
        self.getPage_calls.append(_GetPageCalls(url=url,
                                                method=method,
                                                postdata=postdata,
                                                headers=headers))
        return self.getPage_deferred

    def extract_getPage_call(self):
        """
        Ensure that only one call to getPage occurred and return it
        """
        self.assertEqual(len(self.getPage_calls), 1)
        return self.getPage_calls[0]

    def assertURL(self, base_url, actual_url):
        """
        Verify the construction of the token URL.
        """
        self.assertEqual(urlparse.urljoin(base_url, "authorizations"),
                         actual_url)

    def createToken(self, baseURL=None):
        """
        A wrapper around L{createToken} that ensures the fixture data
        and fake is passed in.
        """
        kwargs = {"_getPage": self.fake_getPage}
        if baseURL:
            kwargs["baseURL"] = baseURL
        return createToken(self.user,
                           self.password,
                           self.note,
                           self.note_url,
                           self.scopes,
                           **kwargs)

    def test_createToken_default_url(self):
        """
        The default URL is used if none is provided.
        """
        self.createToken()
        self.assertEqual(len(self.getPage_calls), 1)
        self.assertURL(HOSTED_BASE_URL, self.extract_getPage_call().url)

    def test_createToken_baseURL(self):
        """
        The provided URL is used.
        """
        baseURL = "https://something.com"
        self.createToken(baseURL=baseURL)
        self.assertEqual(len(self.getPage_calls), 1)
        self.assertURL(baseURL, self.extract_getPage_call().url)

    def test_createToken_baseURL_trailing_slash(self):
        """
        The provided URL is used even if it has a trailing slash.
        """
        baseURL = "https://something.com/"
        self.createToken(baseURL=baseURL)
        self.assertURL(baseURL, self.extract_getPage_call().url)

    def test_createToken_post(self):
        """
        The request is a POST.
        """
        self.createToken()
        self.assertEqual(self.extract_getPage_call().method, "POST")

    def test_createToken_body_ok(self):
        """
        The provided content comprises the request's body.
        """
        self.createToken()
        self.assertEqual(self.body, self.extract_getPage_call().postdata)

    def test_createToken_basic_auth(self):
        """
        The user and password are used in HTTP Basic Authorization.
        """
        self.createToken()
        self.assertEqual(self.extract_getPage_call().headers, self.headers)

    def test_json_result(self):
        """
        The response's body is deserialized as JSON and the "token"
        property returned.
        """
        value = "value"
        response = self.createToken()
        self.getPage_deferred.callback(json.dumps({"token": value}))
        self.assertEqual(self.successResultOf(response), value)
