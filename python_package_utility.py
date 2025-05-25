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

package_requirements_history = []
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

# Pythonバージョンとファイル名パターン
PYTHON_VERSION_TO_PATTERN = {
    "3.6": r"(any|none|py3|cp36)",
    "3.7": r"(any|none|py3|cp37)",
    "3.8": r"(any|none|py3|cp38)",
    "3.9": r"(any|none|py3|cp39)",
    "3.10": r"(any|none|py3|cp310)",
    "3.11": r"(any|none|py3|cp311)",
    "3.12": r"(any|none|py3|cp312)",
    "3.13": r"(any|none|py3|cp313)",
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


@dataclass
class PackageRequirements:
    """
    パッケージの依存関係を保持するデータクラス.

    Attributes
    ----------
    package_name : str
        パッケージ名.
    version_condition : str
        バージョン条件 (例: ">=1.0.0").
    """

    package_name: str
    version_condition: str

    @property
    def requirement(self) -> str:
        """パッケージ名とバージョン条件を結合した文字列を返す."""
        return f"{self.package_name}{self.version_condition}"


# ロギングの設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_package_condition(requirement: str) -> PackageRequirements | None:
    """パッケージ名とバージョン条件を抽出する.

    Parameters
    ----------
    text : str
        パッケージ名とバージョン条件の文字列.

    Returns
    -------
    PackageRequirements | None
        パッケージとバージョン条件.
    """
    pattern = re.compile(r"^([a-zA-Z0-9_\-]+)([<>=!]+)?(\d+\.\d+\.\d+)?$")
    match = pattern.match(requirement)

    if match:
        package = match.group(1)
        operator = match.group(2) if match.group(2) else ""
        version = match.group(3) if match.group(3) else ""
        version_condition = operator + version if operator else ""
        return PackageRequirements(package, version_condition)

    return None  # 不明なフォーマット


def find_whl_package_info_list(
    folder: str, package_name: str
) -> list[PackageInfo]:
    """指定フォルダ内の .whl ファイルから指定パッケージのバージョンを取得"""
    package_info_list = []

    for file in os.listdir(folder):
        if not file.startswith(package_name) or not file.endswith(".whl"):
            continue
        pakage_info = get_package_info_from_whl(file)
        if pakage_info.name == package_name:
            package_info_list.append(pakage_info)

    return package_info_list


def find_targz_package_info_list(
    folder: str, package_name: str
) -> list[PackageInfo]:
    """指定フォルダ内の .tar.gz ファイルから指定パッケージのバージョンを取得"""
    package_info_list = []

    for file in os.listdir(folder):
        if not file.startswith(package_name) or not file.endswith(".tar.gz"):
            continue
        match = re.search(f"{package_name}-([0-9.]*).tar.gz", file)
        if match:
            version = match.group(1)
            package_info_list.append(
                PackageInfo(
                    name=package_name,
                    version=version,
                    python_version="none",
                    abi="none",
                    platform="none",
                )
            )
            continue

    return package_info_list


def normalize_version(version):
    """バージョンを標準化（メジャーのみの場合も補完）"""
    version_parts = version.split(".")

    # メジャーのみの場合はマイナー・パッチを補完（例: "2" → "2.0.0"）
    while len(version_parts) < 3:
        version_parts.append("0")

    return [int(part) if part.isdigit() else part for part in version_parts]


def compare_versions(version1, version2, operator):
    """バージョンを分割して数値比較を行う"""
    if version2 is None or operator is None:
        return True
    v1_parts = normalize_version(version1)
    v2_parts = normalize_version(version2)
    if operator == "==":
        return v1_parts == v2_parts
    if operator == ">":
        return v1_parts > v2_parts
    if operator == ">=":
        return v1_parts >= v2_parts
    if operator == "<":
        return v1_parts < v2_parts
    if operator == "<=":
        return v1_parts <= v2_parts
    return False  # 不明な条件


def parse_condition(condition):
    """演算子とバージョン番号を正規表現で抽出"""
    pattern = re.compile(r"^(==|!=|>=|<=|>|<)\s*(\d+\.\d+\.\d+)$")
    match = pattern.match(condition)

    if match:
        return match.group(1), match.group(2)  # 演算子, バージョン番号

    return None, None  # 未指定


def check_whl_version(
    folder: str,
    requirement: PackageRequirements,
    platform: str,
    python_version: str,
) -> bool:
    """指定フォルダ内の .whl のバージョンを取得し、条件と比較する.

    Parameters
    ----------
    folder : str
        フォルダのパス.
    requirement : PackageRequirements
        パッケージの要件.
    platform : str
        プラットフォーム.
    python_version : str
        Pythonのバージョン.

    Returns
    -------
    bool
        条件に合致するバージョンが存在するかどうか.
    """
    ret = False
    package_info_list = find_whl_package_info_list(
        folder, requirement.package_name
    )

    python_version_pattern = PYTHON_VERSION_TO_PATTERN.get(
        python_version, "none"
    )

    # 条件の解析
    operator, target_version = parse_condition(requirement.version_condition)

    for package_info in package_info_list:
        if (
            package_info.platform != "any"
            and platform not in package_info.platform
        ):
            continue
        if not re.search(python_version_pattern, package_info.python_version):
            continue
        if compare_versions(package_info.version, target_version, operator):
            ret = True
            break
    logger.debug(
        "return=%s,folder=%s,requirement=%s,platform=%s,python_version=%s",
        ret,
        folder,
        requirement,
        platform,
        python_version,
    )
    logger.debug("package_info_list=%s", package_info_list)
    return ret


def check_targz(
    folder: str,
    requirement: PackageRequirements,
) -> bool:
    """指定フォルダ内の .tar.gz のバージョンを取得し、条件と比較する.

    Parameters
    ----------
    folder : str
        フォルダのパス.
    requirement : PackageRequirements
        パッケージの要件.

    Returns
    -------
    bool
        条件に合致するバージョンが存在するかどうか.
    """
    ret = False
    package_info_list = find_targz_package_info_list(
        folder, requirement.package_name
    )
    # 条件の解析
    operator, target_version = parse_condition(requirement.version_condition)
    for pachage_info in package_info_list:
        # バージョン番号が適用外はスキップ
        if compare_versions(pachage_info.version, target_version, operator):
            ret = True
            break
    logger.debug("return=%s,folder=%s,requirement=%s", ret, folder, requirement)
    return ret


def get_dependencies_from_whl(whl_file: str) -> list[PackageRequirements]:
    """.whlファイルから依存関係を取得する.

    Parameters
    ----------
    whl_file : str
        .whlファイルのパス.

    Returns
    -------
    list[PackageRequirements]
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
                requirement = parse_package_condition(
                    "".join(dep_package.split())
                )
                if requirement is None:
                    continue
                dependencies.append(requirement)
    logger.debug("whl_file=%s,dependencies=%s", whl_file, dependencies)
    return dependencies


def get_dependencies_from_targz(targz_file: str) -> list[PackageRequirements]:
    """.tar.gzファイルから依存関係を取得する.

    Parameters
    ----------
    targz_file : str
        .tar.gzファイルのパス.

    Returns
    -------
    list[PackageRequirements]
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
            requirement = parse_package_condition("".join(dep_package.split()))
            if requirement is None:
                continue
            dependencies.append(requirement)
    logger.debug("targz_file=%s,dependencies=%s", targz_file, dependencies)
    return dependencies


def get_package_info_from_whl(filename: str) -> PackageInfo:
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


def get_package_info_from_targz(filename: str) -> PackageInfo:
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
    match = re.search(r"([^-]+)-([^-]+)\.tar\.gz", filename)
    if match:
        package_name = match.group(1)
        package_version = match.group(2)
    return PackageInfo(
        name=package_name,
        version=package_version,
        python_version="none",
        abi="none",
        platform="none",
    )


def download_package_pip(
    package_requirements: PackageRequirements, config: DownloadConfig
) -> None:
    """指定された条件でpipでパッケージをダウンロードする.

    Parameters
    ----------
    package_requirements: PackageRequirements
        ダウンロードするパッケージの要件.
    config : DownloadConfig
        ダウンロード設定.
    """
    base_command = [
        config.pip_path,
        "download",
        package_requirements.requirement,
    ]
    if config.proxy:
        base_command.append(f"--proxy={config.proxy}")  # プロキシ設定を追加
    before_files = set(os.listdir(config.dest_folder))
    try:
        for os_name in config.os_list:
            for platform in OS_TO_PLATFORMS.get(os_name):
                for python_version in config.python_versions:
                    if check_whl_version(
                        folder=config.dest_folder,
                        requirement=package_requirements,
                        platform=platform,
                        python_version=python_version,
                    ):
                        continue
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
        if 0 < len(new_files):
            logger.info("%sが正常にダウンロードされました。", new_files)
            if config.include_deps:
                download_dep_package(config=config, filelist=new_files)
            return
    except subprocess.CalledProcessError as e:
        if config.include_source:
            pass
        else:
            logger.error(
                "%sのダウンロード中にエラーが発生しました: %s",
                package_requirements,
                e,
            )
            return
    if not config.include_source:
        return
    if check_targz(folder=config.dest_folder, requirement=package_requirements):
        logger.info(
            "%sのソース形式はすでにダウンロード済みです。", package_requirements
        )
        return
    # ソース形式を含める場合は、--no-binaryオプションを使用して再度ダウンロード
    no_binary_command = base_command.copy()
    no_binary_command.append("--no-binary=:all:")
    no_binary_command.append(f"--dest={config.dest_folder}")
    try:
        run_command(no_binary_command)
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
    if 0 < len(new_files):
        logger.info("%sが正常にダウンロードされました。", new_files)
        if config.include_deps:
            download_dep_package(config=config, filelist=new_files)


def download_package_no_pip(
    package_requirements: PackageRequirements, config: DownloadConfig
) -> None:
    """PyPISimpleとrequestsを使用して1つのパッケージをダウンロードする.

    Parameters
    ----------
    package_requirements: PackageRequirements
        ダウンロードするパッケージの要件.
    config : DownloadConfig
        ダウンロード設定.
    """
    logger.info(
        "%sのダウンロードを開始します...", package_requirements.package_name
    )
    before_files = set(os.listdir(config.dest_folder))
    try:
        pypi = PyPISimple()
        packages_info = pypi.get_project_page(package_requirements.package_name)
        if not packages_info:
            logger.warning(
                "%sの情報が見つかりませんでした。", package_requirements
            )
            return

        dlcnt = 0
        for package in reversed(packages_info.packages):
            # プラットフォームでフィルタリング
            package_info = get_package_info_from_whl(package.filename)
            if check_whl_version(
                folder=config.dest_folder,
                requirement=package_requirements,
                platform=package_info.platform,
                python_version=package_info.python_version,
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
            if check_targz(
                folder=config.dest_folder, requirement=package_requirements
            ):
                logger.info(
                    "%sのソース形式はすでにダウンロード済みです。",
                    package_requirements,
                )
                return
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
            "%sのダウンロードURLが見つかりませんでした。", package_requirements
        )
    except requests.exceptions.RequestException as e:
        logger.error(
            "%sのダウンロード中にエラーが発生しました: %s",
            package_requirements,
            e,
        )


def download_packages(
    config: DownloadConfig, package_requirements_list: list[PackageRequirements]
) -> None:
    """パッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    package_requirements_list: list[PackageRequirements]
        ダウンロードするパッケージのリスト.
    """
    for package_requirements in package_requirements_list:
        if package_requirements in package_requirements_history:
            continue
        package_requirements_history.append(package_requirements)
        logger.info("%sのダウンロードを開始します...", package_requirements)
        if config.use_pip:
            download_package_pip(
                package_requirements=package_requirements, config=config
            )
            continue
        download_package_no_pip(
            package_requirements=package_requirements, config=config
        )


def download_dep_package(config: DownloadConfig, filelist: list[str]):
    """依存ファイルをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    filelist : list[str]
        ファイルリスト.
    """
    package_requirements_list = []
    for file_ in filelist:
        file_path = os.path.join(config.dest_folder, file_)
        if file_.endswith(".tar.gz"):
            dependencies = get_dependencies_from_targz(targz_file=file_path)
            package_requirements_list.extend(dependencies)
            continue
        if file_.endswith(".whl"):
            dependencies = get_dependencies_from_whl(whl_file=file_path)
            package_requirements_list.extend(dependencies)
            continue
    download_packages(
        config=config, package_requirements_list=package_requirements_list
    )


def start_download(config: DownloadConfig) -> None:
    """PyPISimpleとrequestsを使用してパッケージをダウンロードする.

    Parameters
    ----------
    config : DownloadConfig
        ダウンロード設定.
    """
    package_requirements_history.clear()
    os.makedirs(config.dest_folder, exist_ok=True)
    package_requirements_list = []
    with open(config.package_list_file, "r", encoding="utf-8") as file:
        for line_ in file.readlines():
            requirement = parse_package_condition("".join(line_.split()))
            package_requirements_list.append(requirement)
    download_packages(
        config=config, package_requirements_list=package_requirements_list
    )
