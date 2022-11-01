"""
This script runs the auto-scaler for kubernetes cluster
where some applications deployed to each edge node
"""
import json
import logging
import sys

import requests
from auto_scaler.app_deployment import Deployment


class AutoScaler:
    """
    Class holds constants and functions to watch and scale
    the deployment for an application type on an edge node
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("debug.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    NODE_IP_MAP = {
        "edge1": "138.246.237.7",
        "edge2": "138.246.236.237",
        "edge3": "138.246.237.5"
    }
    MASTER_IP = "138.246.236.8"

    def __init__(self, node, app):
        """ Initialize the deployment object of the given application on the given edge node """
        self.pod_num = 0
        self.avg_cpu = 0
        self.avg_mem = 0
        self.avg_res = 0
        self.load_avg_thres = 1.85
        self.available_mem = 20.00

        self.ip = self.NODE_IP_MAP[node]
        self.master_ip = self.MASTER_IP
        self.node = node
        self.app = "-".join((app, node))
        self.deployment = Deployment(self.node, self.app)

    def watch_and_scale(self):
        """
        Watch the pods and scale up or down according to available resources
        """

        self.__get_metrics()
        if self.avg_cpu == 0 or self.avg_mem == 0:
            return

        load_avg, available_mem = self.__get_node_resource()
        if (self.avg_cpu <= self.deployment.lower_thres_cpu
            or self.avg_mem <= self.deployment.lower_thres_mem) \
            and self.avg_res >= self.deployment.upper_thres_res \
            and load_avg < self.load_avg_thres \
            and available_mem > self.available_mem:
            self.__init_container()

        if (self.avg_cpu > self.deployment.upper_thres_cpu
            or self.avg_mem > self.deployment.upper_thres_mem) \
            and self.avg_res < self.deployment.lower_thres_res:
            self.__terminate_container()


    def __get_metrics(self):
        """Collect metrics from the monitoring service running in the master node"""
        req = json.dumps({"node": self.node, "app": self.app})
        response = requests.post(f"http://{self.master_ip}:8180/metrics", data=req)
        metrics = json.loads(response.text)

        pod_num = metrics["pod_number"]
        pod_instances = metrics["pod_instances"]
        cpu_total = 0
        mem_total = 0
        res_total = 0

        for pod in pod_instances:
            cpu_total += pod["available_cpu_percentage"]
            mem_total += pod["available_mem_percentage"]
            res_total += pod["avg_response_time"]
        self.avg_cpu = cpu_total / pod_num
        self.avg_mem = mem_total / pod_num
        self.avg_res = res_total / pod_num

    def __get_node_resource(self):
        """Monitor resource usage from the service running in each edge node"""
        response = requests.post(f"http://{self.ip}:8380/load")
        resource = json.loads(response.text)

        load_avg = resource["load_avg_5min"]
        available_mem = resource["available_mem"]

        return load_avg, available_mem

    def __init_container(self):
        """Initialize new container"""
        if self.pod_num == 0:
            self.deployment.create_deployment_and_service(1)
        else:
            self.deployment.update_deployment(self.deployment.scale + 1)

    def __terminate_container(self):
        """Terminate one container"""
        if self.pod_num == 1:
            self.deployment.delete_deployment()
        elif self.pod_num > 1:
            self.deployment.update_deployment(self.deployment.scale - 1)
