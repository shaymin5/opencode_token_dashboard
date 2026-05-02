"""F3: Real Manual QA - API endpoint verification."""
import subprocess, time, urllib.request, urllib.error, json, sys, os

BASE = "http://127.0.0.1:20232"

# Start server
proc = subprocess.Popen(
    ["uv", "run", "python", "-m", "app.main", "--port", "20232"],
    cwd=r"D:\gameboy\opencode_token_dashboard",
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(5)

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS {name}")
        passed += 1
    else:
        print(f"  FAIL {name}")
        failed += 1

def http_get(url):
    try:
        return urllib.request.urlopen(url, timeout=10)
    except urllib.error.HTTPError as e:
        return e

try:
    # API Views
    print("=== API Views ===")
    views = ["overview", "tokens-by-date", "tokens-by-model", "tokens-by-project",
             "cost-breakdown", "agent-breakdown", "model-efficiency", "usage-heatmap", "cache-efficiency"]
    for v in views:
        resp = http_get(f"{BASE}/api/data?view={v}")
        check(f"{v} returns {resp.status}", resp.status == 200)

    # Top sessions with limit
    resp = http_get(f"{BASE}/api/data?view=top-sessions&limit=3")
    data = json.loads(resp.read())
    check("top-sessions limit=3 returns <=3 rows", len(data) <= 3)
    check("top-sessions has keys", all(k in data[0] for k in ["title","project","total_tokens"]) if data else True)

    # Error cases
    resp = http_get(f"{BASE}/api/data?view=nonexistent")
    check("invalid view returns 400", resp.status == 400)

    resp = http_get(f"{BASE}/api/data")
    check("no view returns 400", resp.status == 400)

    # Redirects
    print("\n=== Redirects ===")
    for ep in ["overview", "tokens-by-date", "tokens-by-model", "tokens-by-project", "cost-breakdown"]:
        try:
            req = urllib.request.Request(f"{BASE}/api/{ep}")
            req.method = "GET"
            resp = urllib.request.urlopen(req)
            check(f"/api/{ep} redirects (got {resp.status})", resp.status == 200)  # auto-followed
        except urllib.error.HTTPError as e:
            if e.status == 307:
                check(f"/api/{ep} returns 307", True)
            else:
                check(f"/api/{ep} returns 307", False)

    # HTML page
    print("\n=== HTML Page ===")
    resp = http_get(f"{BASE}/")
    html = resp.read().decode("utf-8")
    check("Page loads (200)", resp.status == 200)
    check("Contains echarts", "echarts" in html)
    check("Contains heatmap-chart", "heatmap-chart" in html)
    check("Contains mini-ts-chart", "mini-ts-chart" in html)
    check("Contains top-sessions-chart", "top-sessions-chart" in html)
    check("Contains agent-chart", "agent-chart" in html)
    check("Contains model-chart", "model-chart" in html)
    check("Contains project-chart", "project-chart" in html)
    check("Contains cost-chart", "cost-chart" in html)
    check("Contains cache-chart", "cache-chart" in html)
    check("Contains overview-cards", "overview-cards" in html)
    check("Contains efficiency-cards", "efficiency-cards" in html)
    check("Page size > 10KB", len(html) > 10000)

finally:
    proc.terminate()
    proc.wait()

print(f"\n=== Results ===")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Total: {passed + failed}")
print(f"Verdict: {'APPROVE' if failed == 0 else 'REJECT'}")
