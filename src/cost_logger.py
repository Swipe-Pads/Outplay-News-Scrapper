"""
Persistent cost tracking for AI API usage.

Logs API usage and costs to a file for long-term monitoring.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class PersistentCostLogger:
    """
    Log API costs to a JSON file for persistent tracking.
    """

    def __init__(self, log_file: str = "logs/api_costs.json"):
        """
        Initialize the cost logger.

        Args:
            log_file: Path to the cost log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.log_file.exists():
            self._write_log([])

    def _read_log(self) -> List[Dict]:
        """Read the cost log file."""
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_log(self, entries: List[Dict]):
        """Write entries to the cost log file."""
        with open(self.log_file, 'w') as f:
            json.dump(entries, f, indent=2)

    def log_usage(
        self,
        operation: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        metadata: Dict = None
    ):
        """
        Log an API usage event.

        Args:
            operation: Type of operation (e.g., "summarize_single", "summarize_batch")
            model: Model used (e.g., "claude-sonnet-4-20250514")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Total cost in USD
            metadata: Optional additional metadata (e.g., article_id, article_title)
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'operation': operation,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost_usd': round(cost, 6),
            'metadata': metadata or {}
        }

        # Read existing entries
        entries = self._read_log()

        # Add new entry
        entries.append(entry)

        # Write back
        self._write_log(entries)

        logger.debug(f"Logged API usage: {operation}, {entry['total_tokens']} tokens, ${cost:.6f}")

    def get_total_cost(self, since: datetime = None) -> float:
        """
        Get total cost since a given time.

        Args:
            since: Optional datetime to filter from (UTC)

        Returns:
            Total cost in USD
        """
        entries = self._read_log()

        if since:
            entries = [
                e for e in entries
                if datetime.fromisoformat(e['timestamp'].rstrip('Z')) >= since
            ]

        return sum(e['cost_usd'] for e in entries)

    def get_usage_stats(self, since: datetime = None) -> Dict:
        """
        Get usage statistics since a given time.

        Args:
            since: Optional datetime to filter from (UTC)

        Returns:
            Dictionary with usage statistics
        """
        entries = self._read_log()

        if since:
            entries = [
                e for e in entries
                if datetime.fromisoformat(e['timestamp'].rstrip('Z')) >= since
            ]

        if not entries:
            return {
                'total_requests': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_tokens': 0,
                'total_cost_usd': 0.0,
                'operations': {}
            }

        # Aggregate stats
        stats = {
            'total_requests': len(entries),
            'total_input_tokens': sum(e['input_tokens'] for e in entries),
            'total_output_tokens': sum(e['output_tokens'] for e in entries),
            'total_tokens': sum(e['total_tokens'] for e in entries),
            'total_cost_usd': sum(e['cost_usd'] for e in entries),
            'operations': {}
        }

        # Break down by operation
        for entry in entries:
            op = entry['operation']
            if op not in stats['operations']:
                stats['operations'][op] = {
                    'count': 0,
                    'total_tokens': 0,
                    'total_cost_usd': 0.0
                }

            stats['operations'][op]['count'] += 1
            stats['operations'][op]['total_tokens'] += entry['total_tokens']
            stats['operations'][op]['total_cost_usd'] += entry['cost_usd']

        return stats

    def print_stats(self, since: datetime = None):
        """
        Print usage statistics.

        Args:
            since: Optional datetime to filter from (UTC)
        """
        stats = self.get_usage_stats(since)

        print("=" * 60)
        print("API USAGE STATISTICS")
        if since:
            print(f"Since: {since.isoformat()}")
        print("=" * 60)
        print(f"Total requests: {stats['total_requests']}")
        print(f"Total tokens: {stats['total_tokens']:,}")
        print(f"  - Input: {stats['total_input_tokens']:,}")
        print(f"  - Output: {stats['total_output_tokens']:,}")
        print(f"Total cost: ${stats['total_cost_usd']:.6f}")
        print()

        if stats['operations']:
            print("By operation:")
            print("-" * 60)
            for op, op_stats in stats['operations'].items():
                print(f"  {op}:")
                print(f"    Requests: {op_stats['count']}")
                print(f"    Tokens: {op_stats['total_tokens']:,}")
                print(f"    Cost: ${op_stats['total_cost_usd']:.6f}")
                print()

        print("=" * 60)


# Global cost logger instance
cost_logger = PersistentCostLogger()


if __name__ == '__main__':
    """
    Test the cost logger.
    """
    print("Testing PersistentCostLogger")
    print()

    # Create a test logger
    test_logger = PersistentCostLogger("logs/test_api_costs.json")

    # Log some test usage
    test_logger.log_usage(
        operation="summarize_single",
        model="claude-sonnet-4-20250514",
        input_tokens=250,
        output_tokens=60,
        cost=0.0016,
        metadata={'article_id': 1, 'article_title': 'Test Article'}
    )

    test_logger.log_usage(
        operation="summarize_batch",
        model="claude-sonnet-4-20250514",
        input_tokens=1500,
        output_tokens=350,
        cost=0.0095,
        metadata={'batch_size': 5}
    )

    # Print stats
    test_logger.print_stats()

    # Clean up test file
    Path("logs/test_api_costs.json").unlink(missing_ok=True)

    print("\n✅ Test complete!")
