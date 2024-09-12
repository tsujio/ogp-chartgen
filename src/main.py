import json
import io
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, FileResponse, HTMLResponse
from jinja2 import Environment, BaseLoader
import jsonschema
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
        "xInterval": {
            "type": "object",
            "properties": {
                "unit": {
                    "type": "string",
                    "enum": ["year", "month", "week", "day", "hour", "minute"],
                },
                "interval": {
                    "type": "number",
                },
            },
            "required": ["unit"],
        },
    },
    "required": ["x", "y"],
}

bar_chart_schema = {
    "type": "object",
    "properties": {
        "x": {
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
                        "type": "string",
                    }
                },
            ],
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
        "groupingStyle": {
            "type": "string",
            "enum": ["stacked", "grouped"],
        },
    },
    "required": ["y"],
}

pie_chart_schema = {
    "type": "object",
    "properties": {
        "data": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                    },
                    "label": {
                        "type": "string",
                    },
                },
                "required": ["value", "label"],
            },
        },
        "title": {
            "type": "string",
        },
    },
    "required": ["data"],
}

scatter_chart_schema = {
    "type": "object",
    "properties": {
        "data": {
            "anyOf": [
                {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "number",
                        },
                        "minItems": 2,
                        "maxItems": 2,
                    }
                },
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "position": {
                                "type": "array",
                                "items": {
                                    "type": "number",
                                },
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "label": {
                                "type": "string",
                            },
                        },
                        "required": ["position", "label"],
                    }
                },
            ]
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
    "required": ["data"],
}

