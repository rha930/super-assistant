# Graph Artifact Integration Guide

This document explains how the backend/agent should return graph artifacts to be rendered in the frontend.

## Graph Payload Contract

The agent can include `artifacts` in the streaming response payload to return graph data that will be rendered in the dedicated Graph Panel.

### Response Format

```json
{
  "chunk": "Here is the trend analysis...",
  "artifacts": [
    {
      "type": "graph",
      "graph": {
        "id": "trend_001",
        "title": "Weekly Revenue Trend",
        "chartType": "line",
        "xLabel": "Week",
        "yLabel": "Revenue ($)",
        "series": [
          {
            "name": "Revenue",
            "data": [
              { "x": "W1", "y": 1200 },
              { "x": "W2", "y": 1500 },
              { "x": "W3", "y": 1800 },
              { "x": "W4", "y": 1600 }
            ]
          }
        ],
        "options": {
          "stacked": false,
          "showLegend": true
        }
      }
    }
  ]
}
```

## Supported Chart Types

- `line` - Line chart (default)
- `bar` - Bar chart
- `pie` - Pie/Doughnut chart

## Graph Payload Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for the graph |
| `title` | string | Yes | Human-readable title |
| `chartType` | 'line' \| 'bar' \| 'pie' | Yes | Type of chart to render |
| `xLabel` | string | No | X-axis label (for line/bar) |
| `yLabel` | string | No | Y-axis label (for line/bar) |
| `series` | Series[] | Yes | Array of data series |
| `options` | object | No | Render options |

### Series Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Series name for legend |
| `data` | DataPoint[] | Yes | Array of x/y data points (min 1) |

### DataPoint Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `x` | string \| number | Yes | X-axis value |
| `y` | number | Yes | Y-axis value |

### Options Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stacked` | boolean | false | Stack series on top of each other (line/bar) |
| `showLegend` | boolean | true | Display chart legend |

## Validation

The frontend will validate all graph payloads before rendering. Invalid payloads will:
1. Not crash the application
2. Show an error message in the graph panel
3. Log details to browser console

Common validation errors:
- Missing required fields (`id`, `title`, `chartType`, `series`)
- Invalid chart type (not one of: line, bar, pie)
- Empty series array
- Missing or invalid data points (x/y values)

## Example Usage

### Python Backend Example

```python
from flask import jsonify
from datetime import datetime

def get_data_analysis(query):
    # Analyze data and prepare response with graph
    
    graph_payload = {
        "type": "graph",
        "graph": {
            "id": f"graph_{datetime.now().timestamp()}",
            "title": "Data Analysis Results",
            "chartType": "bar",
            "xLabel": "Category",
            "yLabel": "Count",
            "series": [
                {
                    "name": "Count",
                    "data": [
                        {"x": "A", "y": 10},
                        {"x": "B", "y": 20},
                        {"x": "C", "y": 15}
                    ]
                }
            ],
            "options": {
                "showLegend": False
            }
        }
    }
    
    return {
        "success": True,
        "data": {
            "message": "Analysis complete",
            "artifacts": [graph_payload]
        }
    }
```

## Frontend Integration

The frontend will:
1. Automatically extract graph artifacts from agent responses
2. Validate payloads using schema validation
3. Store graphs in per-conversation state
4. Display in dedicated Graph Panel
5. Allow user to select between multiple graphs in single response
6. Persist graph data until conversation changes

## Best Practices

- Use meaningful graph titles
- Include axis labels for clarity (line/bar charts)
- Keep series names short and descriptive
- Limit data points to reasonable count (~100 max recommended)
- Use consistent data types across series
- Provide sensible defaults in options

## Limitations

- Graphs are scoped to the current conversation
- Graphs do not persist across sessions
- Only one graph displayed at a time (though multiple can be returned)
- Chart rendering is client-side only (no server-side image export)
