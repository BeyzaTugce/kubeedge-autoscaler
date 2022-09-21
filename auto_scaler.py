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
    SQUEEZENET_IMAGE = "byz96/serverless-squeezenet:v1"
    NGINX_IMAGE = "nginx:1.14.2"

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

        self.node = node
        self.app = "-".join((app, node))
        self.scale = 0

        if app == "yolov5":
            self.image = self.YOLOv5_IMAGE
            self.port = 5000
            self.name = "-".join(("yolov5-deployment", node))
        elif app == "squeezenet":
            self.image = self.SQUEEZENET_IMAGE
            self.port = 8080
            self.name = "-".join(("squeezenet-deployment", node))
        elif app == "nginx":
            self.image = self.NGINX_IMAGE
            self.port = 80
            self.name = "-".join(("nginx-deployment", node))

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
            #resources=client.V1ResourceRequirements(
            #    requests={
            #        "cpu": "100m",
            #        "memory": "200Mi"
            #    },
            #    limits={
            #        "cpu": "500m",
            #        "memory": "500Mi"
            #    },
            #),
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

    def create_deployment(self, replica):
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
            raise exc
        # Create deployement
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

    def read_deployment(self):
        """
        Read the resource usage (CPU, Memory etc.) of deployment.
        """
        label = f"app={self.app}"
        try:
            resource = self.api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace="default",
                plural="pods",
                label_selector=label
            )
            pod_list = self.core_v1.list_namespaced_pod(namespace="default")
            print("pods: ", pod_list)
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
        except Exception as exc:
            logging.error("Error while deleting deployment %s", self.name)
            raise exc

    ######################## END ########################

    def watch_and_scale(self, pod_list: list):
        """
        Watch the pods and scale up or down according to available resources
        """
        cpu_total = 0

        for pod in pod_list:
            cpu_total = cpu_total + pod["cpu"]

        if len(pod_list) == 0:
            self.create_deployment(1)
        elif cpu_total < 100000:
            self.update_deployment(self.scale + 1)
        elif cpu_total > 500000 and self.scale > 1:
            self.update_deployment(self.scale - 1)
        elif cpu_total > 500000 and self.scale == 1:
            self.delete_deployment()


    def find_least_congested_pod(self, pod_list):
        """
        Find the least congested pod
        """
        sorted_pods = sorted(pod_list, key=lambda x: x['cpu'])
        return sorted_pods[0]
