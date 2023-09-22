import json
import io
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse, HTMLResponse
from jinja2 import Environment, BaseLoader
import matplotlib.pyplot as plt

app = FastAPI()


@app.get("/")
async def root():
    return FileResponse("editor.html")


template = Environment(loader=BaseLoader(), autoescape=True).from_string("""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta property="og:title" content="{{ title }}">
    <meta property="og:description" content="{{ description }}">
    <meta property="og:image" content="{{ image_url }}">
    <meta property="og:url" content="{{ url }}">
  </head>
</html>
""")


@app.get("/ogp", response_class=HTMLResponse)
async def generate_ogp(request: Request, src: str, title: str = "", description: str = ""):
    image_url = urlparse(str(request.url))._replace(path="/image")

    content = template.render({
        "title": title,
        "description": description,
        "image_url": image_url.geturl(),
        "url": str(request.url),
    })

    return HTMLResponse(content=content, status_code=200)


@app.get("/image", response_class=Response)
def generate_image(src: str):
    s = json.loads(src)
    plt.figure()
    plt.plot(s['x'], s['y'])
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")
