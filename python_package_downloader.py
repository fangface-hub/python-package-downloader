"""Pythonパッケージを指定された条件でダウンロードするGUIアプリケーション."""

# -*- coding: utf-8 -*-
# このスクリプトは、指定されたOS、Pythonバージョン、
# ABIに基づいてPythonパッケージをダウンロードする
# GUIアプリケーションです。
# ユーザーは、OS、Pythonバージョン、パッケージリスト
# ファイルを指定し、ダウンロードを開始できます。

# 必要なライブラリをインポート
import os
import subprocess
from tkinter import (
    ttk,
    Tk,
    messagebox,
    filedialog,
    BooleanVar,
    StringVar,
    Label,
    Listbox,
    END,
)
from tkinter.ttk import Entry, Combobox, Button, Radiobutton
from dataclasses import dataclass
import re
import urllib.parse  # URLエンコード用
import shutil
import logging

try:
    from pypi_simple import PyPISimple
    import requests

    PYPISIMPLE_AVAILABLE = True
except ImportError:
    PYPISIMPLE_AVAILABLE = False

# ログファイルのパス
LOG_FILE = "python_package_downloader.log"

# 起動時にログファイルをクリア
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8"):
        pass  # ファイルを空にする

# ログの設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルをINFOに設定
    format="%(asctime)s - %(levelname)s - %(message)s",  # ログのフォーマット
    handlers=[
        logging.FileHandler(LOG_FILE),  # ログをファイルに出力
        logging.StreamHandler(),  # コンソールにも出力
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class DownloadConfig:
    """
    パッケージダウンロードの設定を保持するデータクラス.

    Attributes
    ----------
    os_name : str
        対象のOS名.
    python_version : str
        対象のPythonバージョン.
    package_list_file : str
        パッケージリストファイルのパス.
    dest_folder : str
        ダウンロード先フォルダのパス.
    include_source : bool, optional
        ソース形式を含めるかどうか (デフォルトはFalse).
    proxy : str, optional
        プロキシ設定 (例: "http://user:password@proxyserver:port").
    use_pip : bool, optional
        pipを使用するかどうか (デフォルトはTrue).
    pip_path : str, optional
        pipのパス (use_pipがTrueの場合に使用).
    """

    os_name: str
    python_version: str
    package_list_file: str
    dest_folder: str
    include_source: bool = False
    proxy: str = (
        None  # プロキシ設定（例: "http://user:password@proxyserver:port"）
    )
    use_pip: bool = True  # pipを使用するかどうか
    pip_path: str = ""  # pipのパス（use_pipがTrueの場合に使用）


@dataclass
class PackageInfo:
    """
    パッケージ情報を保持するデータクラス.

    Attributes
    ----------
    name : str
        パッケージ名.
    version : str
        バージョン.
    python_version : str
        Pythonバージョン.
    abi : str
        ABI.
    platform : str
        プラットフォーム.
    """

    name: str
    version: str
    python_version: str
    abi: str
    platform: str


class LabeledEntry:
    """
    ラベル付きのエントリウィジェットを作成するクラス.

    Parameters
    ----------
    parent : tk.Widget
        親ウィジェット.
    label_text : str
        ラベルのテキスト.
    row : int
        配置する行番号.
    column : int
        配置する列番号.
    entry_state : str, optional
        エントリの状態（デフォルトは "normal"）.
    show : str, optional
        エントリの表示形式（例: "*"）。デフォルトは None.
    padx : int, optional
        x方向のパディング（デフォルトは10）.
    pady : int, optional
        y方向のパディング（デフォルトは5）.
    """

    def __init__(
        self,
        parent,
        label_text,
        row,
        column,
        entry_state="normal",
        show=None,
        padx=10,
        pady=5,
    ):
        """初期化メソッド."""
        self.var = StringVar()
        self.label = Label(parent, text=label_text)
        self.label.grid(
            row=row, column=column, padx=padx, pady=pady, sticky="w"
        )

        self.entry = Entry(
            parent, textvariable=self.var, state=entry_state, show=show
        )
        self.entry.grid(row=row, column=column + 1, padx=padx, pady=pady)

    def get(self) -> str:
        """エントリの値を取得する.

        Returns
        -------
        str:
            エントリの値.
        """
        return self.var.get()

    def set(self, value: str) -> None:
        """エントリの値を設定する.

        Parameters
        ----------
        value : str
            設定する値.
        """
        self.var.set(value)

    def configure_state(self, state: str) -> None:
        """エントリの状態を設定する.

        Parameters
        ----------
        state : str
            エントリの状態,（例: "normal", "readonly", "disabled"）.
        """
        self.entry.config(state=state)

    def configure_show(self, show: str) -> None:
        """エントリの表示形式を設定する.

        Parameters
        ----------
        show : str
            エントリの状態
        """
        self.entry.config(show=show)


def get_package_info_from_filename(filename: str) -> PackageInfo:
    """ファイル名から情報を取得する.

    Parameters
    ----------
    filename : str
        ファイル名.

    Returns
    -------
    PackageInfo
        パッケージ情報.
    """
    package_name = "unknown"
    package_version = "unknown"
    python_version = "unknown"
    abi = "unknown"
    platform = "unknown"
    match = re.search(r"([^-]+)-([^-]+)-([^-]+)-([^-]+)-([^-]+)\.whl", filename)
    if match:
        package_name = match.group(1)
        package_version = match.group(2)
        python_version = match.group(3)
        abi = match.group(4)
        platform = match.group(5)
    return PackageInfo(
        name=package_name,
        version=package_version,
        python_version=python_version,
        abi=abi,
        platform=platform,
    )


def download_package(
    package_name: str, platform: str, abi: str, config: DownloadConfig
) -> None:
    """指定された条件でパッケージをダウンロードする.

    Parameters
    ----------
    package_name : str
        ダウンロードするパッケージ名.
    platform : str
        対象のプラットフォーム.
    abi : str
        対象のABI.
    config : DownloadConfig
        ダウンロード設定.
    """
    base_command = [
        config.pip_path,
        "download",
        package_name,
        f"--platform={platform}",
        f"--python-version={config.python_version}",
        f"--abi={abi}",
        f"--dest={config.dest_folder}",
    ]
    if config.proxy:
        base_command.append(f"--proxy={config.proxy}")  # プロキシ設定を追加
    only_binary_command = base_command.copy()
    only_binary_command.append("--only-binary=:all:")

    try:
        subprocess.run(only_binary_command, check=True)
        logger.info("%sが正常にダウンロードされました。", package_name)
        return
    except subprocess.CalledProcessError as e:
        if config.include_source:
            pass
        else:
            logger.error(
                "%sのダウンロード中にエラーが発生しました: %s", package_name, e
            )
            return
    # ソース形式を含める場合は、--no-binaryオプションを使用して再度ダウンロード
    no_binary_command = base_command.copy()
    no_binary_command.append("--no-binary=:all:")
    try:
        subprocess.run(no_binary_command, check=True)
        logger.info("%sが正常にダウンロードされました。", package_name)
        return
    except subprocess.CalledProcessError:
        pass
    # 依存関係を無視して --no-depsオプションを使用して再度ダウンロード
    no_deps_command = no_binary_command.copy()
    no_deps_command.append("--no-deps")
    try:
        subprocess.run(no_deps_command, check=True)
        logger.info("%sが正常にダウンロードされました。", package_name)
        return
    except subprocess.CalledProcessError as e:
        logger.error(
            "%sのダウンロード中にエラーが発生しました: %s", package_name, e
        )


def download_package_no_pip(
    package_name: str, platform: str, abi: str, config: DownloadConfig
) -> None:
    """PyPISimpleとrequestsを使用して1つのパッケージをダウンロードする.

    Parameters
    ----------
    package_name : str
        ダウンロードするパッケージ名.
    platform : str
        対象のプラットフォーム.
    abi : str
        対象のABI.
    config : DownloadConfig
        ダウンロード設定.
    """
    logger.info("%sのダウンロードを開始します...", package_name)

    try:
        pypi = PyPISimple()
        packages_info = pypi.get_project_page(package_name)
        if not packages_info:
            logger.warning("%sの情報が見つかりませんでした。", package_name)
            return

        # プラットフォーム、Pythonバージョン、ABIでフィルタリング
        abi = PYTHON_VERSION_TO_ABI.get(
            config.python_version
        )  # 辞書からABIを取得
        if not abi:
            logger.warning(
                "%sのABIが見つかりませんでした。", config.python_version
            )
            return

        dlcnt = 0
        for package in reversed(packages_info.packages):
            skip_flg = False
            # プラットフォームでフィルタリング
            package_info = get_package_info_from_filename(package.filename)
            if "any" != package_info.platform:
                if platform != package_info.platform:
                    skip_flg = True
            # ABIでフィルタリング
            if "none" != package_info.abi:
                if abi != package_info.abi:
                    skip_flg = True
            # Pythonバージョンでフィルタリング
            if "none" != package_info.python_version:
                if (
                    config.python_version.replace(".", "")
                    in package_info.python_version
                ):
                    skip_flg = True
            if skip_flg:
                continue
            # パッケージをダウンロード
            response = requests.get(package.url, stream=True, timeout=10)
            response.raise_for_status()

            # ファイルを保存
            filename = os.path.join(
                config.dest_folder, os.path.basename(package.url)
            )
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            dlcnt += 1
            logger.info("%sのダウンロードが完了しました。", package.filename)
            break
        if config.include_source and dlcnt == 0:
            for package in reversed(packages_info.packages):
                # ソース形式を含める場合は、再度ダウンロード
                if package.filename.endswith(".tar.gz"):
                    response = requests.get(
                        package.url, stream=True, timeout=10
                    )
                    response.raise_for_status()
                    # ファイルを保存
                    filename = os.path.join(
                        config.dest_folder, os.path.basename(package.url)
                    )
                    with open(filename, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    dlcnt += 1
                    logger.info(
                        "%sのダウンロードが完了しました。", package.filename
                    )
                    break
        if dlcnt == 0:
            logger.warning(
                "%sのダウンロードURLが見つかりませんでした。", package_name
            )
    except requests.exceptions.RequestException as e:
        logger.error(
            "%sのダウンロード中にエラーが発生しました: %s", package_name, e
        )


def download_packages_from_list(
    platform: str, abi: str, config: DownloadConfig
) -> None:
    """パッケージリストファイルからパッケージを読み込み、ダウンロードする.

    Parameters
    ----------
    platform : str
        対象のプラットフォーム.
    abi : str
        対象のABI.
    config : DownloadConfig
        ダウンロード設定.
    """
    if not os.path.exists(config.package_list_file):
        messagebox.showerror(
            "エラー",
            f"指定されたファイルが見つかりません: {config.package_list_file}",
        )
        return

    with open(config.package_list_file, "r", encoding="utf-8") as file:
        packages = file.readlines()

    for package_name in packages:
        package_name = package_name.strip()
        if package_name:
            logger.info("%sのダウンロードを開始します...", package_name)
            download_package(package_name, platform, abi, config)


# PythonバージョンとABIの対応辞書
PYTHON_VERSION_TO_ABI = {
    "3.6": "cp36",
    "3.7": "cp37",
    "3.8": "cp38",
    "3.9": "cp39",
    "3.10": "cp310",
    "3.11": "cp311",
    "3.12": "cp312",
    "3.13": "cp313",
}

OS_TO_PLATFORMS = {
    "Windows": ["win_amd64"],
    "Linux": ["manylinux2014_x86_64", "manylinux2010_x86_64"],
    "Linux(manylinux2010_x86_64)": ["manylinux2010_x86_64"],
    "macOS": ["macosx_10_9_x86_64"],
}


def start_download(config: DownloadConfig) -> None:
    """指定されたOSとPythonバージョンでパッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    """
    platforms = OS_TO_PLATFORMS.get(config.os_name)
    if not platforms:
        logger.error("サポートされていないOSです: %s", config.os_name)
        messagebox.showerror(
            "エラー", f"サポートされていないOSです: {config.os_name}"
        )
        return

    # ABIを辞書から取得
    abi = PYTHON_VERSION_TO_ABI.get(config.python_version)
    if not abi:
        logger.error(
            "サポートされていないPythonバージョンです: %s",
            config.python_version,
        )
        messagebox.showerror(
            "エラー",
            "".join(
                [
                    "サポートされていないPythonバージョンです:",
                    f"{config.python_version}",
                ]
            ),
        )
        return

    os.makedirs(config.dest_folder, exist_ok=True)

    for platform in platforms:
        logger.info("Platform: %s, ABI: %s", platform, abi)
        download_packages_from_list(platform, abi, config)


def start_download_no_pip(config: DownloadConfig) -> None:
    """PyPISimpleとrequestsを使用してパッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    """
    platforms = OS_TO_PLATFORMS.get(config.os_name)
    if not platforms:
        logger.error("サポートされていないOSです: %s", config.os_name)
        messagebox.showerror(
            "エラー", f"サポートされていないOSです: {config.os_name}"
        )
        return

    # ABIを辞書から取得
    abi = PYTHON_VERSION_TO_ABI.get(config.python_version)
    if not abi:
        logger.error(
            "サポートされていないPythonバージョンです: %s",
            config.python_version,
        )
        messagebox.showerror(
            "エラー",
            "".join(
                [
                    "サポートされていないPythonバージョンです:",
                    f"{config.python_version}",
                ]
            ),
        )
        return

    os.makedirs(config.dest_folder, exist_ok=True)

    for platform in platforms:
        with open(config.package_list_file, "r", encoding="utf-8") as file:
            packages = file.readlines()

        for package_name in packages:
            package_name = package_name.strip()
            if not package_name:
                continue

            # ダウンロード処理を関数に委譲
            download_package_no_pip(package_name, platform, abi, config)


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

    def setup_ui(self) -> None:
        """GUIの各要素を設定する."""
        # pip使用選択
        pip_use_lbl = Label(self, text="ダウンロード方法:")
        pip_use_lbl.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.download_method_var = StringVar(value="pip")
        pip_radio = Radiobutton(
            self,
            text="pipを使う",
            variable=self.download_method_var,
            value="pip",
        )
        pip_radio.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        no_pip_radio = Radiobutton(
            self,
            text="pipを使わない",
            variable=self.download_method_var,
            value="no_pip",
        )
        no_pip_radio.grid(row=0, column=2, padx=10, pady=5, sticky="w")

        # OS選択
        Label(self, text="OSを選択:").grid(
            row=1, column=0, padx=10, pady=5, sticky="w"
        )
        self.os_var = StringVar(value="Windows")
        os_options = [
            "Windows",
            "Linux",
            "Linux(manylinux2010_x86_64)",
            "macOS",
        ]
        os_menu = Combobox(
            self, textvariable=self.os_var, values=os_options, state="readonly"
        )
        os_menu.grid(row=1, column=1, padx=10, pady=5)

        # Pythonバージョン選択（複数選択可能）
        Label(self, text="Pythonバージョン（複数選択可）:").grid(
            row=2, column=0, padx=10, pady=5, sticky="w"
        )
        self.python_versions = [
            "3.6",
            "3.7",
            "3.8",
            "3.9",
            "3.10",
            "3.11",
            "3.12",
            "3.13",
        ]
        self.python_version_listbox = Listbox(
            self, selectmode="multiple", height=len(self.python_versions)
        )
        for version in self.python_versions:
            self.python_version_listbox.insert(END, version)
        self.python_version_listbox.grid(row=2, column=1, padx=10, pady=5)

        # パッケージリストファイル選択
        self.package_list_entry = LabeledEntry(
            self,
            "パッケージリスト:",
            row=3,
            column=0,
            entry_state="readonly",
        )
        # 初期値をスクリプトの格納ディレクトリの package_list.txt に設定
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_package_list_path = os.path.join(script_dir, "package_list.txt")
        self.package_list_entry.set(default_package_list_path)
        package_list_button = Button(
            self, text="選択", command=self.select_package_list
        )
        package_list_button.grid(row=3, column=2, padx=10, pady=5)

        # ダウンロード先フォルダ選択
        self.dest_folder_entry = LabeledEntry(
            self, "ダウンロード先:", row=4, column=0, entry_state="readonly"
        )
        # 初期値をスクリプトの格納ディレクトリの downloads に設定
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_dest_folder = os.path.join(script_dir, "downloads")
        self.dest_folder_entry.set(default_dest_folder)
        dest_folder_button = Button(
            self, text="選択", command=self.select_dest_folder
        )
        dest_folder_button.grid(row=4, column=2, padx=10, pady=5)

        # pipパス指定
        self.pip_path_entry = LabeledEntry(self, "pipのパス:", row=5, column=0)
        self.pip_path_entry.set(self.get_default_pip_path())
        pip_path_button = Button(
            self, text="選択", command=self.select_pip_path
        )
        pip_path_button.grid(row=5, column=2, padx=10, pady=5)

        # プロキシ設定
        self.use_proxy_var = BooleanVar(value=False)
        use_proxy_check = ttk.Checkbutton(
            self,
            text="プロキシを使用する",
            variable=self.use_proxy_var,
            command=self.toggle_proxy_widgets,
        )
        use_proxy_check.grid(
            row=6, column=0, columnspan=2, padx=10, pady=5, sticky="w"
        )

        self.proxy_user_entry = LabeledEntry(
            self, "ユーザー:", row=7, column=0, entry_state="disabled"
        )

        self.proxy_password_entry = LabeledEntry(
            self,
            "パスワード:",
            row=8,
            column=0,
            entry_state="disabled",
            show="*",
        )

        self.proxy_server_entry = LabeledEntry(
            self, "サーバ:", row=9, column=0, entry_state="disabled"
        )

        self.proxy_port_entry = LabeledEntry(
            self, "ポート:", row=10, column=0, entry_state="disabled"
        )
        validatecommand = (self.register(self.validate_port), "%P")
        self.proxy_port_entry.entry["validatecommand"] = validatecommand

        # ソース形式を含めるチェックボックス
        Label(self, text="ソース形式を含める:").grid(
            row=11, column=0, padx=10, pady=5, sticky="w"
        )
        self.include_source_var = BooleanVar(value=False)
        include_source_check = ttk.Checkbutton(
            self, variable=self.include_source_var
        )
        include_source_check.grid(row=11, column=1, padx=10, pady=5)

        # ダウンロード開始ボタン
        download_button = Button(
            self, text="ダウンロード開始", command=self.on_download
        )
        download_button.grid(row=12, column=0, columnspan=3, pady=10)

    def toggle_proxy_widgets(self) -> None:
        """プロキシ関連のウィジェットを有効化または無効化する."""
        state = "normal" if self.use_proxy_var.get() else "disabled"
        self.proxy_user_entry.configure_state(state)
        self.proxy_password_entry.configure_state(state)
        self.proxy_server_entry.configure_state(state)
        self.proxy_port_entry.configure_state(state)

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
            self.package_list_entry.set(file_path)

    def select_dest_folder(self) -> None:
        """ダウンロード先フォルダを選択する."""
        folder_path = filedialog.askdirectory(
            title="ダウンロード先フォルダを選択",
            initialdir=self.dest_folder_entry.get(),
        )
        if folder_path:
            self.dest_folder_entry.set(folder_path)

    def select_pip_path(self) -> None:
        """pipのパスを選択する."""
        file_path = filedialog.askopenfilename(
            title="pipのパスを選択",
            initialfile=self.pip_path_entry.get(),
            filetypes=[("実行ファイル", "*.exe"), ("すべてのファイル", "*.*")],
        )
        if file_path:
            self.pip_path_entry.set(file_path)

    def on_download(self) -> None:
        """ダウンロード処理を開始する."""
        download_method = self.download_method_var.get()
        use_pip = download_method == "pip" or not PYPISIMPLE_AVAILABLE
        pip_path = self.pip_path_entry.get() if use_pip else ""
        os_name = self.os_var.get()
        selected_versions = [
            self.python_versions[i]
            for i in self.python_version_listbox.curselection()
        ]
        package_list_file = self.package_list_entry.get()
        dest_folder = self.dest_folder_entry.get()
        include_source = self.include_source_var.get()

        # プロキシ情報を組み立て
        proxy = None
        if self.use_proxy_var.get():
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

        if not selected_versions:
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
        for python_version in selected_versions:
            config = DownloadConfig(
                os_name=os_name,
                python_version=python_version,
                package_list_file=package_list_file,
                dest_folder=dest_folder,
                include_source=include_source,
                proxy=proxy,
                use_pip=use_pip,
                pip_path=pip_path,
            )

            if config.use_pip:
                start_download(config)
            else:
                start_download_no_pip(config)

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


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
