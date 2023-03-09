import json
import logging
import os
import socket
import sys

import requests
from dotenv import load_dotenv
from flask import Flask, Response, request
from kubernetes import client, config

load_dotenv()

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
    "edge1": os.environ["EDGE-1"],
    "edge2": os.environ["EDGE-2"],
    "edge3": os.environ["EDGE-3"]
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
    services["binaryalert"] = 30400 + node_number

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
    request_start = float(msg["request_start"])
    
    hostname = socket.gethostname()
    host_ip = edge_ips[hostname]

    if node == hostname:
        find_service_ports(hostname)
        port = services[app_type]
        try:
            req = json.dumps({"request_start": request_start})
            res_init = requests.post(f"http://{host_ip}:{port}/init", data=req)
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
            req = json.dumps({"node": node, "app": app_type, "request_start": request_start})
            res = requests.post(f"http://{next_hop_ip}:{proxy_service_port}/proxy", data=req)
            logging.info("Forward the request of %s to %s.", app_type, node)
        except client.ApiException as exc:
            logging.error("Error while forwarding th request of %s to %s", app_type, node)
            raise exc
        
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8280)
