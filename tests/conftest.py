"""Put the site root on sys.path so tests can import the generator modules."""
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SITE_ROOT not in sys.path:
    sys.path.insert(0, SITE_ROOT)
