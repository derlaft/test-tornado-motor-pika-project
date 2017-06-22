#!/usr/bin/env python
import pika
import uuid
import json
import time
import tornado

from common.tornado import RabbitMQ
from tornado.queues import Queue
from tornado import gen, web, websocket
from http import HTTPStatus

import traceback


class RPC(object):
    """RPC is a middleware between frontend and service backends.

    Do all the permission-checking and etc stuff there"""

    def __init__(self, rpc):
        self._rpc = rpc

        # define possible routes there
        self._handlers = {
                "users": {
                    "create": self.create_user,
                    "delete": self.delete_user,
                    "retrieve": self.retrieve_user,
                    },
                }

        # define in which service handle each object
        self._stores = {
                "users": "data_repository",
                }

    def get_handler(self, action, obj):
        """ Get action handler

        :param str action: Action (like create/update/exterminate)
        :param str obj: Object to take actions on (like user/task/whatever)

        :return: `None` if nothing is found, handler async func otherwise

        """

        return self._handlers.get(obj, {}).get(action, None)

    def _error(self, err_string):
        return dict(error=err_string)

    def _rpc_path(self, action, obj):
        return "%s.%s.%s" % (
                self._stores[obj],
                obj, action,
                )

    @gen.coroutine
    def create_user(self, params):

        try:
            # make sure only strings pass in there
            # we don't want password={"$gt": null}
            #  in our mongo's queries, right?
            filtered_params = dict(
                # all fields are required
                username=str(params['username']),
                email=str(params['email']),
                password=str(params['password']),
                first_name=str(params['first_name']),
                last_name=str(params['last_name']),
            )

            rpc_result = yield self._rpc.call(
                    self._rpc_path("create", "users"),
                    filtered_params)
            return rpc_result
        except KeyError:
            return self._error("Missing required user field")

    @gen.coroutine
    def delete_user(self, params):

        filtered_params = dict(
                username=str(params.get('username', '')),
                _id=str(params.get('_id', ''))
                )

        rpc_result = yield self._rpc.call(
                self._rpc_path("delete", "users"),
                filtered_params)

        return rpc_result

    @gen.coroutine
    def retrieve_user(self, params):

        filtered_params = dict(
                limit=int(params.get('limit', 20)),
                offset=int(params.get('offset', 0)),
                )

        rpc_result = yield self._rpc.call(
                self._rpc_path("retrieve", "users"),
                filtered_params)

        return rpc_result
