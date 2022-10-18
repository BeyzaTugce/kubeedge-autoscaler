from time import sleep
from auto_scaler import AutoScaler

application_types = ["shufflenet", "squeezenet", "mobilenet"]
edge_servers = ["edge1", "edge2", "edge3"]
    

if __name__ == '__main__':

    shufflenet_edge1 = AutoScaler("edge1", "shufflenet")
    shufflenet_edge2 = AutoScaler("edge2", "shufflenet")
    shufflenet_edge3 = AutoScaler("edge3", "shufflenet")

    squeezenet_edge1 = AutoScaler("edge1", "squeezenet")
    squeezenet_edge2 = AutoScaler("edge2", "squeezenet")
    squeezenet_edge3 = AutoScaler("edge3", "squeezenet")

    mobilenet_edge1 = AutoScaler("edge1", "mobilenet")
    mobilenet_edge2 = AutoScaler("edge2", "mobilenet")
    mobilenet_edge3 = AutoScaler("edge3", "mobilenet")

    while True:

        shufflenet_edge1.watch_and_scale()
        shufflenet_edge2.watch_and_scale()
        shufflenet_edge3.watch_and_scale()

        squeezenet_edge1.watch_and_scale()
        squeezenet_edge2.watch_and_scale()
        squeezenet_edge3.watch_and_scale()

        mobilenet_edge1.watch_and_scale()
        mobilenet_edge2.watch_and_scale()
        mobilenet_edge3.watch_and_scale()

        sleep(5)
