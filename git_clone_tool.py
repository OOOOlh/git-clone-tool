"""
Git Clone Tool - 带代理支持的 Git 克隆 GUI 工具
双击运行，支持配置代理端口和协议来克隆 GitHub 仓库
"""
import json
import os
import struct
import subprocess
import sys

# Windows 下禁止子进程弹出命令行窗口
if sys.platform == "win32":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    NO_WINDOW = 0
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
HISTORY_FILE = os.path.join(APP_DIR, "clone_history.json")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
ICON_FILE = os.path.join(APP_DIR, "clone_icon.ico")


# ══════════════════════════════════════════════════
# 图标生成
# ══════════════════════════════════════════════════
def generate_icon():
    """生成一个简洁的"克隆"图标（双页重叠），存为 .ico 文件"""
    if os.path.exists(ICON_FILE):
        return

    W, H = 32, 32

    def in_rounded_rect(x, y, l, t, r, b, radius=3):
        """判断点是否在圆角矩形内"""
        if not (l <= x <= r and t <= y <= b):
            return False
        # 四个角
        if x < l + radius and y < t + radius:       # 左上
            return (x - (l + radius)) ** 2 + (y - (t + radius)) ** 2 <= radius ** 2
        if x > r - radius and y < t + radius:       # 右上
            return (x - (r - radius)) ** 2 + (y - (t + radius)) ** 2 <= radius ** 2
        if x < l + radius and y > b - radius:       # 左下
            return (x - (l + radius)) ** 2 + (y - (b - radius)) ** 2 <= radius ** 2
        if x > r - radius and y > b - radius:       # 右下
            return (x - (r - radius)) ** 2 + (y - (b - radius)) ** 2 <= radius ** 2
        return True

    # 绘制像素 (BGRA)
    pixels = []
    for y in range(H):
        for x in range(W):
            back = in_rounded_rect(x, y, 1, 1, 21, 26, 4)      # 后页 - 蓝色
            front = in_rounded_rect(x, y, 9, 5, 29, 30, 4)     # 前页 - 白色
            if front:
                pixels.append((255, 255, 255, 255))
            elif back:
                pixels.append((66, 133, 244, 255))             # Google Blue
            else:
                pixels.append((0, 0, 0, 0))

    # 构建像素数据（BMP 自底向上）
    pixel_data = b""
    for y in range(H - 1, -1, -1):
        for x in range(W):
            r, g, b, a = pixels[y * W + x]
            pixel_data += struct.pack("BBBB", b, g, r, a)

    # BITMAPINFOHEADER (40 bytes)
    bih = struct.pack("<IiiHHIIiiII",
                      40,                   # biSize
                      W, H * 2,             # biWidth, biHeight（×2 含 AND mask）
                      1,                    # biPlanes
                      32,                   # biBitCount
                      0,                    # biCompression (BI_RGB)
                      len(pixel_data),     # biSizeImage
                      0, 0, 0, 0)           # unused

    image_data = bih + pixel_data

    # ICO 头部
    header = struct.pack("<HHH", 0, 1, 1)   # reserved, type=ICO, count=1
    data_offset = 6 + 16                     # header + 1 entry
    entry = struct.pack("<BBBBHHII",
                        W, H,                # width, height (0 = 256)
                        0,                   # color palette
                        0,                   # reserved
                        1,                   # color planes
                        32,                  # bits per pixel
                        len(image_data),    # image size
                        data_offset)

    try:
        with open(ICON_FILE, "wb") as f:
            f.write(header)
            f.write(entry)
            f.write(image_data)
    except OSError:
        pass


# ══════════════════════════════════════════════════
# 历史记录
# ══════════════════════════════════════════════════
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_history(records):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def add_record(url, port, protocol, directory, success, error="", log=""):
    records = load_history()
    records.insert(0, {
        "url": url,
        "port": port,
        "protocol": protocol,
        "directory": directory,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "success": success,
        "error": error,
        "log": log,
    })
    save_history(records)

    # 记住这次的端口和协议，供下次打开使用
    save_config(port, protocol)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(port, protocol):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"port": port, "protocol": protocol}, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════
