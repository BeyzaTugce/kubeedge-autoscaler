"""
This script runs the auto-scaler for kubernetes cluster
where some applications deployed to each edge node
"""
import logging
import sys

from kubernetes import client, config


class AutoScaler:
    """
    Class holds constants and functions to create, read, update and
    delete (CRUD) the deployment for any application type on an edge node
    """

    YOLOv5_IMAGE = "byz96/kubeedge-yolov5:v4"
    MOBILENET_IMAGE = "byz96/serverless-mobilenet:v3"
    SQUEEZENET_IMAGE = "byz96/serverless-squeezenet:v3"
    SHUFFLENET_IMAGE = "byz96/serverless-shufflenet:v3"

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

        self.pod_ips = {}
        self.node = node
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
        elif app == "shufflenet":
            self.image = self.SHUFFLENET_IMAGE
            self.port = 8080
            self.nodeport = 30300 + int(node[-1])
            self.name = "-".join(("shufflenet-deployment", node))
            self.service = "-".join(("shufflenet-lb", node))
        self.scale = self.__set_scale()

    def watch_and_scale(self):
        """
        Watch the pods and scale up or down according to available resources
        """
        cpu_total = 0
        pod_list = self.__read_deployment()
        for pod in pod_list:
            cpu_total = cpu_total + pod["cpu"]

        if len(pod_list) == 0:
            self.__create_deployment_and_service(1)
        elif cpu_total < 100000:
            self.__update_deployment(self.scale + 1)
        elif cpu_total > 500000 and self.scale > 1:
            self.__update_deployment(self.scale - 1)
        elif cpu_total > 500000 and self.scale == 1:
            self.__delete_deployment()
    
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

    ################## CRUD Operations for the given deployment object ##################
    def __create_deployment_object(self, replica):
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

    def __create_service_object(self):
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
                type="NodePort",
                ports=[client.V1ServicePort(
                    port=self.port,
                    target_port=self.port,
                    node_port=self.nodeport
                )]
            )
        )
        return service

    def __create_deployment_and_service(self, replica=1):
        """
        Create the deployment with the given specifications.
        """
        # Create deployment object
        try:
            deployment = self.__create_deployment_object(replica)
            logging.info(
                "Deployment object %s has been successfully created.", self.name
            )
        except Exception as exc:
            logging.error(
                "Error while creating deployment object \
                %s with the given specifications", self.name
            )
            raise exc
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
            raise exc
        # Create service object
        try:
            service = self.__create_service_object()
            logging.info(
                "Service object %s has been successfully created.", self.service
            )
        except Exception as exc:
            logging.error(
                "Error while creating service object \
                %s with the given specifications", self.service
            )
            raise exc
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
            raise exc

    def __read_deployment(self):
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

        pods = []
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

            pods.append({'pod_name': name, 'cpu': cpu_val, 'mem': mem})

        return pods

    def __update_deployment(self, replica):
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
        deployment.spec.replicas = replica

        # patch the deployment
        try:
            self.apps_v1.patch_namespaced_deployment(
                name=self.name, namespace="default", body=deployment
            )
            logging.info("Deployment object %s has been successfully scaled.", self.name)
        except Exception as exc:
            logging.error("Error while scaling deployment %s", self.name)
            raise exc

        self.scale = replica

    def __delete_deployment(self):
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
        except Exception as exc:
            logging.error("Error while deleting deployment %s", self.name)
            raise exc

    ######################## END ########################

    def find_least_congested_pod(self, pod_list):
        """
        Find the least congested pod
        """
        sorted_pods = sorted(pod_list, key=lambda x: x['cpu'])
        return sorted_pods[0]
