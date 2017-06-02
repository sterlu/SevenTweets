import json
import functools
import os
import requests

from flask import Flask
from flask import request

from seventweets import storage
from seventweets.exceptions import error_handled, NotFound, BadRequest, Unauthorized

Storage = storage.Storage()
Nodes = storage.Nodes()

self_node_name = os.environ['NODE_NAME'] if 'NODE_NAME' in os.environ else 'dev'
self_node_address = os.environ['NODE_ADDRESS'] if 'NODE_ADDRESS' in os.environ else 'sbg.dev'

app = Flask(__name__)


def protected_endpoint(f):
    @functools.wraps(f)
    def inner_f(*args, **kwargs):
        request_data = json.loads(request.data)
        if 'api_key' in request_data:
            api_keys = Storage.get_all_keys()
            print(api_keys)
            print(request_data['api_key'])
            if request_data['api_key'] in api_keys:
                return f(*args, **kwargs)
        raise Unauthorized("Unauthorized")
    return inner_f


def scan_network():
    new_node = Nodes.get_new()
    while new_node:
        if new_node['name'] != self_node_name:
            print("Fetching info from node " + new_node['name'])
            try:
                res = requests.post("http://" + new_node['address'] + '/register/', json={
                    "name": self_node_name,
                    "address": self_node_address
                })
                returned_nodes = json.loads(res.text)
                print("Discovered new nodes: ")
                print(returned_nodes)
                for node in returned_nodes:
                    if node['address'] != self_node_address and node['name'] != self_node_name:
                        print("Registering discovered node: ")
                        print(node)
                        Nodes.register_node(node['name'], node['address'])
            except Exception:
                print(Exception)
        Nodes.mark_as_checked(new_node['name'], new_node['address'])
        new_node = Nodes.get_new()


@app.route("/tweets/", methods=["GET"])
def all_tweets():
    return json.dumps(Storage.get_all())


@app.route("/tweets/<int:tweet_id>", methods=["GET"])
@error_handled
def single_tweet(tweet_id):
    tweet = Storage.get_by_id(tweet_id)
    if tweet:
        return json.dumps(tweet)
    else:
        raise NotFound("Tweet not found")


@app.route("/tweets/", methods=["POST"])
@error_handled
@protected_endpoint
def save_tweet():
    if not request.data:
        raise BadRequest("Data not sent")
    request_data = json.loads(request.data)
    if 'tweet' in request_data:
        Storage.save_tweet(request_data["tweet"])
        return "Tweet saved"
    else:
        raise BadRequest("Missing tweet content")


@app.route("/tweets/", methods=["DELETE"])
@error_handled
@protected_endpoint
def delete_tweet():
    if not request.data:
        raise BadRequest("Data not sent")
    request_data = json.loads(request.data)
    if 'id' in request_data:
        if Storage.delete_tweet((int)(request_data["id"])):
            return "Tweet deleted", 204
        else:
            raise NotFound("Tweet not found")
    else:
        raise BadRequest("Missing tweet content")


@app.route("/search/<query>", methods=["GET"])
@error_handled
def search(query):
    # TODO: switch to GET params
    # TODO: add created_from, created_to and all
    # TODO: add external search
    return json.dumps(Storage.search(query))


@app.route("/join_network/", methods=["POST"])
@error_handled
def join_network():
    if not request.data:
        raise BadRequest("Data not sent")
    request_data = json.loads(request.data)
    if request_data['name'] and request_data['address']:
        print("Joining network through node '" + request_data['name'] + "' at " + request_data['address'])
        Nodes.register_node(request_data['name'], request_data['address'])
        scan_network()
        return "Joined"
    else:
        raise BadRequest("Missing parameters")


@app.route("/network_status/", methods=["GET"])
@error_handled
def network_status():
    return json.dumps(Nodes.get_all())


@app.route("/register/", methods=["POST"])
@error_handled
def register_node():
    if not request.data:
        raise BadRequest("Data not sent")
    request_data = json.loads(request.data)
    if request_data['name'] and request_data['address']:
        if request_data['address'] != self_node_address and request_data['name'] != self_node_name:
            print("New node '" + request_data['name'] + "' at " + request_data['address'])
            Nodes.register_node(request_data['name'], request_data['address'])
            scan_network()
        return json.dumps(Nodes.get_all())
    else:
        raise BadRequest("Missing parameters")


@app.route("/register/<node_name>", methods=["DELETE"])
@error_handled
def delete_node(node_name):
    Nodes.delete_node(node_name)
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0")
