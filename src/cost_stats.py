"""
CLI tool for viewing API cost statistics.

Usage:
    python src/cost_stats.py              # Show all-time stats
    python src/cost_stats.py --today      # Show today's stats
    python src/cost_stats.py --week       # Show last 7 days
    python src/cost_stats.py --month      # Show last 30 days
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cost_logger import cost_logger


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='View API cost statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--today', action='store_true', help='Show today\'s stats only')
    parser.add_argument('--week', action='store_true', help='Show last 7 days')
    parser.add_argument('--month', action='store_true', help='Show last 30 days')
    parser.add_argument('--since', help='Show stats since date (YYYY-MM-DD)')

    args = parser.parse_args()

    # Determine time filter
    since = None
    time_desc = "All Time"

    if args.today:
        since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        time_desc = "Today"
    elif args.week:
        since = datetime.utcnow() - timedelta(days=7)
        time_desc = "Last 7 Days"
    elif args.month:
        since = datetime.utcnow() - timedelta(days=30)
        time_desc = "Last 30 Days"
    elif args.since:
        try:
            since = datetime.fromisoformat(args.since)
            time_desc = f"Since {args.since}"
        except ValueError:
            print(f"❌ Invalid date format: {args.since}")
            print("Use YYYY-MM-DD format")
            sys.exit(1)

    # Get and display stats
    print()
    print("=" * 70)
    print(f"API COST STATISTICS - {time_desc}")
    print("=" * 70)
    print()

    stats = cost_logger.get_usage_stats(since=since)

    if stats['total_requests'] == 0:
        print("No API usage recorded for this period.")
        print()
        sys.exit(0)

    # Overall stats
    print(f"Total Requests: {stats['total_requests']}")
    print(f"Total Tokens: {stats['total_tokens']:,}")
    print(f"  • Input Tokens: {stats['total_input_tokens']:,}")
    print(f"  • Output Tokens: {stats['total_output_tokens']:,}")
    print()
    print(f"Total Cost: ${stats['total_cost_usd']:.6f}")
    print()

    # Breakdown by operation
    if stats['operations']:
        print("-" * 70)
        print("BREAKDOWN BY OPERATION")
        print("-" * 70)
        print()

        for op, op_stats in sorted(stats['operations'].items()):
            avg_tokens = op_stats['total_tokens'] / op_stats['count']
            avg_cost = op_stats['total_cost_usd'] / op_stats['count']

            print(f"  {op}:")
            print(f"    Requests: {op_stats['count']}")
            print(f"    Total Tokens: {op_stats['total_tokens']:,}")
            print(f"    Total Cost: ${op_stats['total_cost_usd']:.6f}")
            print(f"    Avg per Request: {avg_tokens:.0f} tokens, ${avg_cost:.6f}")
            print()

    print("=" * 70)
    print()


if __name__ == '__main__':
    main()
