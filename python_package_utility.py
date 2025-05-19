"""Pythonパッケージのダウンロードに関するユーティリティモジュール."""

# -*- coding: utf-8 -*-
import os
import subprocess
import tarfile
import zipfile
import re
import logging
from dataclasses import dataclass, field
from signalex import run_command

try:
    from pypi_simple import PyPISimple
    import requests

    PYPISIMPLE_AVAILABLE = True
except ImportError:
    PYPISIMPLE_AVAILABLE = False
from loggingex import generate_logger

logger = generate_logger(name=__name__, debug=__debug__, filepath=__file__)

dependencies_history = []
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
    "Linux(manylinux2010_x86_64,manylinux2014_x86_64)": [
        "manylinux2014_x86_64",
        "manylinux2010_x86_64",
    ],
    "Linux(manylinux2010_x86_64)": ["manylinux2010_x86_64"],
    "macOS": ["macosx_10_9_x86_64"],
}


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

    os_list: list[str] = field(default_factory=list)
    python_versions: list[str] = field(default_factory=list)
    package_list_file: str = None
    dest_folder: str = None
    include_source: bool = False
    include_deps: bool = False
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


# ロギングの設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_dependencies_from_whl(whl_file: str) -> list[str]:
    """.whlファイルから依存関係を取得する.

    Parameters
    ----------
    whl_file : str
        .whlファイルのパス.

    Returns
    -------
    list[str]
        依存関係のリスト.
    """
    dependencies = []
    with zipfile.ZipFile(whl_file, "r") as z:
        metadata_files = [f for f in z.namelist() if "METADATA" in f]
        if not metadata_files:
            logger.info("%sのMETADATAファイルが見つかりません。", whl_file)
            return dependencies
        with z.open(metadata_files[0]) as metadata:
            lines = metadata.read().decode().split("\n")
            for line in lines:
                if not line.startswith("Requires-Dist:"):
                    continue
                extra_match = re.match(" extra == ", line)
                # extraのパッケージは無視する
                if extra_match:
                    continue
                dep_package = re.sub(r"(Requires-Dist:)([^;]*).*$", r"\2", line)
                dependencies.append(dep_package)
    logger.debug("whl_file=%s,dependencies=%s", whl_file, dependencies)
    return dependencies


def get_dependencies_from_targz(targz_file: str) -> list[str]:
    """.tar.gzファイルから依存関係を取得する.

    Parameters
    ----------
    targz_file : str
        .tar.gzファイルのパス.

    Returns
    -------
    list[str]
        依存関係のリスト.
    """
    dependencies = []
    with tarfile.open(targz_file, "r:gz") as tar:
        pkg_info_files = [f for f in tar.getnames() if f.endswith("PKG-INFO")]
        if not pkg_info_files:
            print("PKG-INFO ファイルが見つかりません。")
            return dependencies

        pkg_info = tar.extractfile(pkg_info_files[0]).read().decode()
        for line in pkg_info.split("\n"):
            if not line.startswith("Requires-Dist:"):
                continue
            extra_match = re.match(" extra == ", line)
            # extraのパッケージは無視する
            if extra_match:
                continue
            dep_package = re.sub(r"(Requires-Dist:)([^;]*).*$", r"\2", line)
            dependencies.append(dep_package)
    logger.debug("targz_file=%s,dependencies=%s", targz_file, dependencies)
    return dependencies


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


def download_package_pip(package_name: str, config: DownloadConfig) -> None:
    """指定された条件でpipでパッケージをダウンロードする.

    Parameters
    ----------
    package_name : str
        ダウンロードするパッケージ名.
    config : DownloadConfig
        ダウンロード設定.
    """
    base_command = [
        config.pip_path,
        "download",
        package_name,
    ]
    if config.proxy:
        base_command.append(f"--proxy={config.proxy}")  # プロキシ設定を追加
    before_files = set(os.listdir(config.dest_folder))
    try:
        for os_name in config.os_list:
            for platform in OS_TO_PLATFORMS.get(os_name):
                for python_version in config.python_versions:
                    tmp_version = python_version.replace(".", "")
                    abi = PYTHON_VERSION_TO_ABI.get(python_version)
                    only_binary_command = base_command.copy()
                    only_binary_command.append("--only-binary=:all:")
                    only_binary_command.append(f"--platform={platform}")
                    only_binary_command.append(
                        f"--python-version={tmp_version}"
                    )
                    only_binary_command.append(f"--abi={abi}")
                    only_binary_command.append(f"--dest={config.dest_folder}")
                    run_command(only_binary_command)
        after_files = set(os.listdir(config.dest_folder))
        new_files = after_files - before_files
        logger.info("%sが正常にダウンロードされました。", new_files)
        if config.include_deps:
            download_dep_package(config=config, filelist=new_files)
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
    for os_name in config.os_list:
        for platform in OS_TO_PLATFORMS.get(os_name):
            for python_version in config.python_versions:
                tmp_version = python_version.replace(".", "")
                abi = PYTHON_VERSION_TO_ABI.get(python_version)
                no_binary_command = base_command.copy()
                no_binary_command.append("--no-binary=:all:")
                no_binary_command.append(f"--platform={platform}")
                no_binary_command.append(f"--python-version={tmp_version}")
                no_binary_command.append(f"--abi={abi}")
                no_binary_command.append(f"--dest={config.dest_folder}")
                try:
                    run_command(no_binary_command)
                    continue
                except subprocess.CalledProcessError:
                    pass
                no_deps_command = no_binary_command.copy()
                no_deps_command.append("--no-deps")
                try:
                    run_command(no_deps_command)
                except subprocess.CalledProcessError:
                    pass
    after_files = set(os.listdir(config.dest_folder))
    new_files = after_files - before_files
    logger.info("%sが正常にダウンロードされました。", new_files)
    if config.include_deps:
        download_dep_package(config=config, filelist=new_files)


