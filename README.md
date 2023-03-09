# KubeEdge Auto Scaler designed for autonomous vehicles in OpenCDA simulation environment

This project aims to better utilize edge resources for autonomous vehicles by periodically (e.g. per 15s) watching response times and resource utilization of containerized application and adjusting the scale of each application deployed to edge nodes. Auto Scaler running in the KubeEdge-based cluster scales the containers in response to the request load by vehicles in OpenCDA. 


## Setup and Run
* "kube-config" file needs to be imported from the Kubernetes cluster, located in the "$HOME/.kube/" directory and metrics-server should be deployed.
* Linux service units should be running in the corresponding nodes as described in [readme.md](metrics/readme.md) for metrics collection and [readme.md](proxy/readme.md) for proxy. Please see [Linux Service Units](linux_service_units/) for starting the services.
* Auto Scaler should be activated. Please see [Auto Scaler](auto_scaler/) for running auto scaler in the cluster.
