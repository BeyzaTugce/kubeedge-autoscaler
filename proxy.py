import json
import logging
import socket
import sys

import requests
from flask import Flask, Response, request
from kubernetes import client, config

# Initialize the Flask application
app = Flask(__name__)

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("debug.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

config.load_kube_config()
api = client.CustomObjectsApi()
core_v1 = client.CoreV1Api()
proxy_service_port = 8280
services = {}

edge_ips = {
    "edge1" : "138.246.237.7",
    "edge2" : "138.246.236.237",
    "edge3" : "138.246.237.5"
}

next_hops = {
    "edge1" : "edge2",
    "edge2" : ["edge1", "edge3"],
    "edge3" : "edge2"
}

def find_service_ports(hostname):
    node_number = int(hostname[-1])
    services["mobilenet"] = 30100 + node_number
    services["squeezenet"] = 30200 + node_number
    services["shufflenet"] = 30300 + node_number

@app.route("/proxy", methods=["POST"])
def forward_request():
    """
    Flas server listening metric requests on port 8280 and forwarding app request to demanding node 
    
    Returns: 
    --------  
    response: Flask Responses
    """
    request_json = request.data.decode()
    msg = json.loads(request_json)
    node = msg["node"]
    app_type = msg["app"]
    
    hostname = socket.gethostname()
    host_ip = edge_ips[hostname]

    if node == hostname:
        find_service_ports(hostname)
        port = services[app_type]
        try:
            res_init = requests.post(f"http://{host_ip}:{port}/init")
            res = requests.post(f"http://{host_ip}:{port}/run")
            logging.info("Local execution of %s in %s.", app_type, node)
        except client.ApiException as exc:
            logging.error("Error while locally executing %s in %s", app_type, node)
            raise exc
    else:
        if hostname == "edge2":
            next_hop_ip = edge_ips[node]
        else:
            next_hop_ip = edge_ips[next_hops[hostname]]
        try:
            req = json.dumps({"node": node, "app": app_type})
            res = requests.post(f"http://{next_hop_ip}:{proxy_service_port}/proxy", data=req)
            logging.info("Forward the request of %s to %s.", app_type, node)
        except client.ApiException as exc:
            logging.error("Error while forwarding th request of %s to %s", app_type, node)
            raise exc
        
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8280)
