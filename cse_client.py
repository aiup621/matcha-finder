import os, json, datetime as dt
import requests

class DailyQuotaExceeded(Exception): pass

class CSEClient:
    def __init__(self, api_key, cx, max_daily=100, state_path=".cse_usage.json", timeout=20):
        self.api_key = api_key
        self.cx = cx
        self.max_daily = int(os.getenv("MAX_DAILY_CSE_QUERIES", max_daily))
        self.state_path = state_path
        self.timeout = timeout
        self._load_state()

    def _today(self):
        return dt.date.today().isoformat()

    def _load_state(self):
        self.state = {"date": self._today(), "used": 0}
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                if s.get("date") == self._today():
                    self.state = s
            except Exception:
                pass

    def _save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False)
        except Exception:
            pass

    def remaining(self):
        if self.state.get("date") != self._today():
            self.state = {"date": self._today(), "used": 0}
        return max(0, self.max_daily - self.state.get("used", 0))

    def _bump(self):
        self.state["date"] = self._today()
        self.state["used"] = self.state.get("used", 0) + 1
        self._save_state()

    def _is_quota_error(self, resp):
        if resp.status_code in (429, 403):
            try:
                err = resp.json().get("error", {})
                reasons = [ (e.get("reason") or "").lower() for e in err.get("errors", []) ]
                text = " ".join(reasons + [(err.get("status") or "").lower()])
                if any(k in text for k in ("daily", "rate", "quota", "resource_exhausted")):
                    return True
            except Exception:
                return True
        return False

    def search(self, q, start=1, num=10, safe="off", lr=None, cr=None):
        if self.remaining() <= 0:
            raise DailyQuotaExceeded("Daily query budget exhausted")
        params = {"key": self.api_key, "cx": self.cx, "q": q, "num": num, "start": start, "safe": safe}
        if lr: params["lr"] = lr
        if cr: params["cr"] = cr
        url = "https://www.googleapis.com/customsearch/v1"
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"Network error: {e}")
        if self._is_quota_error(resp):
            raise DailyQuotaExceeded("Google CSE daily limit or rate limit reached")
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        self._bump()
        return resp.json()
