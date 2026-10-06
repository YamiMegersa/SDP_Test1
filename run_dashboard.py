#!/usr/bin/env python3
"""Run the RAT dashboard web server."""

from rat_metric_engine import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
