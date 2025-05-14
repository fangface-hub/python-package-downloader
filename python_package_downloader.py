"""Pythonパッケージを指定された条件でダウンロードするGUIアプリケーション."""

# -*- coding: utf-8 -*-
# このスクリプトは、指定されたOS、Pythonバージョン、
# ABIに基づいてPythonパッケージをダウンロードする
# GUIアプリケーションです。
# ユーザーは、OS、Pythonバージョン、パッケージリスト
# ファイルを指定し、ダウンロードを開始できます。

# 必要なライブラリをインポート
import os
from tkinter import (
    Tk,
    messagebox,
    filedialog,
    BooleanVar,
    StringVar,
    Label,
    Listbox,
    END,
)
from tkinter.ttk import Frame, Entry, Button, Radiobutton, Checkbutton
import urllib.parse  # URLエンコード用
import shutil
import json

try:
    from cryptography.fernet import Fernet

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

from loggingex import generate_logger, set_init_logfile

from python_package_utility import (
    OS_TO_PLATFORMS,
    PYPISIMPLE_AVAILABLE,
    PYTHON_VERSION_TO_ABI,
    DownloadConfig,
    start_download,
)

set_init_logfile()
logger = generate_logger(name=__name__, debug=__debug__, filepath=__file__)


class CustomEntry(Entry):
    """カスタムエントリウィジェット.
    StringVarを使用して、値の取得と設定を行う.

    Parameters
    ----------
    Entry : _type_
        tkinterのEntryウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        self.var = StringVar()
        super().__init__(master, textvariable=self.var, **kwargs)

    @property
    def value(self) -> str:
        """値を取得（getter）."""
        return self.var.get()

    @value.setter
    def value(self, new_value) -> None:
        """値を設定（setter）."""
        self.var.set(new_value)


class CustomCheckbutton(Checkbutton):
    """カスタムチェックボックスウィジェット.
    BooleanVarを使用して、値の取得と設定を行う.

    Parameters
    ----------
    Checkbutton : _type_
        tkinterのCheckbuttonウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        self.var = BooleanVar()
        super().__init__(master, variable=self.var, **kwargs)

    @property
    def value(self) -> bool:
        """値を取得（getter）."""
        return self.var.get()

    @value.setter
    def value(self, new_value) -> None:
        """値を設定（setter）."""
        self.var.set(new_value)


class CustomListbox(Listbox):
    """カスタムリストボックスウィジェット.
    StringVarを使用して、値の取得と設定を行う.

    Parameters
    ----------
    Listbox : _type_
        tkinterのListboxウィジェットを継承.
    """

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

    @property
    def curselection_list(self) -> list[str]:
        """選択中のリスト."""
        return [self.get(i) for i in self.curselection()]

    @curselection_list.setter
    def curselection_list(self, new_value) -> None:
        """選択中のリストを設定."""
        self.selection_clear(0, END)
        for item in new_value:
            index = self.get(0, END).index(item)
            self.selection_set(index)


def generate_key() -> bytes:
    """暗号化キーを生成し、ファイルに保存する."""
    key_file = "key.key"
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    else:
        with open(key_file, "rb") as f:
            key = f.read()
    return key


def encrypt_password(password: str, key: bytes) -> str:
    """パスワードを暗号化する."""
    fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str, key: bytes) -> str:
    """暗号化されたパスワードを復号化する."""
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_password.encode()).decode()


def save_settings(settings: dict) -> None:
    """設定をJSONファイルに保存する."""
    settings_copy = settings.copy()
    # 暗号化キーが有効な場合
    if CRYPTOGRAPHY_AVAILABLE:
        key = generate_key()
    else:
        key = None
    if CRYPTOGRAPHY_AVAILABLE:
        if settings_copy.get("proxy_password", "") != "":
            settings_copy["proxy_password"] = encrypt_password(
                settings_copy["proxy_password"], key
            )
        else:
            # proxy_passwordが設定されていない場合は削除
            del settings_copy["proxy_password"]
    else:
        # cryptographyがインストールされていない場合は、パスワードを削除する
        del settings_copy["proxy_password"]
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(settings_copy, f, ensure_ascii=False, indent=4)