def download_package_no_pip(package_name: str, config: DownloadConfig) -> None:
    """PyPISimpleとrequestsを使用して1つのパッケージをダウンロードする.

    Parameters
    ----------
    package_name : str
        ダウンロードするパッケージ名.
    config : DownloadConfig
        ダウンロード設定.
    """
    logger.info("%sのダウンロードを開始します...", package_name)
    before_files = set(os.listdir(config.dest_folder))
    try:
        pypi = PyPISimple()
        packages_info = pypi.get_project_page(package_name)
        if not packages_info:
            logger.warning("%sの情報が見つかりませんでした。", package_name)
            return

        dlcnt = 0
        for package in reversed(packages_info.packages):
            # プラットフォームでフィルタリング
            package_info = get_package_info_from_filename(package.filename)
            if not check_hit_package_info(
                config=config, package_info=package_info
            ):
                continue
            # ファイル名取得
            filename = os.path.join(
                config.dest_folder, os.path.basename(package.url)
            )
            if os.path.exists(filename):
                continue

            # パッケージをダウンロード
            response = requests.get(package.url, stream=True, timeout=10)
            response.raise_for_status()

            # ファイルを保存
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            dlcnt += 1
            break
        if config.include_source and dlcnt == 0:
            for package in reversed(packages_info.packages):
                # ソース形式を含める場合は、再度ダウンロード
                if package.filename.endswith(".tar.gz"):
                    # ファイル名取得
                    filename = os.path.join(
                        config.dest_folder, os.path.basename(package.url)
                    )
                    if os.path.exists(filename):
                        continue
                    response = requests.get(
                        package.url, stream=True, timeout=10
                    )
                    response.raise_for_status()
                    # ファイルを保存
                    with open(filename, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    dlcnt += 1
                    break
        after_files = set(os.listdir(config.dest_folder))
        new_files = after_files - before_files
        if 0 < len(new_files) and 0 < dlcnt:
            logger.info("%sのダウンロードが完了しました。", new_files)
            if config.include_deps:
                download_dep_package(config=config, filelist=new_files)
            return
        logger.warning(
            "%sのダウンロードURLが見つかりませんでした。", package_name
        )
    except requests.exceptions.RequestException as e:
        logger.error(
            "%sのダウンロード中にエラーが発生しました: %s", package_name, e
        )


def check_hit_package_info(
    config: DownloadConfig, package_info: PackageInfo
) -> bool:
    """パッケージがダウンロード対象か判定する.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    package_info : PackageInfo
        パッケージ情報.

    Returns
    -------
    bool
        判定結果
    """
    if "any" != package_info.platform:
        platform_list = []
        for os_name in config.os_list:
            platform_list.append(OS_TO_PLATFORMS.get(os_name))
        if package_info.platform not in platform_list:
            return False

    # ABIでフィルタリング
    if "none" != package_info.abi:
        abi_list = []
        for python_version in config.python_versions:
            abi_list.append(PYTHON_VERSION_TO_ABI.get(python_version))
        if package_info.abi not in abi_list:
            return False
    # Pythonバージョンでフィルタリング
    if "none" != package_info.python_version:
        python_version_list = []
        for python_version in config.python_versions:
            python_version_list.append(python_version.replace(".", ""))
        if package_info.python_version not in python_version_list:
            return False
    return True


def download_packages(config: DownloadConfig, packages: list[str]) -> None:
    """_summary_

    Parameters
    ----------
    config : DownloadConfig
        _description_
    packages : list[str]
        _description_
    """
    global dependencies_history  # pylint: disable=global-variable-not-assigned
    for package_name in packages:
        package_name = package_name.strip()
        if not package_name:
            continue
        if package_name in dependencies_history:
            continue
        dependencies_history.append(package_name)
        logger.info("%sのダウンロードを開始します...", package_name)
        if config.use_pip:
            download_package_pip(package_name, config)
        else:
            download_package_no_pip(package_name, config)


def download_dep_package(config: DownloadConfig, filelist: list[str]):
    """依存ファイルをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    filelist : list[str]
        ファイルリスト.
    """
    packages = []
    for file_ in filelist:
        file_path = os.path.join(config.dest_folder, file_)
        if file_.endswith(".tar.gz"):
            dependencies = get_dependencies_from_targz(targz_file=file_path)
            packages.extend(dependencies)
            continue
        if file_.endswith(".whl"):
            dependencies = get_dependencies_from_whl(whl_file=file_path)
            packages.extend(dependencies)
            continue
    download_packages(config=config, packages=packages)


def start_download(config: DownloadConfig) -> None:
    """PyPISimpleとrequestsを使用してパッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    """
    global dependencies_history  # pylint: disable=global-statement
    dependencies_history = []
    os.makedirs(config.dest_folder, exist_ok=True)

    with open(config.package_list_file, "r", encoding="utf-8") as file:
        packages = file.readlines()
    download_packages(config=config, packages=packages)
