import json
import io
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse, HTMLResponse
from jinja2 import Environment, BaseLoader
from jsonschema import validate
import matplotlib.pyplot as plt
import japanize_matplotlib

app = FastAPI()


@app.get("/")
async def root():
    return FileResponse("editor.html")


ogp_template = Environment(loader=BaseLoader(), autoescape=True).from_string("""
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

    content = ogp_template.render({
        "title": title,
        "description": description,
        "image_url": image_url.geturl(),
        "url": str(request.url),
    })

    return HTMLResponse(content=content, status_code=200)


def _decode_src(src: str) -> dict:
    s = json.loads(src)

    schema = {
        "type": "object",
        "properties": {
            "line": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "array",
                        "items": {
                            "type": "number",
                        }
                    },
                    "y": {
                        "type": "array",
                        "items": {
                            "anyOf": [
                                {
                                    "type": "number"
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "type": "number",
                                            },
                                        },
                                        "label": {
                                            "type": "string"
                                        },
                                    },
                                    "required": ["data", "label"],
                                },
                            ]
                        }
                    },
                    "xLabel": {
                        "type": "string",
                    },
                    "yLabel": {
                        "type": "string",
                    },
                    "title": {
                        "type": "string",
                    },
                },
                "required": ["y"],
            },
        },
        "anyOf": [
            {
                "required": [key]
            }
            for key in ["line", "bar", "pie", "scatter", "histogram"]
        ]
    }

    validate(instance=s, schema=schema)

    return s


@app.get("/image", response_class=Response)
def generate_image(src: str):
    s = _decode_src(src)
    plt.figure()

    if "line" in s:
        line = s["line"]

        if any(isinstance(y, dict) for y in line["y"]):
            for y in line["y"]:
                data = (line["x"], y["data"]) if "x" in line else (y["data"],)
                plt.plot(*data, label=y["label"])

            plt.legend()
        else:
            data = (line["x"], line["y"]) if "x" in line else (line["y"],)
            plt.plot(*data)

        if "xLabel" in line:
            plt.xlabel(line["xLabel"])
        if "yLabel" in line:
            plt.ylabel(line["yLabel"])

        if "title" in line:
            plt.title(line["title"])

        ylim = plt.ylim()
        ylim = min(ylim[0], 0), max(ylim[1], 0)
        plt.ylim(bottom=ylim[0], top=ylim[1])

    buf = io.BytesIO()
    plt.savefig(buf, format="png")

    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")
