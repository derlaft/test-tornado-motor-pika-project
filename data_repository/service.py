import motor
import time
import pika
import json

from tornado import gen
from email.utils import parseaddr
from bson.objectid import ObjectId

required_fields = ["username", "email", "password"]


class UserService:
    def __init__(self, mongo_addr):
        """ Connect to database; create a shortcut for collection.

        :param str mongo_addr: URL for a mongo connection.

        """

        self.mongo = motor.motor_tornado.MotorClient(mongo_addr)
        self.db = self.mongo.data_repository
        self.users = self.db.users

        # is there a need to call this every time?
        self.users.create_index("username", unique=True)

    # create user api func
    @gen.coroutine
    def create(self, user):
        """ Create user in the datastore.

        :param user: JSON with user document.
        :return dict: request result, with "success"=True

        """

        # check if user has all the needed fields
        for field in required_fields:
            if field not in user:
                raise Exception('User has not enough fields')

        # check email for correctness
        if parseaddr(user['email'])[1] != user['email'] or '@' not in user['email']:
            raise Exception('Invalid email')

        result = yield self.users.insert_one(user)
        return {"success": result.inserted_id is not None, "inserted_id": str(result.inserted_id)}
    
    @gen.coroutine
    def delete(self, params):
        """ Delete user from datastore.

        :param str username: Username for user to delete
        :param str _id: Database ID for user to delete

        """

        delete_by = None

        if 'username' in params and len(params['username']) > 0:
            # delete user by name
            delete_by = {'username': params['username']}

        elif '_id' in params and len(params['_id']) > 0:
            # delete user by objectid
            delete_by = {'_id': ObjectId(params['_id'])}

        result = yield self.users.delete_one(delete_by)
        return {"success": result.deleted_count == 1}

    @gen.coroutine
    def retrieve(self, params):
        """ Get user from datastore
        
        :param int limit: How much to retrieve
        :param int offset: Retrieve offset
        """

        limit = params.get('limit', 20)
        if limit > 100: limit = 100

        offset = params.get('offset', 0)

        users = yield self.users.find().skip(offset).to_list(limit+1)
        has_more = len(users) == limit+1

        # strip the last remaining one we use for pagination
        if len(users) > limit:
            users = users[:-1]

        # replace ObjectID in result (it's not json-serialize-able)
        # I would better filter out the whole result; but I've written 
        # a lot already
        for user in users:
            user['_id'] = str(user['_id'])

        return dict(
                users=users[:-1],
                has_more=has_more,
                )

    def handlers(self):
        """ Returns RPC routes that are handled by this object """
        return {
                "data_repository.users.create": self.create,
                "data_repository.users.delete": self.delete,
                "data_repository.users.retrieve": self.retrieve,
        }

    # stop all network activity gracefully
    def stop(self):
        self.mongo.close()
