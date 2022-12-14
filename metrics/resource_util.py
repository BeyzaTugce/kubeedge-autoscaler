import json
import os

from flask import Flask, Response

# Initialize the Flask application
app = Flask(__name__)
    
@app.route("/load", methods=["GET"])
def forward_resource_util():
    """
    Flas server listening on port 8380 for the resource utilization of edge node
    
    Returns: 
    --------  
    response: Flask Responses
    """
    with os.popen("uptime | sed 's/.*load average: //' | awk -F\\, '{print $2}'") as f:
        load_avg_5min = float(f.read())

    with os.popen("free | grep Mem | awk '{print $7/$2 * 100.0}'") as f:
        mem = float(f.read())

    res = json.dumps({
        "load_avg_5min": load_avg_5min,
        "available_mem": mem 
    })
    return Response(response=res, status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8380)
    