def load_settings() -> dict:
    """JSONファイルから設定を読み込む."""
    if not os.path.exists("settings.json"):
        return {}
    # 暗号化キーが有効な場合
    if CRYPTOGRAPHY_AVAILABLE:
        key = generate_key()
    else:
        key = None

    with open("settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
    if "proxy_password" in settings:
        settings["proxy_password"] = decrypt_password(
            settings["proxy_password"], key
        )
    return settings


class MainWindow(Tk):
    """pythonパッケージダウンローダーのメインウィンドウ.

    Parameters
    ----------
    tk : tkinter.Tk
        親クラス.Tkのインスタンスを継承.
    """

    def __init__(self) -> None:
        """初期化."""
        super().__init__()
        self.title("pythonパッケージダウンローダー")
        self.setup_ui()

        settings = load_settings()
        if settings:
            self.os_options_listbox.curselection_list = settings.get(
                "os_list", []
            )
            self.python_version_listbox.curselection_list = settings.get(
                "python_versions", []
            )
            self.package_list_entry.value = settings.get(
                "package_list_file", ""
            )
            self.dest_folder_entry.value = settings.get("dest_folder", "")
            self.pip_path_entry.value = settings.get("pip_path", "")
            self.proxy_user_entry.value = settings.get("proxy_user", "")
            self.proxy_password_entry.value = settings.get("proxy_password", "")
            self.proxy_server_entry.value = settings.get("proxy_server", "")
            self.proxy_port_entry.value = settings.get("proxy_port", "")
            self.include_source_check.value = settings.get(
                "include_source", False
            )
            self.include_deps_check.value = settings.get("incude_deps", False)
            self.use_proxy_checkbox.value = settings.get("use_proxy", False)
            self.toggle_proxy_widgets()

    def setup_ui(self) -> None:
        """GUIの各要素を設定する."""
        # pip使用選択
        pip_use_frame = Frame(self)
        pip_use_frame.pack(side="top", fill="x", padx=2, pady=2)
        pip_use_lbl = Label(pip_use_frame, text="ダウンロード方法:")
        pip_use_lbl.pack(side="left", padx=10, pady=5)
        self.download_method_var = StringVar(value="pip")
        pip_radio = Radiobutton(
            pip_use_frame,
            text="pipを使う",
            variable=self.download_method_var,
            value="pip",
        )
        pip_radio.pack(side="left", padx=10, pady=5)
        no_pip_radio = Radiobutton(
            pip_use_frame,
            text="pipを使わない",
            variable=self.download_method_var,
            value="no_pip",
        )
        no_pip_radio.pack(side="left", padx=10, pady=5)
        # OS選択
        os_frame = Frame(self)
        os_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(os_frame, text="OSを選択:").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.os_options = list(OS_TO_PLATFORMS.keys())
        self.os_options_listbox = CustomListbox(
            os_frame,
            selectmode="multiple",
            exportselection=False,
            height=len(self.os_options),
        )
        self.os_options_listbox.pack(
            side="left", padx=10, pady=5, fill="both", expand=True
        )
        for os_option in self.os_options:
            self.os_options_listbox.insert(END, os_option)
        # Pythonバージョン選択（複数選択可能）
        python_version_frame = Frame(self)
        python_version_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(
            python_version_frame, text="Pythonバージョン（複数選択可）:"
        ).pack(side="left", padx=10, pady=5, anchor="w")
        self.python_versions = list(PYTHON_VERSION_TO_ABI.keys())
        self.python_version_listbox = CustomListbox(
            python_version_frame,
            selectmode="multiple",
            exportselection=False,
            height=len(self.python_versions),
        )
        for version in self.python_versions:
            self.python_version_listbox.insert(END, version)
        self.python_version_listbox.pack(
            side="left", padx=10, pady=5, fill="both", expand=True
        )

        # パッケージリストファイル選択
        package_list_frame = Frame(self)
        package_list_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(package_list_frame, text="パッケージリスト:").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.package_list_entry = CustomEntry(
            package_list_frame,
            state="readonly",
        )
        self.package_list_entry.pack(
            side="left", padx=10, pady=5, fill="both", expand=True
        )
        # 初期値をスクリプトの格納ディレクトリの package_list.txt に設定
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_package_list_path = os.path.join(script_dir, "package_list.txt")
        self.package_list_entry.value = default_package_list_path
        package_list_button = Button(
            package_list_frame, text="選択", command=self.select_package_list
        )
        package_list_button.pack(
            side="left", padx=10, pady=5, fill="x", expand=False
        )
        # ダウンロード先フォルダ選択
        dest_folder_frame = Frame(self)
        dest_folder_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(dest_folder_frame, text="ダウンロード先フォルダ:").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.dest_folder_entry = CustomEntry(
            dest_folder_frame,
            state="readonly",
        )
        self.dest_folder_entry.pack(
            side="left", padx=10, pady=5, fill="both", expand=True
        )
        # 初期値をスクリプトの格納ディレクトリの downloads に設定
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_dest_folder = os.path.join(script_dir, "downloads")
        self.dest_folder_entry.value = default_dest_folder
        dest_folder_button = Button(
            dest_folder_frame, text="選択", command=self.select_dest_folder
        )
        dest_folder_button.pack(
            side="left", padx=10, pady=5, fill="x", expand=False
        )

        # pipパス指定
        pip_path_frame = Frame(self)
        pip_path_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(pip_path_frame, text="pipのパス:").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.pip_path_entry = CustomEntry(pip_path_frame)
        self.pip_path_entry.pack(
            side="left", padx=10, pady=5, fill="both", expand=True
        )
        self.pip_path_entry.value = self.get_default_pip_path()
        pip_path_button = Button(
            pip_path_frame, text="選択", command=self.select_pip_path
        )
        pip_path_button.pack(
            side="left", padx=10, pady=5, fill="x", expand=False
        )

        # プロキシ設定
        proxy_setting_frame = Frame(self)
        proxy_setting_frame.pack(side="top", fill="x", padx=2, pady=2)
        use_proxy_frame = Frame(proxy_setting_frame)
        use_proxy_frame.pack(side="top", fill="x", padx=2, pady=0)
        self.use_proxy_checkbox = CustomCheckbutton(
            use_proxy_frame,
            text="プロキシを使用する",
            command=self.toggle_proxy_widgets,
        )
        self.use_proxy_checkbox.pack(side="left", padx=10, pady=2, anchor="w")
        self.use_proxy_checkbox.value = False
        proxy_user_frame = Frame(proxy_setting_frame)
        proxy_user_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_user_frame, text="プロキシユーザー名:").pack(
            side="left", padx=10, pady=2, anchor="w"
        )
        self.proxy_user_entry = CustomEntry(
            proxy_user_frame,
            state="disabled",
        )
        self.proxy_user_entry.pack(
            side="left", padx=10, pady=2, fill="both", expand=True
        )
        proxy_password_frame = Frame(proxy_setting_frame)
        proxy_password_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_password_frame, text="プロキシパスワード:").pack(
            side="left", padx=10, pady=2, anchor="w"
        )
        self.proxy_password_entry = CustomEntry(
            proxy_password_frame,
            state="disabled",
            show="*",
        )
        self.proxy_password_entry.pack(
            side="left", padx=10, pady=2, fill="both", expand=True
        )
        proxy_server_frame = Frame(proxy_setting_frame)
        proxy_server_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_server_frame, text="プロキシサーバー:").pack(
            side="left", padx=10, pady=2, anchor="w"
        )
        self.proxy_server_entry = CustomEntry(
            proxy_server_frame,
            state="disabled",
        )
        self.proxy_server_entry.pack(
            side="left", padx=10, pady=2, fill="both", expand=True
        )
        proxy_port_frame = Frame(proxy_setting_frame)
        proxy_port_frame.pack(side="top", fill="x", padx=2, pady=0)
        Label(proxy_port_frame, text="プロキシポート:").pack(
            side="left", padx=10, pady=2, anchor="w"
        )
        self.proxy_port_entry = CustomEntry(
            proxy_port_frame, state="disabled", validate="key"
        )
        self.proxy_port_entry.pack(
            side="left", padx=10, pady=2, fill="both", expand=True
        )
        validatecommand = (
            proxy_port_frame.register(self.validate_port),
            "%P",
        )
        self.proxy_port_entry.configure(validatecommand=validatecommand)

        # ソース形式を含めるチェックボックス
        source_format_frame = Frame(self)
        source_format_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(source_format_frame, text="ソース形式を含める:").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.include_source_check = CustomCheckbutton(source_format_frame)
        self.include_source_check.pack(side="left", padx=10, pady=5, anchor="w")
        self.include_source_check.value = False
        include_deps_frame = Frame(self)
        include_deps_frame.pack(side="top", fill="x", padx=2, pady=2)
        Label(include_deps_frame, text="依存パッケージをダウンロードする").pack(
            side="left", padx=10, pady=5, anchor="w"
        )
        self.include_deps_check = CustomCheckbutton(include_deps_frame)
        self.include_deps_check.pack(side="left", padx=10, pady=5, anchor="w")
        self.include_deps_check.value = False
        # ダウンロード開始ボタン
        button_frame = Frame(self)
        button_frame.pack(side="top", fill="x", padx=2, pady=2)
        download_button = Button(
            button_frame, text="ダウンロード開始", command=self.on_download
        )
        download_button.pack(
            side="left", padx=10, pady=5, fill="x", expand=True
        )

        # 設定を保存ボタン
        save_button = Button(
            button_frame, text="設定を保存", command=self.on_save_settings
        )
        save_button.pack(side="left", padx=10, pady=5, fill="x", expand=True)

    def toggle_proxy_widgets(self) -> None:
        """プロキシ関連のウィジェットを有効化または無効化する."""
        state = "normal" if self.use_proxy_checkbox.value else "disabled"
        self.proxy_user_entry.config(state=state)
        self.proxy_password_entry.config(state=state)
        self.proxy_server_entry.config(state=state)
        self.proxy_port_entry.config(state=state)

    def validate_port(self, value: str) -> bool:
        """ポート番号が数字のみで構成されているかを検証する.

        Parameters
        ----------
        value : str
            入力された値.

        Returns
        -------
        bool
            数字のみの場合はTrue、それ以外はFalse.
        """
        return value.isdigit() or value == ""

    def select_package_list(self) -> None:
        """パッケージリストファイルを選択する."""
        file_path = filedialog.askopenfilename(
            title="パッケージリストを選択",
            initialfile=self.package_list_entry.get(),
            filetypes=[
                ("テキストファイル", "*.txt"),
                ("すべてのファイル", "*.*"),
            ],
        )
        if file_path:
            self.package_list_entry.value = file_path

    def select_dest_folder(self) -> None:
        """ダウンロード先フォルダを選択する."""
        folder_path = filedialog.askdirectory(
            title="ダウンロード先フォルダを選択",
            initialdir=self.dest_folder_entry.get(),
        )
        if folder_path:
            self.dest_folder_entry.value = folder_path

    def select_pip_path(self) -> None:
        """pipのパスを選択する."""
        file_path = filedialog.askopenfilename(
            title="pipのパスを選択",
            initialfile=self.pip_path_entry.get(),
            filetypes=[("実行ファイル", "*.exe"), ("すべてのファイル", "*.*")],
        )
        if file_path:
            self.pip_path_entry.value = file_path

    def on_download(self) -> None:
        """ダウンロード処理を開始する."""
        download_method = self.download_method_var.get()
        use_pip = download_method == "pip" or not PYPISIMPLE_AVAILABLE
        pip_path = self.pip_path_entry.get() if use_pip else ""
        os_list = self.os_options_listbox.curselection_list
        python_versions = self.python_version_listbox.curselection_list
        package_list_file = self.package_list_entry.get()
        dest_folder = self.dest_folder_entry.get()
        include_source = self.include_source_check.value
        include_deps = self.include_deps_check.value

        # プロキシ情報を組み立て
        proxy = None
        if self.use_proxy_checkbox.value:
            proxy_user = self.proxy_user_var.get()
            proxy_password = self.proxy_password_var.get()
            proxy_server = self.proxy_server_var.get()
            proxy_port = self.proxy_port_var.get()

            if proxy_server and proxy_port:
                proxy = "http://"
                if proxy_user and proxy_password:
                    # パスワードをURLエンコード
                    encoded_password = urllib.parse.quote(proxy_password)
                    proxy += (f"{proxy_user}:{encoded_password}@",)
                proxy += f"{proxy_server}:{proxy_port}"

        # 環境変数にプロキシを設定
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy

        if len(os_list) < 1:
            messagebox.showerror("エラー", "OSを1つ以上選択してください。")
            return

        if len(python_versions) < 1:
            messagebox.showerror(
                "エラー", "Pythonバージョンを1つ以上選択してください。"
            )
            return

        if not package_list_file:
            messagebox.showerror(
                "エラー", "パッケージリストファイルを選択してください。"
            )
            return

        if not dest_folder:
            messagebox.showerror(
                "エラー", "ダウンロード先フォルダを選択してください。"
            )
            return

        # 各バージョンに対してダウンロードを実行
        config = DownloadConfig(
            os_list=os_list,
            python_versions=python_versions,
            package_list_file=package_list_file,
            dest_folder=dest_folder,
            include_source=include_source,
            include_deps=include_deps,
            proxy=proxy,
            use_pip=use_pip,
            pip_path=pip_path,
        )

        start_download(config)

        # すべてのダウンロードが完了した後にダイアログを表示
        messagebox.showinfo(
            "完了", "すべてのパッケージのダウンロードが完了しました。"
        )

    def get_default_pip_path(self) -> str:
        """実行環境のpipまたはpip3のパスを検索する.

        Returns
        -------
        str
            実行環境のpipまたはpip3のパス。見つからない場合は空文字列.
        """
        # pipを検索
        pip_path = shutil.which("pip")
        if pip_path:
            return pip_path

        # pip3を検索
        pip3_path = shutil.which("pip3")
        if pip3_path:
            return pip3_path

        # 見つからない場合は空文字列を返す
        return ""

    def on_save_settings(self) -> None:
        """現在の設定を保存する."""
        settings = {
            "os_list": self.os_options_listbox.curselection_list,
            "python_versions": self.python_version_listbox.curselection_list,
            "package_list_file": self.package_list_entry.value,
            "dest_folder": self.dest_folder_entry.value,
            "pip_path": self.pip_path_entry.value,
            "proxy_user": self.proxy_user_entry.value,
            "proxy_password": self.proxy_password_entry.value,
            "proxy_server": self.proxy_server_entry.value,
            "proxy_port": self.proxy_port_entry.value,
            "include_source": self.include_source_check.value,
            "include_deps": self.include_deps_check.value,
            "use_proxy": self.use_proxy_checkbox.value,
        }
        save_settings(settings)
        messagebox.showinfo("保存完了", "設定が保存されました。")


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
