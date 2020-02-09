###############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) Tavendo GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
###############################################################################

from __future__ import absolute_import
import signal

import six

from autobahn.wamp.types import ComponentConfig
from autobahn.websocket.util import parse_url
from autobahn.asyncio.websocket import WampWebSocketClientFactory

try:
    import asyncio
except ImportError:
    # Trollius >= 0.3 was renamed to asyncio
    # noinspection PyUnresolvedReferences
    import trollius as asyncio

import txaio
txaio.use_asyncio()

__all__ = (
    'ApplicationRunner'
)


class ApplicationRunner(object):

    def __init__(self, url, realm, extra=None, serializers=None,
                 debug=False, debug_app=False,
                 ssl=None):

        assert(type(url) == six.text_type)
        assert(type(realm) == six.text_type)
        assert(extra is None or type(extra) == dict)
        self.url = url
        self.realm = realm
        self.extra = extra or dict()
        self.serializers = serializers
        self.debug = debug
        self.debug_app = debug_app
        self.ssl = ssl

    def run(self, make):
        # 1) factory for use ApplicationSession
        def create():
            cfg = ComponentConfig(self.realm, self.extra)
            try:
                session = make(cfg)
            except Exception as e:
                # the app component could not be created .. fatal
                print(e)
                asyncio.get_event_loop().stop()
            else:
                session.debug_app = self.debug_app
                return session

        isSecure, host, port, resource, path, params = parse_url(self.url)

        if self.ssl is None:
            ssl = isSecure
        else:
            if self.ssl and not isSecure:
                raise RuntimeError(
                    'ssl argument value passed to %s conflicts with the "ws:" '
                    'prefix of the url argument. Did you mean to use "wss:"?' %
                    self.__class__.__name__)
            ssl = self.ssl

        # 2) create a WAMP-over-WebSocket transport client factory
        transport_factory = WampWebSocketClientFactory(create, url=self.url, serializers=self.serializers)
        transport_factory.setProtocolOptions(failByDrop=False, openHandshakeTimeout=90, closeHandshakeTimeout=5)

        # 3) start the client
        loop = asyncio.get_event_loop()
        txaio.use_asyncio()
        txaio.config.loop = loop
        coro = loop.create_connection(transport_factory, host, port, ssl=ssl)
        (transport, protocol) = loop.run_until_complete(coro)

        try:
            loop.add_signal_handler(signal.SIGTERM, loop.stop)
        except NotImplementedError:
            # signals are not available on Windows
            pass

        # 4) now enter the asyncio event loop
        # try:
        #     loop.run_forever()
        # except KeyboardInterrupt:
            # wait until we send Goodbye if user hit ctrl-c
            # (done outside this except so SIGTERM gets the same handling)
        #     pass

        # give Goodbye message a chance to go through, if we still
        # have an active session
        # if protocol._session:
        #     loop.run_until_complete(protocol._session.leave())

        # loop.close()
