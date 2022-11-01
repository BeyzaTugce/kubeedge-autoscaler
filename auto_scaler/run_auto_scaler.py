from time import sleep
from auto_scaler.auto_scaler import AutoScaler

edge_servers = ["edge1", "edge2", "edge3"]
application_types = ["shufflenet", "squeezenet", "mobilenet"]

if __name__ == '__main__':

    #auto_scaler_list = [AutoScaler(node, app) for node in edge_servers for app in application_types]
    #[auto_scaler.create_deployment_and_service(1) for auto_scaler in auto_scaler_list]
    edge1_mobilenet = AutoScaler("edge1", "mobilenet")
    edge2_mobilenet = AutoScaler("edge2", "mobilenet")
    edge3_mobilenet = AutoScaler("edge3", "mobilenet")

    edge1_squeezenet = AutoScaler("edge1", "squeezenet")
    edge2_squeezenet = AutoScaler("edge2", "squeezenet")
    edge3_squeezenet = AutoScaler("edge3", "squeezenet")

    edge1_shufflenet = AutoScaler("edge1", "shufflenet")
    edge2_shufflenet = AutoScaler("edge2", "shufflenet")
    edge3_shufflenet = AutoScaler("edge3", "shufflenet")
    
    while True:
        #[auto_scaler.watch_and_scale() for auto_scaler in auto_scaler_list] 
        edge1_mobilenet.watch_and_scale()
        edge2_mobilenet.watch_and_scale()
        edge3_mobilenet.watch_and_scale()
        edge1_squeezenet.watch_and_scale()
        edge2_squeezenet.watch_and_scale()
        edge3_squeezenet.watch_and_scale()
        edge1_shufflenet.watch_and_scale()
        edge2_shufflenet.watch_and_scale()
        edge3_shufflenet.watch_and_scale()
        sleep(8)
