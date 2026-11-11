"""与 Logisim 内的 Java 桥通信：启动/复用进程、NDJSON 请求、错误映射。

桥是可选通道：没有 JDK / jar / 编译失败时抛 BridgeError，由上层降级到 XML。
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_JAR = os.path.join(PLUGIN_ROOT, "runtime", "bridge", "logisim-bridge.jar")
BUILD_SCRIPT = os.path.join(PLUGIN_ROOT, "tools", "build_bridge.py")


class BridgeError(RuntimeError):
    def __init__(self, code, message, hint="", detail=None):
        super().__init__(message)
        self.code = code
        self.hint = hint
        self.detail = detail or {}

    def to_dict(self):
        return {"code": self.code, "message": str(self), "hint": self.hint,
                "detail": self.detail}


def _run_dir(path):
    digest = hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:12]
    bases = [
        os.environ.get("LOCALAPPDATA"),
        tempfile.gettempdir(),
        os.path.join(PLUGIN_ROOT, "runtime", "bridge"),
    ]
    last = None
    for base in bases:
        if not base:
            continue
        d = os.path.join(base, "logisim-mcp", "run", digest)
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except OSError as exc:
            last = exc
    raise BridgeError("E_RUN_DIR", "无法创建桥会话目录", str(last))


def _tail(path, n=20):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-n:])
    except OSError:
        return ""


class Session:
    def __init__(self, file, java, jar):
        self.file = os.path.abspath(file)
        self.java = java or "java"
        self.jar = jar
        self.rundir = _run_dir(self.file)
        self.portfile = os.path.join(self.rundir, "bridge.json")
        self.logfile = os.path.join(self.rundir, "agent.log")
        self.proc = None
        self.sock = None
        self.info = None
        self._fh = None
        self._next_id = 0
        self._log_handle = None

    # ---------------------------------------------------------------- 启动/复用
    def ensure(self, timeout=60):
        if self._ping_existing():
            return self
        self._launch()
        self._wait_ready(timeout)
        self._connect()
        return self

    def _ping_existing(self):
        try:
            with open(self.portfile, encoding="utf-8") as fh:
                info = json.load(fh)
        except (OSError, ValueError):
            return False
        if info.get("state") != "ready":
            return False
        pid = info.get("pid")
        if pid and not _pid_alive(pid):
            return False
        try:
            sock = socket.create_connection(("127.0.0.1", int(info["port"])), timeout=3)
            sock.settimeout(10)
            fh = sock.makefile("rwb")
            req = {"v": 1, "id": 0, "token": info.get("token"), "cmd": "ping", "params": {}}
            fh.write((json.dumps(req) + "\n").encode("utf-8"))
            fh.flush()
            line = fh.readline()
            if not line:
                return False
            resp = json.loads(line.decode("utf-8"))
            if not resp.get("ok"):
                return False
            self.info, self.sock, self._fh = info, sock, fh
            return True
        except (OSError, ValueError):
            return False

    def _launch(self):
        if not os.path.isfile(BRIDGE_JAR):
            raise BridgeError(
                "E_BRIDGE_NOT_BUILT",
                "Java 桥还没有编译",
                f"运行 python {BUILD_SCRIPT} 生成 {BRIDGE_JAR}",
            )
        if not self.jar or not os.path.isfile(self.jar):
            raise BridgeError("E_NO_JAR", "找不到 logisim-evolution jar")
        try:
            os.remove(self.portfile)
        except OSError:
            pass
        cp = BRIDGE_JAR + os.pathsep + self.jar
        cmd = [
            self.java,
            "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
            "-cp", cp, "logisim.bridge.BridgeMain",
            "--portfile=" + self.portfile, "--log=" + self.logfile, self.file,
        ]
        kwargs = {}
        self._log_handle = open(self.logfile, "ab")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=self._log_handle, stderr=self._log_handle,
            cwd=os.path.dirname(self.file) or None, **kwargs)

    def _wait_ready(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if self.proc is not None and self.proc.poll() is not None:
                raise BridgeError(
                    "E_BRIDGE_EXIT",
                    f"Java 桥启动后退出（code={self.proc.returncode}）",
                    _tail(self.logfile),
                )
            try:
                with open(self.portfile, encoding="utf-8") as fh:
                    info = json.load(fh)
                if info.get("state") == "ready":
                    self.info = info
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.25)
        raise BridgeError("E_BRIDGE_TIMEOUT", f"{timeout}s 内桥没有进入 ready 状态",
                          _tail(self.logfile))

    def _connect(self):
        if not self.info:
            raise BridgeError("E_BRIDGE_DOWN", "桥没有握手信息")
        end = time.time() + 15
        last = None
        while time.time() < end:
            try:
                sock = socket.create_connection(
                    ("127.0.0.1", int(self.info["port"])), timeout=5)
                sock.settimeout(90)
                self.sock = sock
                self._fh = sock.makefile("rwb")
                return
            except OSError as exc:
                last = exc
                time.sleep(0.3)
        raise BridgeError("E_BRIDGE_DOWN", f"连接桥端口失败: {last}")

    # ---------------------------------------------------------------- 请求
    def send(self, cmd, params=None, timeout=90):
        if self.sock is None or self._fh is None:
            self.ensure()
        self._next_id += 1
        req = {"v": 1, "id": self._next_id, "token": self.info.get("token"),
               "cmd": cmd, "params": params or {}}
        try:
            self.sock.settimeout(timeout)
            self._fh.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
            self._fh.flush()
            line = self._fh.readline()
        except OSError as exc:
            raise BridgeError("E_BRIDGE_DOWN", f"桥连接中断: {exc}") from exc
        if not line:
            raise BridgeError("E_BRIDGE_DOWN", "桥没有返回内容")
        resp = json.loads(line.decode("utf-8"))
        if not resp.get("ok"):
            err = resp.get("error") or {}
            raise BridgeError(err.get("code", "E_INTERNAL"), err.get("message", "桥返回错误"),
                              err.get("hint", ""), err.get("detail") or {})
        return resp.get("result")

    def close(self, timeout=10):
        try:
            if self._fh is not None:
                self.send("close", {}, timeout=5)
        except Exception:
            pass
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        if self.proc is not None:
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None

    def status(self):
        return self.send("status")


_SESSIONS = {}


def get_session(file, java, jar):
    key = os.path.abspath(file)
    sess = _SESSIONS.get(key)
    if sess is None:
        sess = Session(key, java, jar)
        _SESSIONS[key] = sess
    sess.ensure()
    return sess


def peek_session(file):
    """只复用已经存在的会话，不启动 Logisim。"""
    sess = _SESSIONS.get(os.path.abspath(file))
    if sess is not None and sess._ping_existing():
        return sess
    return None


def close_session(file):
    key = os.path.abspath(file)
    sess = _SESSIONS.pop(key, None)
    if sess is not None:
        sess.close()


def close_all():
    for sess in list(_SESSIONS.values()):
        try:
            sess.close()
        except Exception:
            pass
    _SESSIONS.clear()


def bridge_available():
    return os.path.isfile(BRIDGE_JAR)


def build_bridge(force=False, logisim_jar=None):
    cmd = [sys.executable, BUILD_SCRIPT]
    if force:
        cmd.append("--force")
    if logisim_jar:
        cmd.extend(["--logisim", logisim_jar])
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    if proc.returncode != 0:
        raise BridgeError("E_BUILD_FAILED", "编译 Java 桥失败", (out + "\n" + err).strip())
    return out.strip()


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
