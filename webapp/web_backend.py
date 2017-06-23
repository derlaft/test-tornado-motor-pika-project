#!/usr/bin/env python
import pika
import uuid
import json
import time
import tornado
import sys

from tornado import gen, web, websocket
from http import HTTPStatus
from rpc_client import RPCClient
from rpc_middleware import RPC


class WebsocketBackend(websocket.WebSocketHandler):

    def initialize(self, rpc):
        self._rpc = rpc

    def reply(self, reply_key, message):
        """ Reply to websocket client

        :param str reply_key: Reply key that identifies this request
        :param message: An object with the response

        """

        message["reply_key"] = reply_key
        encoded_message = json.dumps(message)
        self.write_message(encoded_message)

    def error_reply(self, reply_key, error,
                    status_code=HTTPStatus.BAD_REQUEST):
        """ Reply with an error object (just some syntax sugar) """

        self.reply(reply_key, {"error": error, "error_code": status_code})

    def check_origin(self, origin):
        return True

    @gen.coroutine
    def on_message(self, encoded_message):

        message = json.loads(encoded_message)

        # every message should have a reply code
        if 'reply_key' not in message:
            self.error_reply('', "Reply key is missing")
            return
        reply = message['reply_key']

        # perform various correct checks
        if not self._rpc:  # this generally should not happen, but let it be
            self.error_reply(reply, "Server is starting up",
                             HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if 'action' not in message or 'object' not in message:
            self.error_reply(reply, "Invalid request")
            return

        # any request can have an optional parameters
        params = {}
        if 'params' in message:
            params = message['params']

        # find a handler
        handler = self._rpc.get_handler(action=message['action'],
                                        obj=message['object'])
        if handler is None:
            self.error_reply(reply, "Handler not found")
            return

        # finally! call the middleware handler
        try:
            result = yield handler(params)
        except Exception as e:
            self.error_reply(reply, "Server error (%s)" % str(e),
                             HTTPStatus.REQUEST_TIMEOUT)
            return

        self.reply(reply, {"result": result})
        return

if __name__ == "__main__":
    rabbitURL = 'amqp://localhost:5672/'
    if len(sys.argv) == 2:
        rabbitURL = sys.argv[1]

    conn = RPCClient(rabbitURL)
    rpc = RPC(conn)

    app = web.Application([
        (r'/ws', WebsocketBackend, {"rpc": rpc}),
        (r'/(.*)', web.StaticFileHandler, {'path': './static/'}),
    ])
    app.listen(8081)

    try:
        conn.run()
    except KeyboardInterrupt:
        conn.stop()
