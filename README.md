# test-tornado-motor-pika-project

This is a sample python microservice project. It uses tornado, piko (for RabbitMQ queue), motor (async MongoDB library). 

### docker-compose.yaml

Is used to run mongodb and rabbitmq (that are excepted to run at localhost at default ports).

### How to run

```
docker-compose up -d
export PYTHONPATH=$PWD
python3 data_repository/service.py # run storage service
python3 webapp/web_backend.py # run web backend service
```

Web backend should listen at `localhost:8081`. Visit http://localhost:8081/index.html for a simple web UI.

### File index

* `common/tornado.py`: Base class (`RabbitMQ`) for all the RabbitMQ-listening stuff. Heavily based on the [official docs](http://pika.readthedocs.io/en/0.10.0/examples/tornado_consumer.html).
* `webapp/rpc_client.py`: the class (inherited from `common.Tornado.RabbitMQ`) that implements RPC client over RabbitMQ.
* `webapp/rpc_middleware.py`: the service logic (input checking, probably auth and etc), allows to declare multiple RPC endpoints.
* `test/test_rpc_middleware`: unit-tests for this class.
* `webapp/web_backend.py`: the code that is directly involved in communicating with web clients: routes, websocket handling, etc. Also contains this service entrypoint.
* `data_repository/service.py`: contains the end-service logic (in this case -- communicating with database).
* `data_repository/tornado_consumer.py`: RPC server implemented over `common.Tornado.RabbitMQ`, allows to connect multiple classes like `data_repository.service.UserService`.


### Issue list

* Pydoc notations are present, but not tested (and apparently are pretty broken).
* I have a feeling that I'm not using all the power of python's `unittest.Mock`, so I've published some tests, but don't feel right to continue in this way.
* Broadcast messages are not implemented, but that's not a serious problem.
* Frontend <-> Backend websocket communication introduces a brand-new bycycle protocol heavily influenced by [JSON PURE](https://mmikowski.github.io/json-pure/), but with all the unneeded stuff removed. It's not a problem to use anything else however.
* Config files are not implemented, because this is trivial and lame. Anyway, the real environments use another complicated and bloated stuff like `etcd` and etc.
* This is written in a (shitty) English. I am not sure if you (a potential employer) can read this.
* I must mention that service like this takes much less time, effort, pain and lines of code to be implemented in go. 
