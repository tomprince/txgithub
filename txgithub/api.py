# This file is part of txgithub.  txgithub is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import re
import json
from twisted.python import log
from twisted.internet import defer, ssl
from twisted.web import client

from txgithub.constants import HOSTED_BASE_URL

class _GithubPageGetter(client.HTTPPageGetter):

    def handleStatus_204(self):
        # github returns 204 for e.g., DELETE operations
        self.handleStatus_200()

class _GithubHTTPClientFactory(client.HTTPClientFactory):

    protocol = _GithubPageGetter

    # dont' log about starting and stopping
    noisy = False

class GithubApi(object):
    # Interface to the github API, using
    # - API v3
    # - optional user/pass auth (token is not available with v3)
    # - async API

    def __init__(self, oauth2_token, baseURL=None):
        self._baseURL = baseURL or HOSTED_BASE_URL
        self.oauth2_token = oauth2_token
        self.rateLimitWarningIssued = False
        self.contextFactory = ssl.ClientContextFactory()

    def _makeHeaders(self):
        assert self.oauth2_token, "no token specified"
        return { 'Authorization' : 'token ' + self.oauth2_token }

    def makeRequest(self, url_args, post=None, method='GET', page=0):
        headers = self._makeHeaders()

        url = self._baseURL
        url += '/'.join(url_args)
        if page:
            url += "?page=%d" % page

        postdata = None
        if post:
            postdata = json.dumps(post)

        log.msg("fetching '%s'" % (url,), system='github')
        factory = _GithubHTTPClientFactory(url, headers=headers,
                    postdata=postdata, method=method,
                    agent='txgithub', followRedirect=0,
                    timeout=30)
        from twisted.internet import reactor
        reactor.connectSSL(factory.host, factory.port, factory,
                           self.contextFactory)
        d = factory.deferred
        @d.addCallback
        def check_ratelimit(data):
            self.last_response_headers = factory.response_headers
            remaining = int(factory.response_headers.get(
                                    'x-ratelimit-remaining', [0])[0])
            if remaining < 100 and not self.rateLimitWarningIssued:
                log.msg("warning: only %d Github API requests remaining "
                        "before rate-limiting" % remaining)
                self.rateLimitWarningIssued = True
            return data
        @d.addCallback
        def un_json(data):
            if data:
                return json.loads(data)
        return d

    link_re = re.compile('<([^>]*)>; rel="([^"]*)"')
    @defer.inlineCallbacks
    def makeRequestAllPages(self, url_args):
        page = 0
        data = []
        while True:
            data.extend((yield self.makeRequest(url_args, page=page)))
            if 'link' not in self.last_response_headers:
                break
            link_hdr = self.last_response_headers['link']
            for link in self.link_re.findall(link_hdr):
                if link[1] == 'next':
                    # note that we don't *use* the page -- why bother?
                    break
            else:
                break # no 'next' link, so we're done
            page += 1
        defer.returnValue(data)

    _repos = None
    @property
    def repos(self):
        if not self._repos:
            self._repos = ReposEndpoint(self)
        return self._repos

    _gists = None
    @property
    def gists(self):
        if not self._gists:
            self._gists = GistsEndpoint(self)
        return self._gists


class BaseEndpoint(object):

    def __init__(self, api):
        self.api = api


class ReposEndpoint(BaseEndpoint):

    @defer.inlineCallbacks
    def getEvents(self, repo_user, repo_name, until_id=None):
        """Get all repository events, following paging, until the end
        or until UNTIL_ID is seen.  Returns a Deferred."""
        done = False
        page = 0
        events = []
        while not done:
            new_events = yield self.api.makeRequest(
                    ['repos', repo_user, repo_name, 'events'],
                    page)

            # terminate if we find a matching ID
            if new_events:
                for event in new_events:
                    if event['id'] == until_id:
                        done = True
                        break
                    events.append(event)
            else:
                done = True

            page += 1
        defer.returnValue(events)

    def getHooks(self, repo_user, repo_name):
        """Get all repository hooks.  Returns a Deferred."""
        return self.api.makeRequestAllPages(
            ['repos', repo_user, repo_name, 'hooks'])

    def getHook(self, repo_user, repo_name, hook_id):
        """
        GET /repos/:owner/:repo/hooks/:id

        Returns the Hook.
        """
        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'hooks', str(hook_id)],
            method='GET',
            )

    def createHook(self, repo_user, repo_name, name, config, events, active):
        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'hooks'],
            method='POST',
            post=dict(name=name, config=config, events=events, active=active))

    def editHook(self, repo_user, repo_name, hook_id, name, config,
            events=None, add_events=None, remove_events=None, active=None):
        """
        PATCH /repos/:owner/:repo/hooks/:id

        :param hook_id: Id of the hook.
        :param name:  The name of the service that is being called.
        :param config: A Hash containing key/value pairs to provide settings
                       for this hook.
        """
        post = dict(
                name=name,
                config=config,
                )
        if events is not None:
            post['events'] = events

        if add_events is not None:
            post['add_events'] = add_events

        if remove_events is not None:
            post['remove_events'] = remove_events

        if active is not None:
            post['active'] = active

        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'hooks', str(hook_id)],
            method='PATCH',
            post=post,
            )

    def testHook(self, repo_user, repo_name, hook_id):
        """
        POST /repos/:owner/:repo/hooks/:id/tests

        Response headers:
            Status: 204 No Content
            X-RateLimit-Limit: 5000
            X-RateLimit-Remaining: 4999
        Response content:
            None
        """
        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'hooks', str(hook_id), 'tests'],
            method='POST',
            )

    def deleteHook(self, repo_user, repo_name, id):
        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'hooks', str(id)],
            method='DELETE')

    def getStatuses(self, repo_user, repo_name, sha):
        """
        :param sha: Full sha to list the statuses from.
        :return: A defered with the result from GitHub.
        """
        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'statuses', sha],
            method='GET')

    def createStatus(self,
            repo_user, repo_name, sha, state, target_url=None,
            description=None):
        """
        :param sha: Full sha to create the status for.
        :param state: one of the following 'pending', 'success', 'error'
                      or 'failure'.
        :param target_url: Target url to associate with this status.
        :param description: Short description of the status.
        :return: A defered with the result from GitHub.
        """
        if description is None:
            description = state

        if target_url is None:
            target_url = 'http://developer.github.com/v3/repos/statuses/'

        return self.api.makeRequest(
            ['repos', repo_user, repo_name, 'statuses', sha],
            method='POST',
            post=dict(
                state=state,
                target_url=target_url,
                description=description,
                ))


class GistsEndpoint(BaseEndpoint):
    def create(self, files, description=None, public=True):
        data = { 'files': files, 'public': bool(public) }
        if description is not None:
            data['description'] = description
        return self.api.makeRequest(
                ['gists'],
                method='POST',
                post=data)