# Git 操作
# ══════════════════════════════════════════════════
def git_clone(url, directory, proxy_config, on_line, on_progress,
              stop_event=None, proc_ref=None):
    """
    执行 git clone。
    on_line(text)    — 完整的一行（\n 结尾）
    on_progress(text) — 进度行（\r 结尾，会覆盖上一条进度）
    proxy_config 为 None 表示不走代理
    stop_event       — threading.Event，设置后中断克隆
    proc_ref         — 列表，proc_ref[0] 存放 Popen 对象供外部 kill
    """
    proxy_key = "http.https://github.com.proxy"

    try:
        if proxy_config:
            protocol, port = proxy_config
            proxy_value = f"{protocol}://127.0.0.1:{port}"
            on_line(f"[代理] 设置代理: {proxy_value}")
            subprocess.run(
                ["git", "config", "--global", proxy_key, proxy_value],
                capture_output=True, text=True, check=True,
                creationflags=NO_WINDOW,
            )

        on_line(f"[执行] git clone {url} {directory}")
        process = subprocess.Popen(
            ["git", "clone", "--progress", url, directory],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, creationflags=NO_WINDOW,
        )
        if proc_ref is not None:
            proc_ref[0] = process

        # 逐字符读取，区分 \r（进度刷新）和 \n（完整行）
        leftover = ""
        while True:
            # 检查是否被要求停止
            if stop_event and stop_event.is_set():
                # Windows: 杀进程树，确保子进程也被终止
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True, creationflags=NO_WINDOW,
                )
                process.wait()
                on_line("[已停止] 用户取消了克隆")
                # 清理残留的半成品目录
                if os.path.exists(directory):
                    import shutil
                    shutil.rmtree(directory, ignore_errors=True)
                    on_line("[已停止] 已清理残留目录")
                return False, "用户取消"

            chunk = process.stdout.read(4096)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            data = leftover + text
            leftover = ""

            while data:
                cr = data.find("\r")
                lf = data.find("\n")

                if cr == -1 and lf == -1:
                    leftover = data
                    break

                # 取最近的终止符
                pos_cr = cr if cr != -1 else float("inf")
                pos_lf = lf if lf != -1 else float("inf")
                pos = int(min(pos_cr, pos_lf))
                term = data[pos]
                line = data[:pos]
                data = data[pos + 1:]

                if term == "\r":
                    if line.strip():
                        on_progress(line)
                else:  # \n
                    if line.strip():
                        on_line(line)

        if leftover.strip():
            on_line(leftover)

        process.wait()

        if stop_event and stop_event.is_set():
            if os.path.exists(directory):
                import shutil
                shutil.rmtree(directory, ignore_errors=True)
            return False, "用户取消"

        if process.returncode == 0:
            on_line("[完成] 克隆成功 ✓")
            return True, ""
        else:
            on_line(f"[失败] git clone 返回码: {process.returncode}")
            return False, f"返回码: {process.returncode}"

    except subprocess.CalledProcessError as e:
        msg = f"Git 配置失败: {e.stderr.strip() if e.stderr else str(e)}"
        on_line(f"[错误] {msg}")
        return False, msg
    except FileNotFoundError:
        msg = "未找到 git 命令，请确认已安装 Git 并添加到 PATH"
        on_line(f"[错误] {msg}")
        return False, msg
    except Exception as e:
        on_line(f"[错误] {str(e)}")
        return False, str(e)
    finally:
        if proxy_config:
            subprocess.run(
                ["git", "config", "--global", "--unset", proxy_key],
                capture_output=True, text=True, creationflags=NO_WINDOW,
            )
            on_line("[代理] 代理配置已还原 ✓")


