try:
    import network
    wlan = network.WLAN(network.STA_IF)
    host = wlan.ifconfig()[0]
except ImportError:
    host = "127.0.0.1"

from slowapi.app import SlowAPI

# creating an instance of SlowAPI
app = SlowAPI(debug=True)

# registering a static route
app.add_static_route("/static", "/static")


@app.route("/")
async def index(req, resp):
    # returning a string with status code 200
    return "Hello world!", 200


@app.route("/hello")
async def hello(req, resp):
    # returning a string with status code 200 and custom headers
    return "Bonjour!", 200, {"X-Request-Whatever": "Hello"}


@app.route("/json")
async def json(req, resp):
    # returning a json with default status code 200 and Content-Type: application/json
    # (handled internally based on type)
    return [{"hello": "world"}]


@app.route("/redir")
async def redir(req, resp):
    # returning a redirect with status code 302
    # modifying the response object directly and returning it –
    # therefore, it will be returned as is to the client without any modifications.
    resp.redirect("/hello")
    return resp


# starting the server
if __name__ == "__main__":
    app.run(host=host, port=8000)
