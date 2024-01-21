picoAPI
===
picoAPI is a server and framework for simple asynchronous web applications built with MicroPython for your microcontroller.
Of course, it will run also on CPython. But it's designed primarily for the uPy.

**Consider this an alpha release for now. APIs might change.**

### Features
* Familiar. Written like the frameworks you already know from the "big" Python.
* Designed as asynchronous from the ground up.
* Minimal memory usage. Can run also on ESP8266 devices like ESP-01.

### Examples
See [./examples](/examples) directory.

Basically, it's interface is the same as you normally would see on [Flask](https://github.com/pallets/flask) or [FastAPI](https://github.com/tiangolo/fastapi).

```py
from picoapi import Server

app = Server(debug=True)
app.add_static_route("/static", "./static")

@app.route("/hello")
async def hello(req, resp):
    return "Hello, world!", 201

app.run("192.168.4.1", 8000)

### Registering static route /static/ -> ./static/
### Registering route /hello -> hello()
### Starting server on 192.168.4.1:8000...
### 192.168.4.2:12345: GET /hello 201 (43ms)
```

In the above example, a function needs to have two params: `req` and `resp`, which are obviously `Request` and `Response` object.


### Dependencies
picoAPI depends only on `(u)asyncio`
