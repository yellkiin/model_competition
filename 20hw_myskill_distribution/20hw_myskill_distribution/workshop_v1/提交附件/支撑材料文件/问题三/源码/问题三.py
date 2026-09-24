"""Question-specific entry point for formal candidate replay and validation."""
import argparse
from support_reproduce import solve, validate

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('solve', 'validate'))
    args = parser.parse_args()
    (solve if args.action == 'solve' else validate)()
