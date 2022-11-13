"""
This script runs the auto-scaler for kubernetes cluster
where some applications deployed to each edge node
"""
import json
import logging
import math
import sys
from collections import defaultdict

import numpy as np
import requests
from kubernetes import client, config


class AutoScaler:
    """
    Class holds constants and functions to create, read, update and
    delete (CRUD) the deployment for any application type on an edge node
    """

    # Docker images for application types
    YOLOv5_IMAGE = "byz96/kubeedge-yolov5:v5"
    MOBILENET_IMAGE = "byz96/serverless-mobilenet:v5"
    SQUEEZENET_IMAGE = "byz96/serverless-squeezenet:v5"
    SHUFFLENET_IMAGE = "byz96/serverless-shufflenet:v5" 
    BINARYALERT_IMAGE = "byz96/serverless-binaryalert:v5"

    NODE_IP_MAP = {
        "edge1": "138.246.237.7",
        "edge2": "138.246.236.237",
        "edge3": "138.246.237.5"
    }
    MASTER_IP = "138.246.236.8"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("debug.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    def __init__(self, node, app):
        """ Initialize the deployment object of the given application on the given edge node """
        config.load_kube_config()
        self.api = client.CustomObjectsApi()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

        self.load_avg_thres = 1.85
        self.available_mem = 20.00
        self.pod_cpu_map = defaultdict(lambda : [])
        self.pod_mem_map = defaultdict(lambda : [])

        self.ip = self.NODE_IP_MAP[node]
        self.master_ip = self.MASTER_IP
        self.node = node
        self.app_type = app
        self.app = "-".join((app, node))

        if app == "yolov5":
            self.image = self.YOLOv5_IMAGE
            self.port = 5000
            self.nodeport = 30000 + int(node[-1])
            self.name = "-".join(("yolov5-deployment", node))
            self.service = "-".join(("yolov5-lb", node))
        elif app == "mobilenet":
            self.image = self.MOBILENET_IMAGE
            self.port = 8080
            self.nodeport = 30100 + int(node[-1])
            self.name = "-".join(("mobilenet-deployment", node))
            self.service = "-".join(("mobilenet-lb", node))
        elif app == "squeezenet":
            self.image = self.SQUEEZENET_IMAGE
            self.port = 8080
            self.nodeport = 30200 + int(node[-1])
            self.name = "-".join(("squeezenet-deployment", node))
            self.service = "-".join(("squeezenet-lb", node))
            self.upper_thres_cpu = 0.80
            self.lower_thres_cpu = 0.40
            self.upper_thres_res = 0.50
            self.lower_thres_res = 0.10
        elif app == "shufflenet":
            self.image = self.SHUFFLENET_IMAGE
            self.port = 8080
            self.nodeport = 30300 + int(node[-1])
            self.name = "-".join(("shufflenet-deployment", node))
            self.service = "-".join(("shufflenet-lb", node))
        elif app == "binaryalert":
            self.image = self.BINARYALERT_IMAGE
            self.port = 8080
            self.nodeport = 30400 + int(node[-1])
            self.name = "-".join(("binaryalert-deployment", node))
            self.service = "-".join(("binaryalert-lb", node))

        self.scale = self.__set_scale()

    def watch_and_scale(self):
        """
        Watch the pods and scale up or down according to available resources
        """
        load_avg, available_mem = self.__get_node_resource()
        if self.scale == 0 and load_avg < self.load_avg_thres and available_mem > self.available_mem:
            self.__init_container()
            return

        #pod_resources = self.read_deployment()
        pod_metrics = self.__get_metrics()
        logging.info(f"Pod metrics: {pod_metrics}")
        for pod_name, app_metric in pod_metrics.items():
            #or pod_resources[pod_name]["cpu"] > pod_resources[pod_name]["p90_cpu"]
            #or pod_resources[pod_name]["mem"] > pod_resources[pod_name]["p90_mem"])
            if  app_metric["res_time"] > app_metric["p90_res_time"] \
                and load_avg < self.load_avg_thres \
                and available_mem > self.available_mem:
                self.__init_container()
                return
            #pod_resources[pod_name]["cpu"] < pod_resources[pod_name]["p50_cpu"]
            if  app_metric["res_time"] < app_metric["p50_res_time"]:
                self.__terminate_container()
                return


    def __get_metrics(self):
        """Collect metrics from the monitoring service running in the master node"""
        req = json.dumps({"node": self.node, "app": self.app_type})
        response = requests.post(f"http://{self.master_ip}:8180/metrics", data=req)
        metrics = json.loads(response.text)

        return metrics["pod_instances"]

    def __get_node_resource(self):
        """Monitor resource usage from the service running in each edge node"""
        response = requests.get(f"http://{self.ip}:8380/load")
        resource = json.loads(response.text)
        load_avg = resource["load_avg_5min"]
        available_mem = resource["available_mem"]

        return load_avg, available_mem

    def __init_container(self):
        """Initialize new container"""
        if self.scale == 0:
            self.create_deployment_and_service(1)
        else:
            self.update_deployment(self.scale + 1)

    def __terminate_container(self):
        """Terminate one container"""
        if self.scale == 1:
            self.delete_deployment()
        elif self.scale > 1:
            self.update_deployment(self.scale - 1)


    ################## CRUD Operations for the given deployment object ##################
    def create_deployment_object(self, replica):
        """
        Configure the deployment specifications.
        """

        # Configureate Pod template container
        container = client.V1Container(
            name=self.app,
            image=self.image,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(name="http", container_port=self.port)],
        )
        # Create and configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": self.app
                }
            ),
            spec=client.V1PodSpec(
                containers=[container],
                node_name=self.node
            ),
        )
        # Create the specification of deployment
        spec = client.V1DeploymentSpec(
            replicas=replica,
            template=template,
            selector={
                "matchLabels":
                {
                    "app": self.app
                }
            }
        )
        # Instantiate the deployment object
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=self.name
            ),
            spec=spec,
        )
        return deployment

    def create_service_object(self):
        """
        Create the service with the given specifications.
        """

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=self.service
            ),
            spec=client.V1ServiceSpec(
                selector={
                    "app": self.app
                },
                type="LoadBalancer",
                ports=[client.V1ServicePort(
                    port=self.port,
                    target_port=self.port,
                    node_port=self.nodeport
                )]
            )
        )
        return service

    def create_deployment_and_service(self, replica=1):
        """
        Create the deployment with the given specifications.
        """
        # Create deployment object
        try:
            deployment = self.create_deployment_object(replica)
            logging.info(
                "Deployment object %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Error while creating deployment object \
                %s with the given specifications", self.name
            )
            #raise exc
        # Create deployment
        try:
            self.apps_v1.create_namespaced_deployment(
                body=deployment, namespace="default"
            )
            self.scale = replica
            logging.info(
                "Namespaced deployment %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Error while creating namaspaced deployment %s", self.name
            )
            #raise exc
        # Create service object
        try:
            service = self.create_service_object()
            logging.info(
                "Service object %s has been successfully created.", self.service
            )
        except Exception as exc:
            logging.error(
                "Error while creating service object \
                %s with the given specifications", self.service
            )
            #raise exc
        # Create service
        try:
            self.core_v1.create_namespaced_service(namespace="default", body=service)
            logging.info(
                "Namespaced service %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Error while creating namaspaced service %s", self.name
            )
            #raise exc

    def read_deployment(self):
        """
        Read the resource usage (CPU, Memory etc.) of deployment.
        """
        if self.scale == 0:
            logging.info("Deployment object %s does not exist.", self.name)
            return
        label = f"app={self.app}"
        try:
            resource = self.api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace="default",
                plural="pods",
                label_selector=label
            )
            logging.info("Deployment %s has been successfully read.", self.name)
        except client.ApiException as exc:
            if exc.status == 404:
                return None
            logging.error("Error while reading deployment %s", self.name)
            raise exc

        pods = {}
        for pod in resource["items"]:
            name = pod['metadata']['name']
            cpu = pod['containers'][0]["usage"]["cpu"]
            mem = pod['containers'][0]["usage"]["memory"]
            
            if "n" in cpu:
                cpu_val = float(cpu.split("n")[0]) / 1000000
            elif "m" in cpu:
                cpu_val = float(cpu.split("m")[0])
            else:
                cpu_val = 0.0

            n = len(self.pod_cpu_map[name])
            if n == 10: 
                self.pod_cpu_map.pop(0)
                #self.pod_mem_map.pop(0)
            self.pod_cpu_map[name].append(cpu_val)
            #self.pod_mem_map[name].append(mem)

            p50_cpu = sorted(map(float, self.pod_cpu_map[name]))[int(math.ceil(n*0.5)) - 1]
            p90_cpu = sorted(map(float, self.pod_cpu_map[name]))[int(math.ceil(n*0.9)) - 1]
            #p50_mem = sum(map(float, self.pod_cpu_map[name])) * 0.5
            #p90_mem = sum(map(float, self.pod_cpu_map[name])) * 0.9

            pods[name] = {
                'cpu': cpu_val ,'p50_cpu': p50_cpu, 'p90_cpu': p90_cpu
            }
            #'mem': mem, 'p50_mem': p50_mem, 'p90_mem': p90_mem

        return pods

    def update_deployment(self, replica):
        """
        Scale the deployment with a given number of replicas in the given namespace.
        """
        # Create deployment object
        try:
            deployment = self.create_deployment_object(replica)
            logging.info(
                "Deployment object %s has been successfully \
                created with the new replica number.", self.name
            )
        except Exception as exc:
            logging.error("Error while creating namaspaced deployment %s", self.name)
            raise exc

        # Update container image
        up_down = "up" if self.scale < replica else "down"
        deployment.spec.replicas = replica

        # patch the deployment
        try:
            self.apps_v1.patch_namespaced_deployment(
                name=self.name, namespace="default", body=deployment
            )
            logging.info("Deployment object %s has been successfully scaled %s.", self.name, up_down)
        except Exception as exc:
            logging.error("Error while scaling deployment %s", self.name)
            raise exc

        self.scale = replica

    def delete_deployment(self):
        """
        Delete the deployment.
        """
        if self.scale == 0:
            logging.info("Deployment object %s does not exist.", self.name)
            return

        # Delete deployment
        try:
            self.apps_v1.delete_namespaced_deployment(
                name=self.name,
                namespace="default",
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground",
                    grace_period_seconds=3
                ),
            )
            logging.info("Deployment object %s has been successfully deleted.", self.name)
            self.core_v1.delete_namespaced_service(
                name=self.service,
                namespace="default",
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground",
                    grace_period_seconds=3
                ),
            )
            logging.info("Service object %s has been successfully deleted.", self.service)
        except Exception as exc:
            logging.error("Error while deleting deployment %s and service %s", self.name, self.service)
            raise exc

    ######################## END ########################

    def __set_scale(self):
        """
        Get the replica number of deployment if it exists.
        """
        try:
            resource = self.apps_v1.read_namespaced_deployment_scale(
                name=self.name,
                namespace="default"
            )
            logging.info("Replica number of deployment %s has been successfully read.", self.name)
        except client.ApiException as exc:
            if exc.status == 404:
                return 0
            logging.error("Error while reading replica number of deployment %s", self.name)
            raise exc
        return int(resource.spec.replicas)
