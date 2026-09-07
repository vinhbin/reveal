import subprocess
import sys


def test_database_ssl_requirement_is_preserved():
    # Use a fresh import because configuration is evaluated at module load.
    code = '''
import os
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/reveal?sslmode=require&channel_binding=require'
from backend.config import DATABASE_URL
from urllib.parse import urlsplit, parse_qs
assert DATABASE_URL.startswith('postgresql+asyncpg://')
assert parse_qs(urlsplit(DATABASE_URL).query)['ssl'] == ['require']
assert 'channel_binding' not in parse_qs(urlsplit(DATABASE_URL).query)
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
