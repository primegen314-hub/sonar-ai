"""HTTP client on urllib with corporate proxy auto-detection.

Strategy: try a direct connection first; on a DNS/connect failure, detect the
Windows proxy (static registry proxy, then PAC) and retry once through it.
"""
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


class HttpError(Exception):
    def __init__(self, status, body, url):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.body = body
        self.url = url


def _get_registry_proxy():
    """Return (static_proxy, pac_url) from the Windows registry, or (None, None)."""
    if sys.platform != "win32":
        return None, None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        static_proxy = None
        pac_url = None
        try:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if enabled:
                raw, _ = winreg.QueryValueEx(key, "ProxyServer")
                if raw:
                    # can be "host:port" or "http=host:port;https=host:port"
                    if "=" in raw:
                        for part in raw.split(";"):
                            k, _, v = part.partition("=")
                            if k.strip().lower() in ("https", "http") and v:
                                static_proxy = v.strip()
                                break
                    else:
                        static_proxy = raw.strip()
        except OSError:
            pass
        try:
            pac_url, _ = winreg.QueryValueEx(key, "AutoConfigURL")
        except OSError:
            pass
        winreg.CloseKey(key)
        if static_proxy and not static_proxy.startswith("http"):
            static_proxy = "http://" + static_proxy
        return static_proxy, pac_url or None
    except Exception as e:  # registry read must never be fatal
        print(f"  proxy registry read failed: {e}")
        return None, None


def _fetch_pac(pac_url):
    try:
        req = urllib.request.Request(pac_url, headers={"User-Agent": "Python/proxy-detect"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  PAC fetch failed: {e}")
        return None


def detect_proxy():
    """Best-effort proxy URL for this machine, or None."""
    static_proxy, pac_url = _get_registry_proxy()
    if static_proxy:
        print(f"  static proxy: {static_proxy}")
        return static_proxy
    if not pac_url:
        return None
    print(f"  PAC URL: {pac_url}")
    content = _fetch_pac(pac_url)
    if content:
        m = re.search(r"PROXY\s+([\w.\-]+:\d+)", content, re.IGNORECASE)
        if m:
            proxy = "http://" + m.group(1)
            print(f"  proxy from PAC: {proxy}")
            return proxy
    parsed = urllib.parse.urlparse(pac_url)
    if parsed.hostname and parsed.port:
        fallback = f"http://{parsed.hostname}:{parsed.port}"
        print(f"  falling back to PAC host as proxy: {fallback}")
        return fallback
    return None


class HttpClient:
    def __init__(self, verify_ssl=True):
        if verify_ssl:
            self._ssl_ctx = ssl.create_default_context()
        else:
            self._ssl_ctx = ssl._create_unverified_context()
        self._opener = self._make_opener(proxy=None)
        self._proxy_tried = False
        self.last_headers = {}

    def _make_opener(self, proxy=None):
        handlers = [urllib.request.HTTPSHandler(context=self._ssl_ctx)]
        if proxy:
            handlers.insert(0, urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
        return urllib.request.build_opener(*handlers)

    def _open(self, req, timeout):
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)

    def request(self, url, method="GET", headers=None, form=None, json_body=None, timeout=30):
        """Return (status, body_bytes). Raises HttpError on HTTP >= 400.

        `form` (dict) is sent urlencoded as the request body;
        `json_body` (any JSON-serializable value) is sent as application/json.
        The response headers of the last successful request are kept in
        `self.last_headers` (needed e.g. for GitHub's X-OAuth-Scopes probe).
        """
        data = None
        headers = dict(headers or {})
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            try:
                status, body, resp_headers = self._open(req, timeout)
            except urllib.error.HTTPError:
                raise
            except Exception as exc:
                if self._proxy_tried or not _looks_like_network_failure(exc):
                    raise
                print(f"  direct connection failed ({exc}); detecting proxy ...")
                self._proxy_tried = True
                proxy = detect_proxy()
                if not proxy:
                    raise
                self._opener = self._make_opener(proxy=proxy)
                status, body, resp_headers = self._open(req, timeout)
        except urllib.error.HTTPError as e:
            raise HttpError(e.code, e.read().decode("utf-8", errors="replace"), url) from None
        if status >= 400:
            raise HttpError(status, body.decode("utf-8", errors="replace"), url)
        self.last_headers = resp_headers
        return status, body

    def request_json(self, url, **kwargs):
        _, body = self.request(url, **kwargs)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))


def _looks_like_network_failure(exc):
    text = str(exc)
    return any(marker in text for marker in ("getaddrinfo", "11001", "timed out", "Connection refused", "Name or service"))
