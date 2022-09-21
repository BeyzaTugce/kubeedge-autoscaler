from time import sleep

from auto_scaler import AutoScaler

if __name__ == '__main__':

    as_yolov5_edge1 = AutoScaler("edge1", "nginx")
    as_yolov5_edge2 = AutoScaler("edge2", "nginx")
    as_yolov5_edge3 = AutoScaler("edge3", "nginx")

    as_yolov5_edge1.read_deployment()
    as_yolov5_edge2.read_deployment()
    as_yolov5_edge3.read_deployment()


    while True:

        pods_1 = as_yolov5_edge1.read_deployment()
        as_yolov5_edge1.watch_and_scale(pods_1)

        pods_2 = as_yolov5_edge2.read_deployment()
        as_yolov5_edge2.watch_and_scale(pods_2)

        pods_3 = as_yolov5_edge3.read_deployment()
        as_yolov5_edge3.watch_and_scale(pods_3)

        sleep(2)
