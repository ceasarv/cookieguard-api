# scanner/scan_subprocess.py
"""
Run scans in a subprocess to avoid Celery/asyncio conflicts on Windows.
"""
import subprocess
import sys
import json
import os
import logging

logger = logging.getLogger("scanner")

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_scan_in_subprocess(url: str) -> dict:
    """
    Run a scan in a separate Python process to avoid asyncio issues with Celery on Windows.
    """
    # Escape any quotes in the URL to prevent injection
    safe_url = url.replace('"', '\\"').replace("'", "\\'")

    script = f'''
import sys
import json
sys.path.insert(0, r"{PROJECT_ROOT}")
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cookieguard.settings')

# Suppress logging to stderr so it doesn't interfere with JSON output
import logging
logging.disable(logging.CRITICAL)

import django
django.setup()

import asyncio
from scanner.scan import scan_site

async def main():
    try:
        result = await scan_site("{safe_url}")
        # Use special markers to reliably find the JSON output
        print("__SCAN_RESULT_START__")
        print(json.dumps(result))
        print("__SCAN_RESULT_END__")
    except Exception as e:
        print("__SCAN_RESULT_START__")
        print(json.dumps({{"error": str(e)}}))
        print("__SCAN_RESULT_END__")

asyncio.run(main())
'''

    try:
        logger.info(f"[scan_subprocess] Running scan for: {url}")
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=PROJECT_ROOT,
        )

        # Log stderr for debugging (but don't fail on it)
        if result.stderr:
            logger.debug(f"[scan_subprocess] stderr: {result.stderr[-500:]}")

        # Parse the JSON output from stdout using markers
        output = result.stdout

        # Look for our marked JSON output
        start_marker = "__SCAN_RESULT_START__"
        end_marker = "__SCAN_RESULT_END__"

        if start_marker in output and end_marker in output:
            start_idx = output.index(start_marker) + len(start_marker)
            end_idx = output.index(end_marker)
            json_str = output[start_idx:end_idx].strip()
            if json_str:
                logger.info(f"[scan_subprocess] Successfully parsed result")
                return json.loads(json_str)

        # Fallback: check return code and try to find JSON
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            if "Timeout" in error_msg:
                error_msg = "Page load timed out"
            elif len(error_msg) > 300:
                error_msg = error_msg[-300:]
            logger.error(f"[scan_subprocess] Process failed: {error_msg}")
            return {"error": f"Scan process failed: {error_msg}"}

        # Try to find JSON in output without markers
        output = output.strip()
        if not output:
            return {"error": "No output from scan process"}

        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        return {"error": "Could not find valid JSON in scan output"}

    except subprocess.TimeoutExpired:
        logger.error("[scan_subprocess] Scan timed out after 120 seconds")
        return {"error": "Scan timed out after 120 seconds"}
    except json.JSONDecodeError as e:
        logger.error(f"[scan_subprocess] JSON decode error: {e}")
        return {"error": f"Failed to parse scan result: {str(e)}"}
    except Exception as e:
        logger.error(f"[scan_subprocess] Subprocess error: {e}")
        return {"error": f"Subprocess error: {str(e)}"}
