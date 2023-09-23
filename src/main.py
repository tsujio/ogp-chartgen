import json
import io
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse, HTMLResponse
from jinja2 import Environment, BaseLoader
from jsonschema import validate
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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


line_chart_schema = {
    "type": "object",
    "properties": {
        "x": {
            "type": "array",
            "items": {
                "type": "number",
            },
        },
        "y": {
            "anyOf": [
                {
                    "type": "array",
                    "items": {
                        "type": "number",
                    }
                },
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "items": {
                                    "type": "number",
                                },
                            },
                            "label": {"type": "string"},
                        },
                        "required": ["data", "label"],
                    },
                },
            ],
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
}

time_series_chart_schema = {
    "type": "object",
    "properties": {
        "x": {
            "type": "array",
            "items": {
                "type": "string",
                "format": "date"
            },
        },
        "y": {
            "anyOf": [
                {
                    "type": "array",
                    "items": {
                        "type": "number",
                    }
                },
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "items": {
                                    "type": "number",
                                },
                            },
                            "label": {"type": "string"},
                        },
                        "required": ["data", "label"],
                    },
                },
            ],
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
    "required": ["x", "y"],
}

schema = {
    "type": "object",
    "properties": {
        "line": line_chart_schema,
        "timeSeries": time_series_chart_schema,
    },
    "anyOf": [
        {
            "required": [key]
        }
        for key in ["line", "timeSeries", "bar", "pie", "scatter", "histogram"]
    ],
}


def _decode_src(src: str) -> dict:
    s = json.loads(src)

    validate(instance=s, schema=schema)

    return s


def _plot_line_chart(src: dict):
    data = ()
    if "x" in src:
        data = (src["x"],)

    if any(isinstance(y, dict) for y in src["y"]):
        for y in src["y"]:
            _data = (*data, y["data"])
            plt.plot(*_data, label=y["label"])

        plt.legend()
    else:
        _data = (*data, src["y"])
        plt.plot(*_data)

    if "xLabel" in src:
        plt.xlabel(src["xLabel"])
    if "yLabel" in src:
        plt.ylabel(src["yLabel"])

    if "title" in src:
        plt.title(src["title"])

    ylim = plt.ylim()
    ylim = min(ylim[0], 0), max(ylim[1], 0)
    plt.ylim(bottom=ylim[0], top=ylim[1])


def _plot_time_series_chart(src: dict):
    x = [mdates.datestr2num(v) for v in src["x"]]

    xaxis = plt.axes().xaxis
    xaxis.set_minor_formatter(mdates.DateFormatter("%Y-%m-%d"))
    xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    plt.xticks(rotation=70)

    if any(isinstance(y, dict) for y in src["y"]):
        for y in src["y"]:
            plt.plot(x, y["data"], label=y["label"])

        plt.legend()
    else:
        plt.plot(x, src["y"])

    if "xLabel" in src:
        plt.xlabel(src["xLabel"])
    if "yLabel" in src:
        plt.ylabel(src["yLabel"])

    if "title" in src:
        plt.title(src["title"])

    ylim = plt.ylim()
    ylim = min(ylim[0], 0), max(ylim[1], 0)
    plt.ylim(bottom=ylim[0], top=ylim[1])


@app.get("/image", response_class=Response)
def generate_image(src: str):
    s = _decode_src(src)
    plt.figure()

    if "line" in s:
        _plot_line_chart(s["line"])
    elif "timeSeries" in s:
        _plot_time_series_chart(s["timeSeries"])

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")

    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")
