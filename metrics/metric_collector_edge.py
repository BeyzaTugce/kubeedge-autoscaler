import json
import logging
import os
import sys

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

def find_ready_pod_ips(label):
    """
    Create the dictionary mapping pod names to their IPs
    """
    pod_ips = {}
    try:
        pod_list = core_v1.list_namespaced_pod(namespace="autoscaler", label_selector=label)
        for pod in pod_list.items:
            if pod.status.phase != "Running":
                continue
            pod_ips[pod.metadata.name] = pod.status.pod_ip
        logging.info("Pod IPs have been successfully read.")
    except client.ApiException as exc:
        if exc.status == 404:
            return None
        logging.error("Error while reading pod IPs")
        raise exc
    return pod_ips


@app.route("/metrics", methods=["POST"])
def collect_metrics():
    """
    Flas server listening metric requests on port 8180 and collecting pod metrics for demanding app 
    
    Returns: 
    --------  
    response: Flask Responses
    """
    request_json = request.data.decode()
    msg = json.loads(request_json)
    node = msg["node"]
    app_type = msg["app"]
    name = None
    port = None

    if app_type == "mobilenet":
        port = 8080
        name = "-".join(("mobilenet-deployment", node))
    elif app_type == "squeezenet":
        port = 8080
        name = "-".join(("squeezenet-deployment", node))
    elif app_type == "shufflenet":
        port = 8080
        name = "-".join(("shufflenet-deployment", node))
    elif app_type == "binaryalert":
        port = 8080
        name = "-".join(("binaryalert-deployment", node))
    
    label = f"app={app_type}-{node}"
    pod_ips = find_ready_pod_ips(label)

    try:
        resource = api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace="autoscaler",
            plural="pods",
            label_selector=label
        )
        logging.info("Deployment %s has been successfully read.", name)
    except client.ApiException as exc:
        if exc.status == 404:
            logging.info("Deployment %s has not been found.", name)
            res = json.dumps({
                "pod_number": 0,
                "pod_instances": {}
            })
            return Response(response=res, status=404)
        logging.error("Error while reading deployment %s", name)
        raise exc

    pod_num = len(resource["items"])
    pod_instances = {}

    for pod in resource["items"]:
        pod_name = pod['metadata']['name']
        if pod_name not in pod_ips:
            continue
        pod_ip = pod_ips[pod_name]
        request_count = 0
        response_time = 0
        p10_res_time = 0
        p50_res_time = 0
        p90_res_time = 0
        p50_all_res_times = 0
        p90_all_res_times = 0

        with os.popen(f"kubectl exec -n autoscaler -it {pod_name} -- curl {pod_ip}:{port}/metrics") as f:
            metrics = f.readlines()
            if len(metrics) > 58:
                request_count = float(metrics[38].split()[-1])
                response_time = float(metrics[44].split()[-1])
                p10_res_time = float(metrics[47].split()[-1])
                p50_res_time = float(metrics[50].split()[-1])
                p90_res_time = float(metrics[53].split()[-1])
                #request_density = float(metrics[56].split()[-1])
                #p10_req_density = float(metrics[59].split()[-1])
                #p50_req_density = float(metrics[62].split()[-1])
                #p90_req_density = float(metrics[65].split()[-1])
                p50_all_res_times = float(metrics[68].split()[-1])
                p90_all_res_times = float(metrics[71].split()[-1])

        pod_info = {
            "req_count": request_count,
            "res_time": response_time, 
            "p10_res_time": p10_res_time,
            "p50_res_time": p50_res_time, 
            "p90_res_time": p90_res_time,
            "p50_all_res_times": p50_all_res_times, 
            "p90_all_res_times": p90_all_res_times
        }
        pod_instances[pod_name] = pod_info

    res = json.dumps({
        "pod_number": pod_num,
        "pod_instances": pod_instances
    })
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8180)
    