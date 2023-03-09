import json
import os

from flask import Flask, Response

# Initialize the Flask application
app = Flask(__name__)
    
@app.route("/load", methods=["GET"])
def monitor_resource_utils():
    """
    Flas server listening on port 8380 for the resource utilization of edge node
    
    Returns: 
    --------  
    response: Flask Responses
    """
    #with os.popen("top -b -n 1 | grep Cpu | awk '{print 100-$8}'") as f:
    with os.popen("uptime | sed 's/.*load average: //' | awk -F\\, '{print $1}'") as f:
        cpu = float(f.read())

    with os.popen("free | grep Mem | awk '{print $7/$2 * 100.0}'") as f:
        mem = float(f.read())

    res = json.dumps({
        "cpu_util": cpu,
        "available_mem": mem 
    })
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8380)
    