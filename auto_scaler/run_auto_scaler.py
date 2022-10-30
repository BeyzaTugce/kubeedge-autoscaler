from time import sleep
from auto_scaler.auto_scaler import AutoScaler

edge_servers = ["edge1", "edge2", "edge3"]
application_types = ["shufflenet", "squeezenet", "mobilenet"]

if __name__ == '__main__':

    auto_scaler_list = [AutoScaler(node, app) for node in edge_servers for app in application_types]
    #[auto_scaler.create_deployment_and_service(1) for auto_scaler in auto_scaler_list]

    [auto_scaler.delete_deployment(1) for auto_scaler in auto_scaler_list]
    #while True:

    #    [auto_scaler.watch_and_scale() for auto_scaler in auto_scaler_list] 
    #    sleep(3)