# ══════════════════════════════════════════════════
# GUI
# ══════════════════════════════════════════════════
class GitCloneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Clone Tool")
        self.root.geometry("960x600")
        self.root.minsize(800, 500)

        # 设置图标
        try:
            generate_icon()
            self.root.iconbitmap(ICON_FILE)
        except Exception:
            pass  # 图标加载失败不影响使用

        self.last_directory = ""
        self._last_was_progress = False  # 上一条日志是否是进度行
        self._stop_event = threading.Event()
        self._proc_ref = [None]  # 用列表包装，方便在 git_clone 里修改
        self.build_ui()
        self._load_last_config()
        self.load_history_to_listbox()

    def _load_last_config(self):
        """恢复上次使用的端口和协议"""
        cfg = load_config()
        if cfg.get("port"):
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, cfg["port"])
        if cfg.get("protocol") in ("http", "socks5"):
            self.proto_var.set(cfg["protocol"])

    # ── UI 构建 ──────────────────────────────
    def build_ui(self):
        # 可拖拽的分隔面板
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        right = ttk.Frame(paned, width=260)
        paned.add(right, weight=1)

        self.build_form(left)
        self.build_history(right)

    def build_form(self, parent):
        # 仓库地址
        ttk.Label(parent, text="仓库地址:").pack(anchor=tk.W, pady=(0, 2))
        self.url_entry = ttk.Entry(parent)
        self.url_entry.pack(fill=tk.X, pady=(0, 10))
        self.url_entry.insert(0, "https://github.com/")

        # 代理端口 + 协议
        proxy_frame = ttk.Frame(parent)
        proxy_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(proxy_frame, text="代理端口:").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(proxy_frame, width=8)
        self.port_entry.pack(side=tk.LEFT, padx=(5, 15))
        ttk.Label(proxy_frame, text="协议:").pack(side=tk.LEFT)
        self.proto_var = tk.StringVar(value="socks5")
        ttk.Radiobutton(proxy_frame, text="SOCKS5", variable=self.proto_var,
                        value="socks5").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Radiobutton(proxy_frame, text="HTTP", variable=self.proto_var,
                        value="http").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(parent, text="（留空 = 不走代理）", foreground="#888").pack(
            anchor=tk.W, pady=(0, 10))

        # 保存目录
        ttk.Label(parent, text="保存目录:").pack(anchor=tk.W, pady=(0, 2))
        dir_frame = ttk.Frame(parent)
        dir_frame.pack(fill=tk.X, pady=(0, 12))
        self.dir_entry = ttk.Entry(dir_frame)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.dir_entry.insert(0, APP_DIR)
        ttk.Button(dir_frame, text="浏览", width=6,
                   command=self.browse_dir).pack(side=tk.LEFT, padx=(5, 0))

        # 克隆按钮
        self.clone_btn = ttk.Button(parent, text="开始克隆",
                                    command=self.start_clone)
        self.clone_btn.pack(pady=(0, 10))

        # 日志区标题 + 停止按钮
        log_header = ttk.Frame(parent)
        log_header.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(log_header, text="输出日志:").pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(log_header, text="停止", width=6,
                                   command=self.stop_clone, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT)

        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED,
                                font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                insertbackground="white")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def build_history(self, parent):
        ttk.Label(parent, text="历史记录:").pack(anchor=tk.W, pady=(0, 2))

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        h_scroll = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        v_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.history_list = tk.Listbox(
            list_frame, font=("Microsoft YaHei", 9),
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
        )
        h_scroll.configure(command=self.history_list.xview)
        v_scroll.configure(command=self.history_list.yview)

        self.history_list.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.history_list.bind("<Button-1>", self._on_history_click)
        self.history_list.bind("<Button-3>", self._on_history_right_click)

        # 按钮放左下角
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="清空历史",
                   command=self.clear_history).pack(side=tk.LEFT)

    # ── 事件 ──────────────────────────────────
    def browse_dir(self):
        initial = self.dir_entry.get() or self.last_directory or APP_DIR
        chosen = filedialog.askdirectory(initialdir=initial)
        if chosen:
            self.last_directory = chosen
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, chosen)

    def start_clone(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入仓库地址")
            return

        parent_dir = self.dir_entry.get().strip()
        if not parent_dir:
            messagebox.showwarning("提示", "请选择保存目录")
            return

        repo_name = self._extract_repo_name(url)
        directory = os.path.join(parent_dir, repo_name)

        port = self.port_entry.get().strip()
        protocol = self.proto_var.get()
        proxy_config = (protocol, port) if port else None

        self.clone_btn.configure(state=tk.DISABLED, text="克隆中...")
        self.stop_btn.configure(state=tk.NORMAL)
        self._stop_event.clear()
        self.log_clear()
        self._last_was_progress = False
        self._log_buffer = []  # 开始收集日志

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_line(f"时间: {timestamp}")
        self.log_line(f"仓库: {url}")
        self.log_line(f"目录: {directory}")
        if proxy_config:
            self.log_line(f"代理: {protocol}://127.0.0.1:{port}")
        else:
            self.log_line("代理: 无（直连）")
        self.log_line("-" * 40)

        threading.Thread(target=self._clone_thread, args=(
            url, directory, proxy_config, port, protocol, parent_dir), daemon=True).start()

    @staticmethod
    def _extract_repo_name(url):
        name = url.rstrip("/")
        if "/" in name:
            name = name.rsplit("/", 1)[-1]
        else:
            name = name.rsplit(":", 1)[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name

    def _clone_thread(self, url, directory, proxy_config, port, protocol, parent_dir):
        success, error = git_clone(
            url, directory, proxy_config,
            on_line=self._log_capture,
            on_progress=self._log_capture_progress,
            stop_event=self._stop_event,
            proc_ref=self._proc_ref,
        )
        self._last_was_progress = False
        full_log = "\n".join(self._log_buffer)
        add_record(url, port, protocol, parent_dir, success, error, full_log)
        self.root.after(0, self._clone_done, success, error)

    def _clone_done(self, success, error=""):
        self.stop_btn.configure(state=tk.DISABLED)
        self.clone_btn.configure(state=tk.NORMAL, text="开始克隆")
        self.load_history_to_listbox()
        if success:
            messagebox.showinfo("完成", "克隆成功！")
        elif error == "用户取消":
            pass  # 用户主动停止，不弹错误框
        else:
            messagebox.showerror("失败", "克隆失败，请查看日志了解详情")

    def stop_clone(self):
        """用户主动停止克隆 — 强制终止进程树"""
        self._stop_event.set()
        self.stop_btn.configure(state=tk.DISABLED)
        self.clone_btn.configure(state=tk.NORMAL, text="开始克隆")
        proc = self._proc_ref[0]
        if proc is not None and proc.poll() is None:
            # Windows: 杀掉整个进程树（含 git-remote-https 等子进程）
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, creationflags=NO_WINDOW,
            )
            self.log_line("[已停止] 用户取消了克隆")

    # ── 日志 ──────────────────────────────────
    def log_clear(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def log_line(self, text):
        """追加一个普通行。如果上一条是进度行，直接替换掉它（模拟终端行为）"""
        def _do():
            self.log_text.configure(state=tk.NORMAL)
            if self._last_was_progress:
                # 进度行被最终结果替换（如 "Receiving objects: 99%" → "Receiving objects: 100%, done."）
                last_line_start = self.log_text.index("end-1c linestart")
                self.log_text.delete(last_line_start, "end-1c")
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self._last_was_progress = False
        self.root.after(0, _do)

    def log_progress(self, text):
        """进度行 — 覆盖上一条进度（同 \r 语义），无换行符，等待下次覆盖或替换"""
        def _do():
            self.log_text.configure(state=tk.NORMAL)
            if self._last_was_progress:
                # 替换上一次的进度行
                last_line_start = self.log_text.index("end-1c linestart")
                self.log_text.delete(last_line_start, "end-1c")
            else:
                # 接在最后一行后面
                self.log_text.insert(tk.END, "\n")
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self._last_was_progress = True
        self.root.after(0, _do)

    def _log_capture(self, text):
        """log_line + 写入缓冲区"""
        self._log_buffer.append(text)
        self.log_line(text)

    def _log_capture_progress(self, text):
        """进度行只显示，不存入缓冲区（避免刷屏）"""
        self.log_progress(text)

    # ── 历史记录 ──────────────────────────────
    def load_history_to_listbox(self):
        self.history_list.delete(0, tk.END)
        self.history_map = []
        for r in load_history():
            status = "✓" if r["success"] else "✗"
            port_str = f":{r['port']}" if r.get("port") else ""
            proto = r.get("protocol", "")
            proto_str = f" [{proto}{port_str}]" if port_str else ""
            label = f"{status} {r['url']}{proto_str}"
            self.history_list.insert(tk.END, label)
            self.history_map.append(r)

    def _on_history_click(self, event):
        """左键点击：只在点击到有效条目时才触发"""
        idx = self.history_list.nearest(event.y)
        if idx < 0 or idx >= len(self.history_map):
            return
        # 确保点击位置在条目的可见范围内
        bbox = self.history_list.bbox(idx)
        if bbox is None:
            return
        bx, by, bw, bh = bbox
        if not (by <= event.y <= by + bh):
            return
        self.history_list.selection_clear(0, tk.END)
        self.history_list.selection_set(idx)
        self._fill_form(self.history_map[idx])

    def _on_history_right_click(self, event):
        """右键菜单：先选中点击的条目，再弹出菜单"""
        idx = self.history_list.nearest(event.y)
        if idx < 0 or idx >= len(self.history_map):
            return
        self.history_list.selection_clear(0, tk.END)
        self.history_list.selection_set(idx)
        self.history_list.activate(idx)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="复制链接", command=lambda: self._copy_to_clipboard(idx, "url"))
        menu.add_command(label="复制全部信息", command=lambda: self._copy_to_clipboard(idx, "all"))
        menu.add_separator()
        menu.add_command(label="查看日志", command=lambda: self._show_history_log(idx))
        menu.add_separator()
        menu.add_command(label="删除此条", command=lambda: self._delete_history_item(idx))
        menu.post(event.x_root, event.y_root)

    def _copy_to_clipboard(self, idx, mode):
        r = self.history_map[idx]
        if mode == "url":
            text = r["url"]
        else:
            port_str = f":{r['port']}" if r.get("port") else ""
            proto = r.get("protocol", "")
            proxy_str = f" [{proto}{port_str}]" if port_str else " [直连]"
            text = f"{r['url']}{proxy_str}\n目录: {r['directory']}\n时间: {r['timestamp']}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _fill_form(self, r):
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, r["url"])
        self.port_entry.delete(0, tk.END)
        self.port_entry.insert(0, r.get("port", ""))
        if r.get("protocol"):
            self.proto_var.set(r["protocol"])
        self.dir_entry.delete(0, tk.END)
        self.dir_entry.insert(0, r.get("directory", ""))

    def clear_history(self):
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            save_history([])
            self.load_history_to_listbox()

    def _delete_history_item(self, idx):
        """删除单条历史记录"""
        records = load_history()
        if 0 <= idx < len(records):
            del records[idx]
            save_history(records)
            self.load_history_to_listbox()

    def _show_history_log(self, idx):
        """在日志区展示某条历史记录的完整日志"""
        r = self.history_map[idx]
        log_text = r.get("log", "")
        self.log_clear()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)


# ══════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = GitCloneApp(root)
    root.mainloop()
