"""
power_automate.py
Power Automate Management API Python 클라이언트

사전 준비:
  pip install requests

사용 예시:
  from power_automate import PowerAutomateClient

  client = PowerAutomateClient(
      tenant_id="...",
      client_id="...",
      client_secret="...",
      environment_id="Default-...",
  )

  # 비동기 실행
  run_id = client.run_flow(flow_id="...")

  # 동기 실행 (완료까지 대기)
  result = client.run_flow_sync(flow_id="...", body={"name": "홍길동"}, timeout=300)
  print(result.status)   # "Succeeded"
  print(result.duration) # 42.0 (초)
"""

import time
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────
_API_BASE = "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple"
_API_VERSION = "2016-11-01"
_SCOPE = "https://service.flow.microsoft.com/.default"
_CLIENT_SCOPE = "https://service.flow.microsoft.com"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

TERMINAL_STATUSES = {"Succeeded", "Failed", "Cancelled", "TimedOut"}


# ─────────────────────────────────────────────────────────────
# 데이터 클래스
# ─────────────────────────────────────────────────────────────
@dataclass
class FlowInfo:
    """Flow 기본 정보"""

    flow_id: str
    display_name: str
    state: str  # "Started" | "Stopped"

    @property
    def is_active(self) -> bool:
        return self.state == "Started"

    def __repr__(self):
        icon = "✅" if self.is_active else "⏸"
        return f"FlowInfo({icon} '{self.display_name}', id={self.flow_id})"


