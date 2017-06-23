import unittest
import functools
import tornado

from unittest.mock import patch, Mock
from webapp.rpc_middleware import RPC
from tornado import gen

good_user = dict(
        username='coco',
        password='supersecret',
        email='test@email',
        first_name='lapush',
        last_name='lapushin',
        )


class RPCMiddlewareTest(unittest.TestCase):

    @gen.coroutine
    def test_check_useradd(self):
        """ check a common useradding """

        mock = Mock()
        mock.call.return_value = gen.maybe_future(dict(success=True))
        rpc = RPC(mock)

        result = yield rpc.create_user(good_user)

        self.assertTrue(mock.call.called)
        self.assertTrue(result.get('success', False))
        mock.call.assert_called_with("data_repository.users.create", good_user)

    @gen.coroutine
    def test_check_useradd_bad(self):
        """ check creating with incorrect fields """

        mock = Mock()
        mock.call.return_value = gen.maybe_future(dict(success=True))
        rpc = RPC(mock)

        for k in good_user.keys():
            bad_user = good_user.copy()
            del bad_user[k]

            result = yield rpc.create_user(bad_user)
            self.assertFalse(mock.call.called)
            self.assertFalse(result.get('success', False))
            self.assertIsNot(result.get('error'), None)

    @gen.coroutine
    def test_check_useradd_rpcerr(self):

        """ Check ability to handle RPC errors """

        mock = Mock()
        mock.call.return_value = gen.maybe_future(dict(success=False))
        rpc = RPC(mock)

        result = yield rpc.create_user(good_user)
        self.assertFalse(result.get('success', False))

    @gen.coroutine
    def test_delete_user(self):
        """ Check common deleting """

        mock = Mock()
        mock.call.return_value = gen.maybe_future(dict(success=True))
        rpc = RPC(mock)

        result = yield rpc.delete_user(dict(username='shit'))

    @gen.coroutine
    def test_delete_user_bad(self):

        mock = Mock()
        mock.call.return_value = gen.maybe_future(dict(success=False))
        rpc = RPC(mock)

        result = yield rpc.delete_user(dict(username={}))

        self.assertFalse(result['success'])


if __name__ == "__main__":
    unittest.main()
