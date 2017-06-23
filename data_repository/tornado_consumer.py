import pika
import logging
import time
import functools
import tornado
import json
import sys

from tornado import gen
from pika import adapters

from service import UserService
from common.tornado import RabbitMQ

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)


class RPCConsumer(RabbitMQ):

    """RPCConsumer will handle all the messages based by handlers.

    Handler is an object with .handlers() method.
    This method should return a dict(string->tornado.gen.coroutine).
    Messages will be sent to handlers decided by their routing messages.

    """
    EXCHANGE = 'test'
    EXCHANGE_TYPE = 'topic'
    ROUTING_KEY = ''

    def __init__(self, amqp_url, *handlers):
        """Create a new instance of the consumer class, passing in the AMQP
        URL used to connect to RabbitMQ.

        :param str amqp_url: The AMQP url to connect with
        :param list of handle: Dictionary of handlers

        """

        self._consumer_tags = []

        RabbitMQ.__init__(self, amqp_url)

        # save our handlers for ruture use
        self._handlers = {}
        for handle in handlers:
            for k, v in handle.handlers().items():
                self._handlers[k] = v

    def on_exchange_declareok(self, unused_frame):
        """Register all the queues for communication

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response

        """
        LOGGER.debug('Exchange declared')

        for queue in self._handlers.keys():
            self._channel.queue_declare(self.on_queue_declareok, queue)

        RabbitMQ.on_exchange_declareok(self, unused_frame)

    def on_queue_declareok(self, method_frame):
        """Bind all needed queues. Not sure if needed.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """

        for queue in self._handlers.keys():
            LOGGER.debug('Binding %s to %s with %s',
                         self.EXCHANGE, queue, self.ROUTING_KEY)
            self._channel.queue_bind(self.on_bindok, queue,
                                     self.EXCHANGE, self.ROUTING_KEY)

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """Handle all messages, in async, reply to them.

        :param pika.channel.Channel unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param str|unicode body: The message body

        """
        LOGGER.debug('Received message # %s from %s: %s',
                     basic_deliver.delivery_tag, properties.app_id, body)

        if basic_deliver.routing_key in self._handlers:
            # future that will handle this request,
            #   and a callback invoked to handle it
            future = self._wrap_handler(
                    self._handlers[basic_deliver.routing_key],
                    body)
            # functools.partial is used to invoke future by name
            #   without creating a nested func
            callback = functools.partial(
                    self._on_reply,
                    reply_tag=basic_deliver.delivery_tag,
                    answer_tag=properties.reply_to,
                    correlation_id=properties.correlation_id)

            # get ioloop and exec it
            self._ioloop.add_future(future, callback)
        else:
            LOGGER.debug('Skipping non-handed message with request to %s' %
                         basic_deliver.routing_key)

    @gen.coroutine
    def _wrap_handler(self, handler, body):
        """This method is used to pass encoded body to a handler and return it's value.
        Errors are handled and returned via "error" field.

        :param handler tornado.gen.coroutine handler: will be awaited
        :param str|unicode body: Encoded to JSON message body
        :return: non-encoded (it may be still used) JSON handler result

        """
        try:
            decoded_body = json.loads(body)
            result = yield handler(decoded_body)
            return result
        except Exception as e:
            return {"error": str(e)}

    @gen.coroutine
    def _on_reply(self, cb, reply_tag='', answer_tag='', correlation_id=''):
        """A callback to handle results

        :param cb tornado.gen.coroutine: The callback to expect.
        :param reply_tag str: RabbitMQ ack tag
        :param answer_tag str: RabbitMQ reply tag
        :param answer_tag str: RabbitMQ correlation ID

        """
        result = yield cb
        encoded_result = json.dumps(result)

        # We want to have some discard ability for a really fatal situations
        # however, I still have no idea how to select Exceptions
        #  (handled by _wrap_handler, for example) that are really fatal
        # and corresponding request should not be marked
        # as acked. It is practically impossible to handle every exception in
        # python. That is one thing I like implemented good in go.
        # So, I am not really sure, but it appears this `discard` is pretty
        # useless in general
        if "discard" in result and result["discard"]:
            LOGGER.debug('Discarding result to %s' % reply_tag)
            return

        # I really would like to see a way to make these two actions atomic
        self._channel.basic_publish(
                exchange='',
                routing_key=answer_tag,
                properties=pika.BasicProperties(correlation_id=correlation_id),
                body=encoded_result)
        self._channel.basic_ack(reply_tag)

    def start_consuming(self):
        """This method sets up the consuming itself

        """

        for queue in self._handlers.keys():
            self._consumer_tags += self._channel.basic_consume(self.on_message,
                                                               queue=queue)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    mongoURL = 'mongodb://localhost:27017'
    rabbitURL = 'amqp://localhost:5672/'

    if len(sys.argv) == 3:
        mongoURL = sys.argv[1]
        rabbitURL = sys.argv[2]

    users = UserService(mongoURL)
    worker = RPCConsumer(rabbitURL, users)

    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop()
        users.stop()