histogram_chart_schema = {
    "type": "object",
    "properties": {
        "data": {
            "type": "array",
            "items": {
                "type": "number",
            }
        },
        "bins": {
            "type": "number",
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
    "required": ["data"],
}

schema = {
    "type": "object",
    "properties": {
        "line": line_chart_schema,
        "timeSeries": time_series_chart_schema,
        "bar": bar_chart_schema,
        "pie": pie_chart_schema,
        "scatter": scatter_chart_schema,
        "histogram": histogram_chart_schema,
    },
    "anyOf": [
        {
            "required": [key]
        }
        for key in ["line", "timeSeries", "bar", "pie", "scatter", "histogram"]
    ],
}


def _decode_src(src: str) -> dict:
    try:
        s = json.loads(src)
    except json.decoder.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid json (src)")

    try:
        jsonschema.validate(instance=s, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return s


def _plot_line_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    data = ()
    if "x" in src:
        data = (src["x"],)

    if all(isinstance(y, dict) for y in src["y"]):
        for y in src["y"]:
            _data = (*data, y["data"])
            if len(set(len(d) for d in _data)) != 1:
                raise HTTPException(status_code=400, detail="Some data have different length")
            ax.plot(*_data, label=y["label"])

        ax.legend()
    else:
        _data = (*data, src["y"])
        if len(set(len(d) for d in _data)) != 1:
            raise HTTPException(status_code=400, detail="Some data have different length")
        ax.plot(*_data)

    if "xLabel" in src:
        ax.set_xlabel(src["xLabel"])
    if "yLabel" in src:
        ax.set_ylabel(src["yLabel"])

    if "title" in src:
        ax.set_title(src["title"])

    ylim = ax.get_ylim()
    ylim = min(ylim[0] * 1.1, 0), max(ylim[1] * 1.1, 0)
    ax.set_ylim(bottom=ylim[0], top=ylim[1])

    ax.set_axisbelow(True)
    ax.grid()


def _plot_time_series_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    x = [mdates.datestr2num(v) for v in src["x"]]

    if "xInterval" in src:
        interval = src["xInterval"].get("interval", 1)
        match src["xInterval"]["unit"]:
            case "year":
                formatter = mdates.DateFormatter("%Y")
                locator = mdates.YearLocator(base=interval)
            case "month":
                formatter = mdates.DateFormatter("%Y-%m")
                locator = mdates.MonthLocator(interval=interval)
            case "week":
                formatter = mdates.DateFormatter("%Y-%m-%d")
                locator = mdates.WeekdayLocator(interval=interval)
            case "day":
                formatter = mdates.DateFormatter("%Y-%m-%d")
                locator = mdates.DayLocator(interval=interval)
            case "hour":
                formatter = mdates.DateFormatter("%Y-%m-%d %H:00")
                locator = mdates.HourLocator(interval=interval)
            case "minute":
                formatter = mdates.DateFormatter("%Y-%m-%d %H:%M")
                locator = mdates.MinuteLocator(interval=interval)
    else:
        formatter = mdates.DateFormatter("%Y-%m-%d")
        locator = mdates.DayLocator(interval=1)

    xaxis = ax.xaxis
    xaxis.set_major_formatter(formatter)
    xaxis.set_major_locator(locator)

    ax.tick_params("x", labelrotation=70)

    if all(isinstance(y, dict) for y in src["y"]):
        for y in src["y"]:
            if len(x) != len(y["data"]):
                raise HTTPException(status_code=400, detail="Some data have different length")
            ax.plot(x, y["data"], label=y["label"])

        ax.legend()
    else:
        if len(x) != len(src["y"]):
            raise HTTPException(status_code=400, detail="Some data have different length")
        ax.plot(x, src["y"])

    if "xLabel" in src:
        ax.set_xlabel(src["xLabel"])
    if "yLabel" in src:
        ax.set_ylabel(src["yLabel"])

    if "title" in src:
        ax.set_title(src["title"])

    ylim = ax.get_ylim()
    ylim = min(ylim[0] * 1.1, 0), max(ylim[1] * 1.1, 0)
    ax.set_ylim(bottom=ylim[0], top=ylim[1])

    ax.set_axisbelow(True)
    ax.grid()


def _plot_bar_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    if "x" in src:
        x = src["x"]
    else:
        x = list(range(len(src["y"])))

    if all(isinstance(y, dict) for y in src["y"]):
        for i, y in enumerate(src["y"]):
            if len(x) != len(y["data"]):
                raise HTTPException(status_code=400, detail="Some data have different length")
            match src.get("groupingStyle", "stacked"):
                case "stacked":
                    bottom = [sum(py["data"][j] for py in src["y"][:i]) for j in range(len(y["data"]))]
                    c = ax.bar(x, y["data"], bottom=bottom, label=y["label"])
                    ax.bar_label(c, label_type="center")
                case "grouped":
                    xn = list(range(len(x))) if all(isinstance(v, str) for v in x) else x
                    width = ((xn[1] - xn[0]) / len(src["y"]) * 0.8) if len(xn) > 1 else 1.0
                    x_offset = [n + width * i for n in xn]
                    c = ax.bar(x_offset, y["data"], width, label=y["label"])
                    ax.bar_label(c)

                    if i == len(src["y"]) - 1:
                        ax.set_xticks([n + width * (len(src["y"]) - 1) / 2 for n in xn], x)

        ax.legend()
    else:
        if len(x) != len(src["y"]):
            raise HTTPException(status_code=400, detail="Some data have different length")
        c = ax.bar(x, src["y"])
        ax.bar_label(c)

    if "xLabel" in src:
        ax.set_xlabel(src["xLabel"])
    if "yLabel" in src:
        ax.set_ylabel(src["yLabel"])

    if "title" in src:
        ax.set_title(src["title"])

    ax.set_axisbelow(True)
    ax.grid(axis="y")


def _plot_pie_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    data = [d["value"] for d in src["data"]]
    labels = [d["label"] for d in src["data"]]

    ax.pie(data, labels=labels, startangle=90, counterclock=False, autopct=lambda pct: f"{pct:.1f}%")

    if "title" in src:
        ax.set_title(src["title"])


def _plot_scatter_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    if all(isinstance(data, dict) for data in src["data"]):
        labels = set(data["label"] for data in src["data"])
        for label in labels:
            positions = [data["position"] for data in src["data"] if data["label"] == label]
            x = [x for x, y in positions]
            y = [y for x, y in positions]
            ax.scatter(x, y, label=label)

        ax.legend()
    else:
        x = [x for x, y in src["data"]]
        y = [y for x, y in src["data"]]
        ax.scatter(x, y)

    if "xLabel" in src:
        ax.set_xlabel(src["xLabel"])
    if "yLabel" in src:
        ax.set_ylabel(src["yLabel"])

    if "title" in src:
        ax.set_title(src["title"])

    ax.set_axisbelow(True)
    ax.grid()


def _plot_histogram_chart(fig: plt.Figure, ax: plt.Axes, src: dict):
    bins = src.get("bins")

    ax.hist(src["data"], bins=bins)

    if "xLabel" in src:
        ax.set_xlabel(src["xLabel"])
    if "yLabel" in src:
        ax.set_ylabel(src["yLabel"])

    if "title" in src:
        ax.set_title(src["title"])

    ax.set_axisbelow(True)
    ax.grid(axis="y")


@app.get("/image", response_class=Response)
def generate_image(src: str):
    s = _decode_src(src)

    fig, ax = plt.subplots()

    if "line" in s:
        _plot_line_chart(fig, ax, s["line"])
    elif "timeSeries" in s:
        _plot_time_series_chart(fig, ax, s["timeSeries"])
    elif "bar" in s:
        _plot_bar_chart(fig, ax, s["bar"])
    elif "pie" in s:
        _plot_pie_chart(fig, ax, s["pie"])
    elif "scatter" in s:
        _plot_scatter_chart(fig, ax, s["scatter"])
    elif "histogram" in s:
        _plot_histogram_chart(fig, ax, s["histogram"])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")

    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")
