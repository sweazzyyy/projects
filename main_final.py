import tkinter as tk
from tkinter import scrolledtext, messagebox
import os
import socket
import shlex
import argparse
import yaml
import csv
from datetime import datetime
import getpass
import hashlib
import json

class VFS:
    """Виртуальная файловая система"""
    def __init__(self, physical_path=None):
        self.physical_path = physical_path
        self.filesystem = {}
        self.current_dir = "/"
        self.default_vfs = {
            "/": {
                "type": "directory",
                "content": {
                    "home": {"type": "directory", "content": {}},
                    "etc": {"type": "directory", "content": {
                        "motd": {"type": "file", "content": "Welcome to VFS Emulator!"}
                    }},
                    "bin": {"type": "directory", "content": {}},
                    "tmp": {"type": "directory", "content": {}}
                }
            }
        }

        if physical_path and os.path.exists(physical_path):
            self.load_from_directory(physical_path)
        else:
            self.filesystem = self.default_vfs.copy()

    def load_from_directory(self, path):
        """Загрузка VFS из директории"""
        try:
            self.filesystem = {"/": {"type": "directory", "content": {}}}
            self._build_vfs_from_dir(path, "/", self.filesystem["/"]["content"])
            return True
        except Exception as e:
            raise Exception(f"Ошибка загрузки VFS: {str(e)}")

    def _build_vfs_from_dir(self, real_path, vfs_path, vfs_node):
        """Рекурсивное построение VFS из реальной директории"""
        for item in os.listdir(real_path):
            real_item_path = os.path.join(real_path, item)
            if os.path.isdir(real_item_path):
                vfs_node[item] = {"type": "directory", "content": {}}
                self._build_vfs_from_dir(real_item_path, vfs_path + item + "/", vfs_node[item]["content"])
            else:
                try:
                    with open(real_item_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    vfs_node[item] = {"type": "file", "content": content}
                except:
                    vfs_node[item] = {"type": "file", "content": f"Binary file: {item}"}

    def get_vfs_info(self):
        """Информация о VFS"""
        name = os.path.basename(self.physical_path) if self.physical_path else "default_vfs"
        vfs_data = json.dumps(self.filesystem, sort_keys=True)
        sha256_hash = hashlib.sha256(vfs_data.encode()).hexdigest()
        return name, sha256_hash

    def list_directory(self, path=None):
        """Список содержимого директории"""
        if path is None:
            path = self.current_dir
        node = self._get_node(path)
        if node and node["type"] == "directory":
            return list(node["content"].keys())
        return []

    def change_directory(self, path):
        """Смена текущей директории"""
        if path == "..":
            if self.current_dir != "/":
                self.current_dir = os.path.dirname(self.current_dir.rstrip('/')) or "/"
            return True

        if path.startswith("/"):
            target_path = path
        else:
            target_path = os.path.join(self.current_dir, path).replace("\\", "/")

        node = self._get_node(target_path)
        if node and node["type"] == "directory":
            self.current_dir = target_path
            return True
        return False

    def _get_node(self, path):
        """Получение узла по пути"""
        if path == "/":
            return self.filesystem.get("/")
        parts = path.strip("/").split("/")
        node = self.filesystem.get("/")
        for part in parts:
            if node and node["type"] == "directory" and part in node["content"]:
                node = node["content"][part]
            else:
                return None
        return node

    def remove(self, path):
        """Удаление файла или директории"""
        target_path = os.path.join(self.current_dir, path).replace("\\", "/") if not path.startswith("/") else path
        parent_path = os.path.dirname(target_path)
        item_name = os.path.basename(target_path)
        parent_node = self._get_node(parent_path)
        if parent_node and parent_node["type"] == "directory" and item_name in parent_node["content"]:
            del parent_node["content"][item_name]
            return True
        return False

    def change_owner(self, path, owner):
        """Изменение владельца (эмуляция)"""
        node = self._get_node(path)
        if node:
            node["owner"] = owner
            return True
        return False

class ConfigManager:
    """Менеджер конфигурации"""
    def __init__(self):
        self.params = {}
        self.log_file = None

    def load_config(self):
        parser = argparse.ArgumentParser(description='Эмулятор командной строки')
        parser.add_argument('--vfs-path', help='Путь к физическому расположению VFS')
        parser.add_argument('--log-path', help='Путь к лог-файлу')
        parser.add_argument('--script-path', help='Путь к стартовому скрипту')
        parser.add_argument('--config-path', help='Путь к конфигурационному файлу')
        args = parser.parse_args()

        file_params = {}
        if args.config_path:
            try:
                with open(args.config_path, 'r', encoding='utf-8') as f:
                    file_params = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Ошибка чтения конфигурационного файла: {e}")

        self.params = {
            'vfs_path': args.vfs_path or file_params.get('vfs_path'),
            'log_path': args.log_path or file_params.get('log_path'),
            'script_path': args.script_path or file_params.get('script_path')
        }

        if self.params['log_path']:
            try:
                file_exists = os.path.exists(self.params['log_path'])
                self.log_file = open(self.params['log_path'], 'a', newline='', encoding='utf-8')
                if not file_exists:
                    writer = csv.writer(self.log_file)
                    writer.writerow(['timestamp', 'command', 'success', 'error_message', 'username'])
            except Exception as e:
                print(f"Ошибка открытия лог-файла: {e}")

        print("=== Параметры конфигурации ===")
        for k, v in self.params.items():
            print(f"{k}: {v}")
        print("===============================")
        return True

    def log_command(self, command, success=True, error_msg=""):
        if self.log_file:
            writer = csv.writer(self.log_file)
            writer.writerow([
                datetime.now().isoformat(),
                command,
                success,
                error_msg,
                getpass.getuser()
            ])
            self.log_file.flush()

    def execute_startup_script(self, command_handler):
        if not self.params['script_path']:
            return True
        try:
            with open(self.params['script_path'], 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    print(f"[Скрипт:{line_num}] > {line}")
                    success, _ = command_handler(line, from_script=True)
                    if not success:
                        print(f"Ошибка на строке {line_num}: остановка выполнения")
                        return False
            return True
        except Exception as e:
            print(f"Ошибка выполнения стартового скрипта: {e}")
            return False

    def close(self):
        if self.log_file:
            self.log_file.close()

class ShellEmulator:
    def __init__(self, root):
        self.root = root
        self.config = ConfigManager()
        if not self.config.load_config():
            messagebox.showerror("Ошибка", "Не удалось загрузить конфигурацию")
            return

        self.vfs = VFS(self.config.params['vfs_path'])
        self.command_history = []

        self.setup_gui()

        motd_node = self.vfs._get_node("/etc/motd")
        if motd_node and motd_node["type"] == "file":
            self.print_output(motd_node["content"] + "\n")

        if not self.config.execute_startup_script(self.execute_command):
            messagebox.showwarning("Предупреждение", "Стартовый скрипт завершился с ошибкой")

    def setup_gui(self):
        username = os.getlogin()
        hostname = socket.gethostname()
        self.root.title(f"Эмулятор - [{username}@{hostname}]")
        self.root.geometry("800x600")

        self.output_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled')
        self.output_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(frame, text=">").pack(side=tk.LEFT)
        self.command_entry = tk.Entry(frame)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.command_entry.bind("<Return>", lambda e: self.execute_command())
        tk.Button(frame, text="Выполнить", command=self.execute_command).pack(side=tk.RIGHT, padx=5)

        self.print_output("Добро пожаловать в эмулятор!\nВведите 'help' для списка команд.\n")

    def print_output(self, text):
        self.output_area.config(state='normal')
        self.output_area.insert(tk.END, text)
        self.output_area.see(tk.END)
        self.output_area.config(state='disabled')

    def parse_command(self, cmd_str):
        try:
            parts = shlex.split(cmd_str)
            return (parts[0], parts[1:]) if parts else ("", [])
        except ValueError:
            raise ValueError("Ошибка синтаксиса: незакрытые кавычки")

    def execute_command(self, cmd_str=None, from_script=False):
        if cmd_str is None:
            cmd_str = self.command_entry.get().strip()
            self.command_entry.delete(0, tk.END)
        if not cmd_str:
            return True, ""

        if not from_script:
            self.print_output(f"> {cmd_str}\n")

        try:
            cmd, args = self.parse_command(cmd_str)
            self.command_history.append(cmd_str)
            mapping = {
                "ls": self.cmd_ls,
                "cd": self.cmd_cd,
                "whoami": self.cmd_whoami,
                "who": self.cmd_who,
                "rm": self.cmd_rm,
                "chown": self.cmd_chown,
                "vfs-info": self.cmd_vfs_info,
                "help": self.cmd_help,
                "history": self.cmd_history,
                "exit": lambda a: (True, self.root.quit() or "")
            }
            func = mapping.get(cmd)
            result = func(args) if func else (False, f"Ошибка: неизвестная команда '{cmd}'")
            success, out = result
            if out:
                self.print_output(str(out) + "\n")
            self.config.log_command(cmd_str, success, "" if success else out)
            return success, out
        except Exception as e:
            msg = f"Ошибка: {e}"
            self.print_output(msg + "\n")
            self.config.log_command(cmd_str, False, msg)
            return False, msg

    def cmd_ls(self, args):
        path = args[0] if args else None
        items = self.vfs.list_directory(path)
        return True, "\n".join(items) if items else "Директория пуста"

    def cmd_cd(self, args):
        if not args:
            return False, "Использование: cd <путь>"
        ok = self.vfs.change_directory(args[0])
        return (True, f"Текущая директория: {self.vfs.current_dir}") if ok else (False, f"Директория не найдена: {args[0]}")

    def cmd_whoami(self, args): return True, os.getlogin()
    def cmd_who(self, args):
        users = ["admin", os.getlogin(), "guest"]
        host = socket.gethostname()
        return True, "\n".join(f"{u}@{host}" for u in users)

    def cmd_rm(self, args):
        if not args: return False, "Использование: rm <файл>"
        return (True, f"Удалено: {args[0]}") if self.vfs.remove(args[0]) else (False, f"Файл не найден: {args[0]}")

    def cmd_chown(self, args):
        if len(args) < 2:
            return False, "Использование: chown <владелец> <файл>"
        return (True, f"Владелец изменен: {args[1]} -> {args[0]}") if self.vfs.change_owner(args[1], args[0]) else (False, f"Файл не найден: {args[1]}")

    def cmd_vfs_info(self, args):
        name, h = self.vfs.get_vfs_info()
        return True, f"VFS: {name}\nSHA-256: {h}"

    def cmd_history(self, args):
        return True, "\n".join(self.command_history)

    def cmd_help(self, args):
        return True, """Доступные команды:
  ls [путь]            - список файлов
  cd <путь>            - смена директории
  whoami               - текущий пользователь
  who                  - список пользователей
  rm <файл>            - удалить файл
  chown <владелец> <файл> - смена владельца
  vfs-info             - информация о VFS
  history              - история команд
  help                 - справка
  exit                 - выход из эмулятора
"""

def main():
    root = tk.Tk()
    app = ShellEmulator(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.config.close(), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
