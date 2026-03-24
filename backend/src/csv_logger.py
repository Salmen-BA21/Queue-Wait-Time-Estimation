"""
Local CSV logging for queue metrics.
Provides backup persistence for metrics and alerts.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


class CSVMetricsLogger:
    """Logs queue metrics to a local CSV file."""

    def __init__(self, output_dir: str | Path = "data"):
        """
        Initialize CSV logger.
        
        Args:
            output_dir: Directory to store CSV files (default: 'data')
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create timestamped CSV file path
        timestamp = datetime.now().strftime("%Y-%m-%d")
        self.csv_path = self.output_dir / f"queue_metrics_{timestamp}.csv"
        
        # Check if file exists to determine if we need to write headers
        self.file_exists = self.csv_path.exists()
        
        # Define CSV column headers
        self.headers = [
            "timestamp", "frame_id", "source", "people_in_zone",
            "arrival_rate", "service_rate", "estimated_wait_sec",
            "arrival_rate_lower", "arrival_rate_upper",
            "service_rate_lower", "service_rate_upper",
            "wait_time_lower", "wait_time_upper",
            "uncertainty_level", "queue_stable", "alert_triggered", "alert_message",
            "establishment_name", "section_name", "employee_name"
        ]
        
        # Write headers if file is new
        if not self.file_exists:
            self._write_headers()
    
    def _write_headers(self) -> None:
        """Write header row to CSV file."""
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
    
    def log_metrics(self, payload: dict) -> None:
        """
        Log a single metrics payload to CSV.
        
        Args:
            payload: Dictionary with queue metrics (matches QueuePayload structure)
        """
        try:
            # Ensure all required fields are present
            row_data = {header: payload.get(header, "") for header in self.headers}
            
            with open(self.csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow(row_data)
        except Exception as e:
            print(f"[CSV Logger] Error logging metrics: {e}")
    
    def log_alert(self, alert_type: str, message: str) -> None:
        """
        Log an alert event to a separate alerts CSV file.
        
        Args:
            alert_type: Type of alert (e.g., "queue_threshold", "rate_spike")
            message: Alert message details
        """
        try:
            alert_file = self.output_dir / f"alerts_{datetime.now().strftime('%Y-%m-%d')}.csv"
            
            # Write headers if new file
            if not alert_file.exists():
                with open(alert_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["timestamp", "type", "message"])
                    writer.writeheader()
            
            # Append alert
            alert_data = {
                "timestamp": datetime.now().isoformat(),
                "type": alert_type,
                "message": message
            }
            
            with open(alert_file, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "type", "message"])
                writer.writerow(alert_data)
        except Exception as e:
            print(f"[CSV Logger] Error logging alert: {e}")
    
    def get_csv_path(self) -> Path:
        """Return the path to the current CSV file."""
        return self.csv_path
