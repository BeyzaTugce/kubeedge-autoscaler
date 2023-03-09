# Auto Scaler module to scale up or down pods on KubeEdge edge node according to available cpu and memory resources

This project includes functions for watching and scaling the pods deployed to an edge node in KubeEdge cluster. For CRUD (create, read, update, delete) operations, all necessary functions are implemented with Kubernetes Python API Client. 

```
auto_scaler--   | 
                |
                - auto_scaler.py
                |     This code is to create an auto scaler for specified edge node and application type.
                |
                - metric_collector.py
                |     This code is to collect metrics for specified edge node and application type.
                |
                - run_auto_scaler.py
                |     This file is to run the auto scalers for each node and watch them
                |
```

## Setup and Run
First, "kube-config" file needs to be imported from the Kubernetes cluster, located in the "$HOME/.kube/" directory and metrics-server should be deployed.

```
mkdir -p $HOME/.kube
sudo cp -i $HOME/.kube/config /etc/kubernetes/admin.conf
sudo chown $(id -u):$(id -g) $HOME/.kube/config

python -m run_auto_scaler
```
