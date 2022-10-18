import json
import logging
import os

from flask import Flask, Response, request
from kubernetes import client, config

# Initialize the Flask application
app = Flask(__name__)

config.load_kube_config()
api = client.CustomObjectsApi()
core_v1 = client.CoreV1Api()
pod_ips = {}

def find_pod_ips():
    """
    Create the dictionary mapping pod names to their IPs
    """
    try:
        pod_list = core_v1.list_namespaced_pod(namespace="default")
        for pod in pod_list.items:
            pod_ips[pod.metadata.name] = pod.status.pod_ip
        logging.info("Pod IPs have been successfully read.")
    except client.ApiException as exc:
        if exc.status == 404:
            return None
        logging.error("Error while reading pod IPs")
        raise exc
    
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

    if app_type == "yolov5":
        port = 5000
        name = "-".join(("yolov5-deployment", node))
    elif app_type == "mobilenet":
        port = 8080
        name = "-".join(("mobilenet-deployment", node))
    elif app_type == "squeezenet":
        port = 8080
        name = "-".join(("squeezenet-deployment", node))
    elif app_type == "shufflenet":
        port = 8080
        name = "-".join(("shufflenet-deployment", node))

    find_pod_ips()
    
    label = f"app={app_type}-{node}"
    try:
        resource = api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace="default",
            plural="pods",
            label_selector=label
        )
        logging.info("Deployment %s has been successfully read.", name)
    except client.ApiException as exc:
        if exc.status == 404:
            return None
        logging.error("Error while reading deployment %s", name)
        raise exc

    request_count = 0
    available_cpu = 0 
    available_mem = 0
    avg_response_time = 0
    pod_num = len(resource["items"])
    
    for pod in resource["items"]:
        pod_name = pod['metadata']['name']
        pod_ip = pod_ips[pod_name]
        response_times = []

        with os.popen(f"kubectl exec -it {pod_name} -- curl {pod_ip}:{port}/metrics") as f:
            metrics = f.readlines()
            if len(metrics) > 62:
                request_count = float(metrics[38].split()[-1])
                available_cpu = float(metrics[44].split()[-1])
                available_mem = float(metrics[45].split()[-1])
                avg_response_time = float(metrics[48].split()[-1])

                num_of_req = request_count if request_count < 10 else 10
                for i in range(num_of_req):
                    response_times.append(float(metrics[51+(i*3)].split()[-1]))

    res = json.dumps({
        "req_count": request_count,
        "pod_number": pod_num, 
        "available_cpu_percentage": available_cpu / pod_num, 
        "available_mem_percentage": available_mem / pod_num,
        "avg_response_time": avg_response_time / pod_num,
        "response_times": response_times
    })
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8180)
    