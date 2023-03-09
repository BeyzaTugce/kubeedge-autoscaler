# Metric collection module to collect application-level and infrastructure-level metrics from containerized applications in the cluster and monitor the available resources of edge servers

This project includes functions for listening metrics endpoint of running applications deployed to edge nodes in the cluster and also for watching the CPU usage and available memory of edge nodes 

```
metric_collection-- | 
                    |
                    - metric_collector_edge.py
                    |     This code is to enable the connected vehicle to collect only application-level metrics from containers based on the specified edge node and application type deployed to hosting edge node.
                    |
                    - metric_collector.py
                    |     This code is to enable master node to collect both application-level and infrastructure-level metrics from containers based on the specified edge node and application type during auto scaling decisions.
                    |
                    - resource_monitor.py
                    |     This code is to monitor resource usage of edge nodes.
                    |
```

## Setup and Run
* [metric_collection_edge.py](metric_collector_edge.py) should be started running as a linux system daemon service in each edge node
* [metric_collection.py](metric_collector.py) should be started running as a linux system daemon service in the master node
* [resource_monitor.py](resource_monitor.py) should be started running as a linux system daemon service in the master node

Please see [Linux Service Units](../linux_service_units/) for starting the above listed services
