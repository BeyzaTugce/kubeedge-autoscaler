# Proxy module to forward offloading requests

This project includes functions for forwarding requests from vehicles to the optimally selected edge node where the application task will be offloaded  

```
proxy_service-- | 
                |
                - proxy.py
                |     This code is to forward offloading request of vehicles between neighbor edge nodes, from the nearest edge node to the optimally selected one hop by hop.
```

## Setup and Run
* [proxy.py](proxy.py) should be started running as a linux system daemon service in each edge node

Please see [Linux Service Units](../linux_service_units/) for starting the above listed service