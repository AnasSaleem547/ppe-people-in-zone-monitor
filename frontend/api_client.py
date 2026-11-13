import httpx
from urllib.parse import quote


class APIError(RuntimeError):
    pass


class APIClient:
    def __init__(self, base_url, transport=None):
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def _request(self, method, path, **kwargs):
        try:
            with httpx.Client(base_url=self.base_url, transport=self.transport,
                              timeout=httpx.Timeout(300, connect=5)) as client:
                response = client.request(method, path, **kwargs)
            if response.is_error:
                try:
                    detail = response.json().get("detail", "Request failed.")
                except ValueError:
                    detail = "The backend could not complete this request."
                if isinstance(detail, list):
                    detail = "; ".join(str(item.get("msg", "Invalid input")) for item in detail)
                raise APIError(str(detail))
            return response.json()
        except httpx.RequestError as exc:
            raise APIError("Cannot reach the backend. Check that FastAPI is running, then try again.") from exc

    def upload(self, file, filename):
        file.seek(0)
        return self._request("POST", "/api/uploads", files={"file": (filename, file, "application/octet-stream")})

    def submit(self, payload, request_key):
        return self._request("POST", "/api/jobs", json=payload, headers={"Idempotency-Key": request_key})

    def status(self, job_id):
        return self._request("GET", f"/api/jobs/{quote(job_id, safe='')}")
