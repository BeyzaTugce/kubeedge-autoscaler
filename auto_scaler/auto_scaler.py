"""
This script runs the auto-scaler for kubernetes cluster
where some applications deployed to each edge node
"""
import json
import logging
import math
import os
import sys
from collections import defaultdict

import requests
from dotenv import load_dotenv
from kubernetes import client, config

load_dotenv()

class AutoScaler:
    """
    Class holds constants and functions to create, read, update and
    delete (CRUD) the deployment for any application type on an edge node
    """

    # Docker images for application types
    MOBILENET_IMAGE = "byz96/serverless-mobilenet:v5.2"
    SQUEEZENET_IMAGE = "byz96/serverless-squeezenet:v5.2"
    SHUFFLENET_IMAGE = "byz96/serverless-shufflenet:v5.2" 
    BINARYALERT_IMAGE = "byz96/serverless-binaryalert:v5.2"

    NODE_IP_MAP = {
        "edge1": os.environ["EDGE-1"],
        "edge2": os.environ["EDGE-2"],
        "edge3": os.environ["EDGE-3"]
    }
    TARGET_CPU = {
        "shufflenet": 125,
        "mobilenet": 250,
        "squeezenet": 125,
        "binaryalert": 45
    }
    MASTER_IP = os.environ["MASTER"]
    MIN_SCALE = 1
    MAX_SCALE = 30
    TIME_LIMIT = 5

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

        self.min_scale = self.MIN_SCALE
        self.max_scale = self.MAX_SCALE
        self.time_limit = self.TIME_LIMIT

        self.node_cpu_thres = 90.00
        self.node_mem_thres = 30.00
        self.desired_cpu_avg = self.TARGET_CPU[app]
        self.pod_cpu_map = defaultdict(lambda : [])
        self.pod_mem_map = defaultdict(lambda : [])

        self.ip = self.NODE_IP_MAP[node]
        self.master_ip = self.MASTER_IP

        self.node = node
        self.app_type = app
        self.app = "-".join((app, node))

        if app == "mobilenet":
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
        cpu_util, available_mem = self.__get_node_resource()
        if self.scale == 0 and cpu_util < self.node_cpu_thres and available_mem > self.node_mem_thres:
            self.__init_container()
            return

        pod_metrics = self.__get_metrics()
        if pod_metrics is None:
            return
        
        pod_num = len(pod_metrics)
        if pod_num == 0:
            return

        res_time = 0
        p10_res_time = 0
        #p50_res_time = 0
        p90_res_time = 0
        pod_cpu_total = 0

        for _, app_metric in pod_metrics.items():
            res_time += app_metric["res_time"]
            p10_res_time += app_metric["p10_res_time"]
            #p50_res_time += app_metric["p50_res_time"]
            p90_res_time += app_metric["p90_res_time"]
            pod_cpu_total += app_metric["cpu"]

        res_time_avg = res_time / pod_num
        p10_res_time_avg = p10_res_time / pod_num
        #p50_res_time_avg = p50_res_time / pod_num
        p90_res_time_avg = p90_res_time / pod_num
        pod_cpu_avg = pod_cpu_total / pod_num

        desired_replicas = math.ceil(pod_num * ( pod_cpu_avg / self.desired_cpu_avg ))

        if (res_time_avg > p90_res_time_avg or desired_replicas > self.scale) \
            and cpu_util < self.node_cpu_thres and available_mem > self.node_mem_thres:
            self.__init_container()
        elif res_time_avg < p10_res_time_avg or desired_replicas < self.scale:
            self.__terminate_container()


    def __get_metrics(self):
        """Collect metrics from the monitoring service running in the master node"""
        try:
            req = json.dumps({"node": self.node, "app": self.app_type})
            response = requests.post(f"http://{self.master_ip}:8180/metrics", data=req)
            metrics = json.loads(response.text)
        except Exception as exc:
            logging.error("Error while reading metrics of %s - %s", self.node, self.app_type)
            return        

        return metrics["pod_instances"]

    def __get_node_resource(self):
        """Monitor resource usage from the service running in each edge node"""
        response = requests.get(f"http://{self.ip}:8380/load")
        resource = json.loads(response.text)
        cpu_util = resource["cpu_util"]
        available_mem = resource["available_mem"]

        return cpu_util, available_mem

    def __init_container(self):
        """Initialize new container"""
        if self.scale == self.max_scale:
            logging.info("Max number of pods have already been created")
        elif self.scale == 0:
            self.create_deployment_and_service()
        else:
            self.update_deployment(self.scale + 1)

    def __terminate_container(self):
        """Terminate one container"""
        if self.scale == self.min_scale:
            logging.info("Min number of pods are running")
        else:
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
            resources=client.V1ResourceRequirements(
                requests={
                    "cpu": "200m"
                    #"memory": "512Mi"
                }
            ),
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
                "Error while creating deployment object %s with the given specifications", self.name)
            raise exc
        # Create deployment
        try:
            self.apps_v1.create_namespaced_deployment(
                body=deployment, namespace="autoscaler"
            )
            self.scale = replica
            logging.info(
                "Namespaced deployment %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Error while creating namaspaced deployment %s", self.name
            )
        # Create service object
        try:
            service = self.create_service_object()
            logging.info(
                "Service object %s has been successfully created.", self.service
            )
        except Exception as exc:
            logging.warning(
                "Service object %s already exists", self.service)
        # Create service
        try:
            self.core_v1.create_namespaced_service(namespace="autoscaler", body=service)
            logging.info(
                "Namespaced service %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Namaspaced service %s exists", self.name
            )

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
                namespace="autoscaler",
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
            if len(pod['containers']) == 0:
                continue
            cpu = pod['containers'][0]["usage"]["cpu"]
            mem = pod['containers'][0]["usage"]["memory"]
            
            if "n" in cpu:
                cpu_val = float(cpu.split("n")[0]) / 1000000
            elif "m" in cpu:
                cpu_val = float(cpu.split("m")[0])
            else:
                cpu_val = 0.0

            #p90_cpu = sorted(map(float, self.pod_cpu_map[name]))[int(math.ceil(n*0.9)) - 1]

            n = len(self.pod_cpu_map[name])
            if n == 10: 
                self.pod_cpu_map[name].pop(0)
            self.pod_cpu_map[name].append(cpu_val)

            p10_cpu = sum(map(float, self.pod_cpu_map[name])) * 0.1
            p50_cpu = sum(map(float, self.pod_cpu_map[name])) * 0.5
            p90_cpu = sum(map(float, self.pod_cpu_map[name])) * 0.9

            pods[name] = {
                'cpu': cpu_val , 'p10_cpu': p10_cpu, 'p50_cpu': p50_cpu, 'p90_cpu': p90_cpu
            }
        return pods

    def update_deployment(self, replica):
        """
        Scale the deployment with a given number of replicas in the given namespace.
        """
        # Create deployment object
        """
        try:
            deployment = self.create_deployment_object(replica)
            logging.info("Deployment object %s has been successfully created with the new replica number.", self.name)
        except Exception as exc:
            logging.error("Error while creating namaspaced deployment %s", self.name)
            raise exc
        """
        # Update container image
        up_down = "up" if self.scale < replica else "down"
        #deployment.spec.replicas = replica
        
        # patch the deployment
        try:
            self.apps_v1.patch_namespaced_deployment_scale(
                name=self.name, namespace="autoscaler", body={'spec': {'replicas': replica}}
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
                namespace="autoscaler",
                body=client.V1DeleteOptions(
                    propagation_policy="Background",
                    grace_period_seconds=3
                ),
            )
            self.scale -= 1
            logging.info("Deployment object %s has been successfully deleted.", self.name)
        except Exception as exc:
            logging.error("Error while deleting deployment %s", self.name)
            #raise exc
        try:
            self.core_v1.delete_namespaced_service(
                name=self.service,
                namespace="autoscaler",
                body=client.V1DeleteOptions(
                    propagation_policy="Background",
                    grace_period_seconds=3
                ),
            )
            logging.info("Service object %s has been successfully deleted.", self.service)
        except Exception as exc:
            logging.error("Error while deleting service %s", self.service)
            #raise exc

    ######################## END ########################

    def __set_scale(self):
        """
        Get the replica number of deployment if it exists.
        """
        try:
            resource = self.apps_v1.read_namespaced_deployment_scale(
                name=self.name,
                namespace="autoscaler"
            )
            logging.info("Replica number of deployment %s has been successfully read.", self.name)
        except client.ApiException as exc:
            if exc.status == 404:
                return 0
            logging.error("Error while reading replica number of deployment %s", self.name)
            raise exc
        return int(resource.spec.replicas)
