import os
import atexit
import subprocess
import threading
from typing import Optional

_tunnel_lock = threading.Lock()
_tunnel_proc: Optional[subprocess.Popen] = None
_job_handle = None


def _ensure_windows_job_object():
    """Windows 콘솔 종료 시 자식 cloudflared 프로세스도 함께 종료되도록 Job Object를 생성합니다."""
    global _job_handle
    if os.name != "nt" or _job_handle is not None:
        return _job_handle
    try:
        import ctypes
        from ctypes import wintypes

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if job:
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = kernel32.SetInformationJobObject(
                job, 9, ctypes.byref(info), ctypes.sizeof(info)
            )
            if ok:
                _job_handle = job
            else:
                kernel32.CloseHandle(job)
    except Exception:
        pass
    return _job_handle


def _assign_to_job(proc: subprocess.Popen) -> None:
    if os.name != "nt":
        return
    job = _ensure_windows_job_object()
    if job and hasattr(proc, "_handle"):
        try:
            import ctypes
            ctypes.windll.kernel32.AssignProcessToJobObject(job, int(proc._handle))
        except Exception:
            pass


def _find_cloudflared(exec_dir: str) -> Optional[str]:
    cloudflared_path = os.path.join(exec_dir, "cloudflared.exe")
    if os.path.exists(cloudflared_path):
        return cloudflared_path
    parent_cloudflared = os.path.join(os.path.dirname(exec_dir), "cloudflared.exe")
    if os.path.exists(parent_cloudflared):
        return parent_cloudflared
    return None


def _stop_tunnel_unlocked() -> None:
    global _tunnel_proc
    if _tunnel_proc is not None:
        try:
            if _tunnel_proc.poll() is None:
                _tunnel_proc.terminate()
                try:
                    _tunnel_proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    _tunnel_proc.kill()
        except Exception:
            pass
        _tunnel_proc = None


def stop_tunnel() -> None:
    with _tunnel_lock:
        _stop_tunnel_unlocked()


def start_or_restart_tunnel(exec_dir: str, token: str = "") -> bool:
    global _tunnel_proc
    with _tunnel_lock:
        _stop_tunnel_unlocked()
        cloudflared_path = _find_cloudflared(exec_dir)
        if not cloudflared_path:
            return False

        clean_token = (token or "").strip()
        if clean_token:
            print("🚀 Cloudflare [고정 터널 (Named Tunnel)]을 자동으로 시작합니다...")
            cmd = [cloudflared_path, "tunnel", "run", "--token", clean_token]
        else:
            print("🚀 Cloudflare [임시 터널 (Quick Tunnel)]을 자동으로 시작합니다...")
            cmd = [
                cloudflared_path,
                "tunnel",
                "--url",
                "http://127.0.0.1:8000",
                "--metrics",
                "127.0.0.1:20241",
            ]

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            _assign_to_job(proc)
            _tunnel_proc = proc
            return True
        except Exception as e:
            print(f"터널 자동 실행 실패: {e}")
            return False


def restart_if_running(exec_dir: str, token: str = "") -> bool:
    with _tunnel_lock:
        is_running = _tunnel_proc is not None and _tunnel_proc.poll() is None
    if not is_running:
        return False
    return start_or_restart_tunnel(exec_dir, token)


atexit.register(stop_tunnel)
