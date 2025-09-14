"""Cost tracking for LLM usage."""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import json
from pathlib import Path


class CostTracker:
    """
    Tracks LLM usage and costs.
    
    Features:
    - Token usage tracking
    - Cost calculation and limits
    - Daily/monthly aggregation
    - Persistent storage
    """
    
    def __init__(self, 
                 max_daily_cost: float = 100.0,
                 storage_path: Optional[str] = None):
        """
        Initialize cost tracker.
        
        Args:
            max_daily_cost: Maximum allowed daily cost
            storage_path: Path to store usage data
        """
        self.max_daily_cost = max_daily_cost
        self.storage_path = storage_path or str(
            Path.home() / '.cognidb' / 'usage.json'
        )
        
        # Usage data structure
        self.usage_data = defaultdict(lambda: {
            'requests': 0,
            'tokens': {'prompt': 0, 'completion': 0, 'total': 0},
            'cost': 0.0,
            'models': defaultdict(int)
        })
        
        # Load existing data
        self._load_usage_data()
    
    def track_usage(self, 
                   cost: float,
                   token_usage: Dict[str, int],
                   model: Optional[str] = None) -> None:
        """
        Track usage for a request.
        
        Args:
            cost: Cost of the request
            token_usage: Token usage statistics
            model: Model used
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Update daily stats
        self.usage_data[today]['requests'] += 1
        self.usage_data[today]['cost'] += cost
        self.usage_data[today]['tokens']['prompt'] += token_usage.get('prompt_tokens', 0)
        self.usage_data[today]['tokens']['completion'] += token_usage.get('completion_tokens', 0)
        self.usage_data[today]['tokens']['total'] += token_usage.get('total_tokens', 0)
        
        if model:
            self.usage_data[today]['models'][model] += 1
        
        # Save data
        self._save_usage_data()
    
    def get_daily_cost(self, date: Optional[str] = None) -> float:
        """
        Get cost for a specific day.
        
        Args:
            date: Date in YYYY-MM-DD format (default: today)
            
        Returns:
            Daily cost
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        return self.usage_data.get(date, {}).get('cost', 0.0)
    
    def get_monthly_cost(self, year: int, month: int) -> float:
        """
        Get cost for a specific month.
        
        Args:
            year: Year
            month: Month (1-12)
            
        Returns:
            Monthly cost
        """
        total_cost = 0.0
        month_str = f"{year:04d}-{month:02d}"
        
        for date, data in self.usage_data.items():
            if date.startswith(month_str):
                total_cost += data.get('cost', 0.0)
        
        return total_cost
    
    def get_total_cost(self) -> float:
        """Get total cost across all time."""
        return sum(data.get('cost', 0.0) for data in self.usage_data.values())
    
    def get_token_usage(self, date: Optional[str] = None) -> Dict[str, int]:
        """
        Get token usage for a specific day.
        
        Args:
            date: Date in YYYY-MM-DD format (default: today)
            
        Returns:
            Token usage statistics
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        return self.usage_data.get(date, {}).get('tokens', {
            'prompt': 0,
            'completion': 0,
            'total': 0
        })
    
    def is_limit_exceeded(self, date: Optional[str] = None) -> bool:
        """
        Check if daily cost limit is exceeded.
        
        Args:
            date: Date to check (default: today)
            
        Returns:
            True if limit exceeded
        """
        daily_cost = self.get_daily_cost(date)
        return daily_cost >= self.max_daily_cost
    
    def get_remaining_budget(self, date: Optional[str] = None) -> float:
        """
        Get remaining budget for the day.
        
        Args:
            date: Date to check (default: today)
            
        Returns:
            Remaining budget
        """
        daily_cost = self.get_daily_cost(date)
        return max(0, self.max_daily_cost - daily_cost)
    
    def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get usage summary for recent days.
        
        Args:
            days: Number of days to include
            
        Returns:
            Usage summary
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        summary = {
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'total_cost': 0.0,
            'total_requests': 0,
            'total_tokens': 0,
            'daily_breakdown': [],
            'model_usage': defaultdict(int)
        }
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str in self.usage_data:
                data = self.usage_data[date_str]
                summary['total_cost'] += data['cost']
                summary['total_requests'] += data['requests']
                summary['total_tokens'] += data['tokens']['total']
                
                summary['daily_breakdown'].append({
                    'date': date_str,
                    'cost': data['cost'],
                    'requests': data['requests'],
                    'tokens': data['tokens']['total']
                })
                
                for model, count in data['models'].items():
                    summary['model_usage'][model] += count
            
            current_date += timedelta(days=1)
        
        summary['model_usage'] = dict(summary['model_usage'])
        summary['average_daily_cost'] = summary['total_cost'] / days
        summary['average_cost_per_request'] = (
            summary['total_cost'] / summary['total_requests'] 
            if summary['total_requests'] > 0 else 0
        )
        
        return summary
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """
        Remove usage data older than specified days.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        dates_to_remove = [
            date for date in self.usage_data.keys()
            if date < cutoff_str
        ]
        
        for date in dates_to_remove:
            del self.usage_data[date]
        
        if dates_to_remove:
            self._save_usage_data()
    
    def export_usage_report(self, 
                          start_date: str,
                          end_date: str,
                          format: str = 'json') -> str:
        """
        Export usage report for date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            format: Export format (json, csv)
            
        Returns:
            Formatted report
        """
        report_data = []
        
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            if date_str in self.usage_data:
                data = self.usage_data[date_str]
                report_data.append({
                    'date': date_str,
                    'requests': data['requests'],
                    'cost': data['cost'],
                    'prompt_tokens': data['tokens']['prompt'],
                    'completion_tokens': data['tokens']['completion'],
                    'total_tokens': data['tokens']['total'],
                    'models': dict(data['models'])
                })
            current += timedelta(days=1)
        
        if format == 'json':
            return json.dumps(report_data, indent=2)
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            if report_data:
                writer = csv.DictWriter(
                    output,
                    fieldnames=['date', 'requests', 'cost', 'prompt_tokens', 
                              'completion_tokens', 'total_tokens']
                )
                writer.writeheader()
                for row in report_data:
                    # Flatten models field
                    row_copy = row.copy()
                    del row_copy['models']
                    writer.writerow(row_copy)
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _load_usage_data(self) -> None:
        """Load usage data from storage."""
        try:
            if Path(self.storage_path).exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Convert to defaultdict structure
                    for date, usage in data.items():
                        self.usage_data[date] = usage
                        if 'models' in usage:
                            self.usage_data[date]['models'] = defaultdict(
                                int, usage['models']
                            )
        except Exception:
            # If loading fails, start fresh
            pass
    
    def _save_usage_data(self) -> None:
        """Save usage data to storage."""
        try:
            # Ensure directory exists
            Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Convert defaultdict to regular dict for JSON serialization
            data_to_save = {}
            for date, usage in self.usage_data.items():
                data_to_save[date] = {
                    'requests': usage['requests'],
                    'tokens': usage['tokens'],
                    'cost': usage['cost'],
                    'models': dict(usage['models'])
                }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception:
            # Log error but don't fail the request
            pass