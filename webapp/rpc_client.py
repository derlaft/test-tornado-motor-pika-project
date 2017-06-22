#!/usr/bin/env python
import pika
import uuid
import json
import time
import tornado
import functools

from common.tornado import RabbitMQ
from tornado.queues import Queue
from tornado import gen, web, websocket
from http import HTTPStatus

class RPCClient(RabbitMQ):
    """ Client-sender to RabbitMQ stuff """
    def __init__(self, amq_url, timeout=60):
        RabbitMQ.__init__(self, amq_url)

        self._reply_queues = dict()
        self._ioloop = tornado.ioloop.IOLoop.current()
        self._callback_queue = "rpc-answer-%s" % str(uuid.uuid4())
        self._timeout = timeout

    def on_exchange_declareok(self, unused_frame):
        """ declare callback queue for rpc calls """

        result = self.channel().queue_declare(queue=self._callback_queue, callback=self.on_queue_declareok)

    @gen.coroutine
    def call(self, action, body):
        """ Do the actual calling 
        
        :param str action: action to perform (CRUD for example)
        :param str body: an object to send (will be json-encoded)

        """

        # queue is used to send result back to this routine
        corr_id = str(uuid.uuid4())
        queue = Queue(maxsize=1)
        self._reply_queues[corr_id] = queue

        # send message       
        self.channel().basic_publish(
                exchange='',
                routing_key=action,
                properties=pika.BasicProperties(
                    correlation_id=corr_id,
                    reply_to = self._callback_queue,
                    ),
                body=json.dumps(body))
        
        # add timeout callback
        self._ioloop.add_timeout(time.time() + self._timeout, functools.partial(
            self._on_timeout,
            queue=queue,
            correlation_id=corr_id,
            ))

        # retrieve result back
        result = yield queue.get()
        queue.task_done()
        
        if 'timeout_error' in result:
            raise TimeoutError(result['error'])

        return result

    @gen.coroutine
    def _on_timeout(self, queue, correlation_id):
        # if this is still present at this moment -- we should return timeout err
        if correlation_id in self._reply_queues:
            self._reply_queues[correlation_id].put({
                "error": "Timeout has passed",
                "timeout_error": True
                })
            del self._reply_queues[correlation_id]

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """ Handle new messages and put them in the right queues """
        print("on msg")

        corr_id = properties.correlation_id

        # check if queue still exists (else timeout is passed)
        if corr_id in self._reply_queues:
            decoded_body = json.loads(body)
            self._reply_queues[corr_id].put(decoded_body)
            del self._reply_queues[corr_id]
        else:
            logger.getLogger().debug(
                    "Skipped response, corr_id=%s. timeout passed?" % corr_id
                    )

