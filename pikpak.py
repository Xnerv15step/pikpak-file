import json
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple

RCLONE_PATH = r"D:\rclone\rclone.exe"
RCLONE_REMOTE = "pikpak"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".rmvb", ".flv"}

class FlattenGUI:
    """PikPak 資料夾拍平工具（透過 rclone remote）。

    目標：把 remote 內指定資料夾下的影片檔，從子資料夾搬回根層（同資料夾下）。
    """

    def __init__(self, root):
        self.root = root
        self.root.title("PikPak 資料夾拍平工具")
        self.root.geometry("600x500")
        self.root.configure(bg="#1e1e1e")
        self.folders: List[str] = []
        self._running = False
        self._build_ui()

    def _build_ui(self):
        # 標題
        tk.Label(self.root, text="PikPak 資料夾拍平工具", bg="#1e1e1e", fg="white",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # 輸入區
        input_frame = tk.Frame(self.root, bg="#1e1e1e")
        input_frame.pack(fill=tk.X, padx=20)

        self.entry_var = tk.StringVar()
        tk.Entry(input_frame, textvariable=self.entry_var, bg="#2b2b2b", fg="white",
                 insertbackground="white", relief=tk.FLAT, font=("Arial", 11)
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        tk.Button(input_frame, text="➕ 新增", command=self.add_folder,
                  bg="#4a90d9", fg="white", relief=tk.FLAT, padx=12
                  ).pack(side=tk.LEFT)

        # 資料夾清單
        tk.Label(self.root, text="待處理資料夾：", bg="#1e1e1e", fg="#aaa",
                 font=("Arial", 10)).pack(anchor="w", padx=20, pady=(10, 2))

        list_frame = tk.Frame(self.root, bg="#2b2b2b")
        list_frame.pack(fill=tk.BOTH, padx=20, expand=False)

        self.listbox = tk.Listbox(list_frame, bg="#2b2b2b", fg="white", relief=tk.FLAT,
                                  selectbackground="#4a90d9", font=("Arial", 10), height=6)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(list_frame, command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)

        # 刪除按鈕
        tk.Button(self.root, text="🗑️ 移除選取", command=self.remove_folder,
                  bg="#555", fg="white", relief=tk.FLAT, padx=10
                  ).pack(anchor="e", padx=20, pady=4)

        # 執行按鈕
        self.run_btn = tk.Button(self.root, text="▶ 開始拍平", command=self.start_flatten,
                                 bg="#27ae60", fg="white", relief=tk.FLAT, padx=20, pady=8,
                                 font=("Arial", 11, "bold"))
        self.run_btn.pack(pady=6)

        # 進度顯示
        tk.Label(self.root, text="執行紀錄：", bg="#1e1e1e", fg="#aaa",
                 font=("Arial", 10)).pack(anchor="w", padx=20)

        log_frame = tk.Frame(self.root, bg="#2b2b2b")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(2, 16))

        self.log = tk.Text(log_frame, bg="#2b2b2b", fg="#ccc", relief=tk.FLAT,
                           font=("Consolas", 9), state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_sb = tk.Scrollbar(log_frame, command=self.log.yview)
        log_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=log_sb.set)

    def add_folder(self):
        name = self.entry_var.get().strip()
        if not name:
            return
        if name in self.folders:
            messagebox.showwarning("提示", "此資料夾已在清單中！")
            return
        self.folders.append(name)
        self.listbox.insert(tk.END, name)
        self.entry_var.set("")

    def remove_folder(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.folders.pop(idx)
        self.listbox.delete(idx)

    def log_msg(self, msg):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def start_flatten(self):
        if self._running:
            messagebox.showinfo("提示", "正在執行中，請稍候。")
            return
        if not self.folders:
            messagebox.showwarning("提示", "請先新增資料夾！")
            return
        self._running = True
        self.run_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.run_flatten, daemon=True).start()

    def run_flatten(self):
        folders = list(self.folders)
        try:
            for folder in folders:
                self.root.after(0, self.log_msg, f"\n{'='*40}")
                self.root.after(0, self.log_msg, f"📂 處理：{folder}")
                self._flatten(folder)
            self.root.after(0, self.log_msg, "\n🎉 全部完成！")
        finally:
            self._running = False
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))

    def _run(self, cmd):
        result = subprocess.run(
            [RCLONE_PATH] + cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout, result.stderr, result.returncode

    def _list_files(self, remote_path):
        stdout, _, rc = self._run(["lsjson", "-R", f"{RCLONE_REMOTE}:{remote_path}"])
        if rc != 0:
            return []
        try:
            return json.loads(stdout) if stdout.strip() else []
        except Exception:
            return []

    def _flatten(self, target):
        files = self._list_files(target)
        moved = 0

        for f in files:
            if f.get("IsDir"):
                continue
            name = f.get("Name") or ""
            if not name:
                continue
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in VIDEO_EXTENSIONS:
                continue
            path = f.get("Path") or ""
            if "/" not in path:
                continue

            src = f"{target}/{path}"
            dst = f"{target}/{name}"
            self.root.after(0, self.log_msg, f"  移動：{name}")
            _, err, rc = self._run(["moveto", f"{RCLONE_REMOTE}:{src}", f"{RCLONE_REMOTE}:{dst}"])
            err = (err or "").strip()
            if rc != 0 or err:
                self.root.after(0, self.log_msg, f"  ⚠️ 錯誤：{err or 'rclone 執行失敗'}")
            else:
                moved += 1

        self.root.after(0, self.log_msg, f"✅ 共移動 {moved} 個檔案")

        if moved > 0:
            self.root.after(0, self.log_msg, "🗑️ 清除空資料夾...")
            self._run(["rmdirs", f"{RCLONE_REMOTE}:{target}"])

if __name__ == "__main__":
    root = tk.Tk()
    app = FlattenGUI(root)
    root.mainloop()
