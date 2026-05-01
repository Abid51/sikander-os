"""
Plugin: Data Analysis System
Migrated to IgrisPlugin base class
"""

import logging
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.core.plugin_loader import IgrisPlugin

logger = logging.getLogger(__name__)


class DataAnalysisPlugin(IgrisPlugin):
    """Data analysis and reporting plugin"""

    NAME = "data_analysis"
    VERSION = "1.0.0"
    AUTHOR = "Igris Team"
    DESCRIPTION = "Advanced data analysis and reporting"

    def __init__(self):
        self.datasets: Dict[str, List[float]] = {}

    def on_load(self):
        logger.info(f"[PLUGIN: {self.NAME}] Data analysis plugin loaded ✅")

    def on_unload(self):
        self.datasets.clear()
        logger.info(f"[PLUGIN: {self.NAME}] Unloaded.")

    def on_command(self, command: str, args: dict) -> Optional[Any]:
        if command == "analyze_data":
            return self._analyze_data(args)
        elif command == "create_report":
            return self._create_report(args)
        elif command == "predict_trend":
            return self._predict_trend(args)
        elif command == "store_dataset":
            return self._store_dataset(args)
        return None

    def _analyze_data(self, args: dict) -> dict:
        data = args.get("data", [])
        dataset_name = args.get("dataset_name")

        if not data:
            return {"error": "No data provided"}

        try:
            numeric = [float(x) for x in data]
        except ValueError as e:
            return {"error": f"Invalid data format: {e}"}

        analysis = {
            "count": len(numeric),
            "sum": sum(numeric),
            "min": min(numeric),
            "max": max(numeric),
            "mean": statistics.mean(numeric),
            "median": statistics.median(numeric),
            "stdev": statistics.stdev(numeric) if len(numeric) > 1 else 0,
            "variance": statistics.variance(numeric) if len(numeric) > 1 else 0,
        }

        if dataset_name:
            self.datasets[dataset_name] = numeric

        return {"status": "success", "analysis": analysis, "dataset_name": dataset_name, "timestamp": datetime.now().isoformat()}

    def _create_report(self, args: dict) -> dict:
        name = args.get("dataset_name")
        title = args.get("title", "Data Analysis Report")

        if name not in self.datasets:
            return {"error": f"Dataset not found: {name}"}

        data = self.datasets[name]
        sorted_data = sorted(data)
        n = len(sorted_data)

        return {
            "status": "success",
            "report": {
                "title": title,
                "dataset": name,
                "data_points": n,
                "analysis": {
                    "min": min(data), "max": max(data),
                    "mean": statistics.mean(data), "median": statistics.median(data),
                    "stdev": statistics.stdev(data) if n > 1 else 0,
                },
                "quartiles": {
                    "q1": sorted_data[n // 4] if n > 3 else sorted_data[0],
                    "q2": sorted_data[n // 2] if n > 1 else sorted_data[0],
                    "q3": sorted_data[3 * n // 4] if n > 3 else sorted_data[-1],
                },
                "range": max(data) - min(data),
                "generated_at": datetime.now().isoformat(),
            },
        }

    def _predict_trend(self, args: dict) -> dict:
        name = args.get("dataset_name")
        periods = args.get("periods", 3)

        if name not in self.datasets:
            return {"error": f"Dataset not found: {name}"}

        data = self.datasets[name]
        if len(data) < 2:
            return {"error": "Need at least 2 data points"}

        trend = (data[-1] - data[0]) / len(data)
        predictions = [data[-1] + trend * (i + 1) for i in range(periods)]

        return {"status": "success", "dataset": name, "current_value": data[-1], "predictions": predictions, "method": "linear_regression"}

    def _store_dataset(self, args: dict) -> dict:
        name = args.get("name")
        data = args.get("data", [])

        if not name or not data:
            return {"error": "Missing name or data"}

        self.datasets[name] = [float(x) for x in data]
        return {"status": "stored", "dataset": name, "size": len(data), "total_datasets": len(self.datasets)}

    def get_commands(self) -> list:
        return [
            {"name": "analyze_data", "args": ["data", "dataset_name"], "description": "Analyze numeric data"},
            {"name": "create_report", "args": ["dataset_name", "title"], "description": "Create analysis report"},
            {"name": "predict_trend", "args": ["dataset_name", "periods"], "description": "Predict future trends"},
            {"name": "store_dataset", "args": ["name", "data"], "description": "Store dataset for later"},
        ]

    def get_status(self) -> dict:
        return {"status": "active", "datasets_stored": len(self.datasets)}