@dataclass
class RunResult:
    """Flow 실행 결과"""

    run_id: str
    status: str  # Succeeded | Failed | Cancelled | TimedOut
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    error: Optional[dict] = field(default=None)
    raw: Optional[dict] = field(default=None, repr=False)

    @property
    def succeeded(self) -> bool:
        return self.status == "Succeeded"

    @property
    def duration(self) -> Optional[float]:
        """소요 시간 (초). 시작/종료 시각이 없으면 None."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def __repr__(self):
        icon = "✅" if self.succeeded else "❌"
        dur = f", duration={self.duration:.1f}s" if self.duration is not None else ""
        return f"RunResult({icon} status='{self.status}'{dur}, run_id={self.run_id})"


# ─────────────────────────────────────────────────────────────
# 예외
# ─────────────────────────────────────────────────────────────
class PowerAutomateError(Exception):
    """API 호출 오류"""


class AuthError(PowerAutomateError):
    """인증 오류"""


class FlowRunError(PowerAutomateError):
    """Flow 실행 오류"""


class PollTimeoutError(PowerAutomateError):
    """폴링 타임아웃"""


# ─────────────────────────────────────────────────────────────
# 클라이언트
# ─────────────────────────────────────────────────────────────
class PowerAutomateClient:
    """
    Power Automate Management API 클라이언트

    Parameters
    ----------
    tenant_id      : Azure AD 테넌트 ID
    client_id      : 앱 등록 클라이언트 ID
    client_secret  : 앱 등록 클라이언트 시크릿
    environment_id : Power Platform 환경 ID
                     (Power Platform Admin Center에서 확인)
    poll_interval  : 동기 실행 시 폴링 간격 (초, 기본 5)
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        environment_id: str,
        poll_interval: int = 5,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment_id = environment_id
        self.poll_interval = poll_interval

        self._token: Optional[str] = None
        self._token_exp: float = 0.0
        self._session = requests.Session()

    # ── 인증 ────────────────────────────────────────────────
    def _get_token(self) -> str:
        """액세스 토큰 반환 (만료 시 자동 갱신)"""
        if self._token and time.time() < self._token_exp - 60:
            return self._token

        url = _TOKEN_URL.format(tenant_id=self.tenant_id)
        resp = self._session.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": _SCOPE,
            },
        )
        if resp.status_code != 200:
            raise AuthError(f"토큰 획득 실패 ({resp.status_code}): {resp.text}")

        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + data.get("expires_in", 3600)
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "x-ms-client-scope": _CLIENT_SCOPE,
        }

    def _params(self) -> dict:
        return {"api-version": _API_VERSION}

    def _url(self, *parts: str) -> str:
        path = "/".join(str(p) for p in parts)
        return f"{_API_BASE}/environments/{self.environment_id}/{path}"

    def _get(self, *path_parts, **query) -> dict:
        url = self._url(*path_parts)
        params = {**self._params(), **query}
        resp = self._session.get(url, headers=self._headers(), params=params)
        if resp.status_code != 200:
            raise PowerAutomateError(
                f"GET {url} 실패 ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def _post(self, *path_parts, json_body: dict = None) -> requests.Response:
        url = self._url(*path_parts)
        resp = self._session.post(
            url,
            headers=self._headers(),
            params=self._params(),
            json=json_body or {},
        )
        return resp

    # ── 유틸 ─────────────────────────────────────────────────
    @staticmethod
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(s[:26] + "Z" if "." in s else s, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _make_run_result(run: dict) -> RunResult:
        props = run.get("properties", {})
        return RunResult(
            run_id=run.get("name", ""),
            status=props.get("status", "Unknown"),
            start_time=PowerAutomateClient._parse_dt(props.get("startTime")),
            end_time=PowerAutomateClient._parse_dt(props.get("endTime")),
            error=props.get("error"),
            raw=run,
        )

    # ── 공개 API ─────────────────────────────────────────────

    def list_flows(self) -> list[FlowInfo]:
        """
        환경 내 전체 Flow 목록을 반환합니다.

        Returns
        -------
        list[FlowInfo]
        """
        data = self._get("flows")
        flows = data.get("value", [])
        return [
            FlowInfo(
                flow_id=f["name"],
                display_name=f.get("properties", {}).get("displayName", ""),
                state=f.get("properties", {}).get("state", ""),
            )
            for f in flows
        ]

    def get_trigger_name(self, flow_id: str) -> str:
        """Flow의 첫 번째 트리거 이름을 반환합니다."""
        data = self._get("flows", flow_id, "triggers")
        triggers = data.get("value", [])
        if not triggers:
            raise FlowRunError(f"Flow '{flow_id}'에 실행 가능한 트리거가 없습니다.")
        return triggers[0]["name"]

    def run_flow(
        self,
        flow_id: str,
        body: Optional[dict] = None,
    ) -> str:
        """
        Flow를 비동기로 실행하고 Run ID를 반환합니다.

        Parameters
        ----------
        flow_id : 실행할 Flow ID
        body    : 트리거에 전달할 JSON 데이터 (선택)

        Returns
        -------
        str : Run ID
        """
        trigger_name = self.get_trigger_name(flow_id)

        # 실행 전 최신 run 타임스탬프 저장 (새 run 구별용)
        before_runs = self._get("flows", flow_id, "runs", **{"$top": 1}).get(
            "value", []
        )
        before_start = (
            before_runs[0]["properties"]["startTime"] if before_runs else None
        )

        resp = self._post(
            "flows", flow_id, "triggers", trigger_name, "run", json_body=body or {}
        )
        if resp.status_code not in (200, 202):
            raise FlowRunError(f"Flow 실행 실패 ({resp.status_code}): {resp.text}")

        return self._wait_for_run_id(flow_id, before_start)

    def _wait_for_run_id(
        self,
        flow_id: str,
        before_start: Optional[str],
        timeout: int = 30,
    ) -> str:
        """실행 후 새 Run ID가 생길 때까지 최대 timeout초 대기"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(2)
            runs = self._get("flows", flow_id, "runs", **{"$top": 1}).get("value", [])
            if runs:
                latest = runs[0]
                if latest["properties"]["startTime"] != before_start:
                    return latest["name"]
        raise FlowRunError("Run ID를 가져오지 못했습니다 (타임아웃).")

    def get_run_status(self, flow_id: str, run_id: str) -> RunResult:
        """
        특정 Run의 현재 상태를 조회합니다.

        Parameters
        ----------
        flow_id : Flow ID
        run_id  : Run ID (run_flow() 반환값)

        Returns
        -------
        RunResult
        """
        run = self._get("flows", flow_id, "runs", run_id)
        return self._make_run_result(run)

    def wait_for_completion(
        self,
        flow_id: str,
        run_id: str,
        timeout: int = 300,
    ) -> RunResult:
        """
        Run이 완료 상태가 될 때까지 폴링하며 대기합니다.

        Parameters
        ----------
        flow_id  : Flow ID
        run_id   : Run ID
        timeout  : 최대 대기 시간 (초, 기본 300)

        Returns
        -------
        RunResult

        Raises
        ------
        PollTimeoutError : timeout 내에 완료되지 않은 경우
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.get_run_status(flow_id, run_id)
            if result.status in TERMINAL_STATUSES:
                return result
            time.sleep(self.poll_interval)

        raise PollTimeoutError(
            f"Flow run '{run_id}'이 {timeout}초 내에 완료되지 않았습니다."
        )

    def run_flow_sync(
        self,
        flow_id: str,
        body: Optional[dict] = None,
        timeout: int = 300,
    ) -> RunResult:
        """
        Flow를 실행하고 완료될 때까지 대기한 뒤 결과를 반환합니다.

        Parameters
        ----------
        flow_id : 실행할 Flow ID
        body    : 트리거에 전달할 JSON 데이터 (선택)
        timeout : 최대 대기 시간 (초, 기본 300)

        Returns
        -------
        RunResult

        Examples
        --------
        >>> result = client.run_flow_sync("abc-123", body={"name": "홍길동"})
        >>> if result.succeeded:
        ...     print(f"완료! 소요: {result.duration:.1f}초")
        ... else:
        ...     print(f"실패: {result.error}")
        """
        run_id = self.run_flow(flow_id, body=body)
        return self.wait_for_completion(flow_id, run_id, timeout=timeout)
