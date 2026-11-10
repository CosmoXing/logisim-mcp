"""Windows GUI 自动化（ctypes + PIL，无 PowerShell/COM 依赖）。

沙箱实测：PowerShell 的 Add-Type 加载 WinForms、COM WScript.Shell 会被拒，
ctypes 直调 user32 + PIL.ImageGrab 全部可用——本模块就是这条路径的封装。

典型流程（给 Logisim 截图 / 验证）：
    import gui
    gui.open_circ(r"D:/作业/2.3.circ")            # 后台启动 Logisim 载入电路
    h, title = gui.wait_window("Logisim", 25)     # 轮询等窗口出现
    gui.wheel(h, 6, ctrl=True, dy=-120)           # Ctrl+滚轮缩小看全图
    im = gui.shot("_out.png", h)                  # 截窗口区域
    gui.close(h)                                  # 发 WM_CLOSE

坑与要点（详见 references/pitfalls.md H12）：
  1. 截图像素坐标与 SetCursorPos 逻辑坐标在 DPI 缩放下不一致：
     click() 用 GetWindowRect（物理像素），滚轮/点击前先按实测比例校准。
  2. Ctrl+滚轮 = 画布缩放；Shift+滚轮 = 横向滚动。
  3. 后台任务里启动的 GUI 在任务结束时被回收——给用户看要提示重开。
  4. .circ 默认无文件关联，双击无效；必须命令行启动。
"""
import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
import time

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

u = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

WM_CLOSE = 0x0010
SW_RESTORE = 9
MOUSEEVENTF_WHEEL = 0x0800
VK_CTRL, VK_SHIFT, VK_ESC = 0x11, 0x10, 0x1B


def find(title_kw="Logisim"):
    """按标题关键字找**可见**顶层窗口，返回 [(hwnd, title), ...]。"""
    res = []

    def cb(h, l):
        if not u.IsWindowVisible(h):
            return True
        n = u.GetWindowTextLengthW(h)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            if title_kw in buf.value:
                res.append((h, buf.value))
        return True

    u.EnumWindows(CB(cb), 0)
    return res


def wait_window(title_kw="Logisim", timeout=25):
    """轮询等待窗口出现（启动 Logisim 后约 8~15 秒出窗）。"""
    f = []
    for _ in range(timeout):
        f = find(title_kw)
        if f:
            break
        time.sleep(1)
    if not f:
        raise RuntimeError(f"{timeout} 秒内没等到窗口 {title_kw!r}")
    h, title = f[0]
    u.ShowWindow(h, SW_RESTORE)
    u.SetForegroundWindow(h)
    time.sleep(1.5)
    return h, title


def rect(h):
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def foreground(h):
    u.ShowWindow(h, SW_RESTORE)
    u.SetForegroundWindow(h)
    time.sleep(0.6)


def click(h, x, y, wait=0.6):
    """单击。x/y 以窗口左上角为原点（逻辑坐标，DPI 缩放时需按实测比例换算）。"""
    l, t, _, _ = rect(h)
    foreground(h)
    u.SetCursorPos(l + x, t + y)
    time.sleep(0.15)
    u.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    u.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
    time.sleep(wait)


def wheel(h, n, ctrl=False, shift=False, dy=-120, wait=1.0):
    """滚轮 n 格。ctrl=True 缩放画布（Logisim Ctrl+滚轮），shift=True 横滚。"""
    l, t, _, _ = rect(h)
    foreground(h)
    u.SetCursorPos(l + (rect(h)[2] - l) // 2, t + (rect(h)[3] - t) // 2)
    time.sleep(0.3)
    if ctrl:
        u.keybd_event(VK_CTRL, 0, 0, 0)
    if shift:
        u.keybd_event(VK_SHIFT, 0, 0, 0)
    for _ in range(n):
        u.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, dy, 0)
        time.sleep(0.08)
    if ctrl:
        u.keybd_event(VK_CTRL, 0, 2, 0)
    if shift:
        u.keybd_event(VK_SHIFT, 0, 2, 0)
    time.sleep(wait)


def key(vk, ctrl=False, shift=False, wait=0.5):
    """发一个组合键（如 key(0x4B, ctrl=True) = Ctrl+K 启动时钟模拟）。"""
    if ctrl:
        u.keybd_event(VK_CTRL, 0, 0, 0)
    if shift:
        u.keybd_event(VK_SHIFT, 0, 0, 0)
    u.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(vk, 0, 2, 0)
    if shift:
        u.keybd_event(VK_SHIFT, 0, 2, 0)
    if ctrl:
        u.keybd_event(VK_CTRL, 0, 2, 0)
    time.sleep(wait)


def shot(name, h=None):
    """截窗口区域存 PNG。h 为空则抓第一个 Logisim 窗口；仍无则全屏。"""
    if ImageGrab is None:
        raise RuntimeError("需要 Pillow：pip install pillow")
    if h is None:
        f = find("Logisim") or find("")
        if not f:
            im = ImageGrab.grab(all_screens=True)
            im.save(name)
            print("shot(全屏)", name, im.size)
            return im
        h = f[0][0]
    l, t, r_, b = rect(h)
    im = ImageGrab.grab(bbox=(l, t, r_, b))
    im.save(name)
    print("shot", name, im.size)
    return im


def close(h=None):
    """发 WM_CLOSE（有未保存改动会弹确认框——外部改过文件时别点保存，见 pitfalls E3）。"""
    if h is None:
        f = find()
        if not f:
            return False
        h = f[0][0]
    u.PostMessageW(h, WM_CLOSE, 0, 0)
    time.sleep(2)
    return True


def open_circ(circ_path, jar=None, workdir=None):
    """后台启动 Logisim 载入电路。返回 Popen；窗口用 wait_window() 等。"""
    if jar is None:
        try:
            from sim import find_jar
            jar = find_jar()
        except ImportError:
            for base in ("D:/app", "C:/app"):
                if os.path.isdir(base):
                    hits = sorted(f for f in os.listdir(base)
                                  if f.lower().startswith("logisim") and f.endswith(".jar"))
                    if hits:
                        jar = os.path.join(base, hits[-1])
                        break
    if not jar:
        raise RuntimeError("找不到 logisim jar，设 LOGISIM_JAR 环境变量或传入 jar 参数")
    return subprocess.Popen(["java", "-jar", jar, str(circ_path)],
                            cwd=workdir or os.path.dirname(str(circ_path)),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    f = find("Logisim")
    if cmd == "shot":
        shot(sys.argv[2], f[0][0] if f else None)
    elif cmd == "click":
        click(f[0][0], int(sys.argv[2]), int(sys.argv[3]))
        shot(sys.argv[4] if len(sys.argv) > 4 else "_g.png", f[0][0])
    elif cmd == "list":
        for h, t in find(sys.argv[2] if len(sys.argv) > 2 else ""):
            print(h, t)
