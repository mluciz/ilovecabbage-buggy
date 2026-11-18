#!/usr/bin/env python3
"""Backward-compatible entrypoint for schema-2 three-ToF simulator.

The old schema-1 single-sensor sender was intentionally replaced; it no longer
matches the Unreal receiver. Use demo_sender.py for all current options.
"""
from demo_sender import main

if __name__ == "__main__":
    main()
