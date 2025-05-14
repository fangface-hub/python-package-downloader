#! python3
"""シグナル拡張."""
import subprocess
import signal
import sys

# グローバル変数でサブプロセスを追跡
subprocess_instances = []


def __signal_handler(sig, frame) -> None:  # pylint: disable=unused-argument
    """
    子プロセスを終了するシグナルハンドラ.

    Parameters
    ----------
    sig : TYPE
        シグナル.
    frame : TYPE
        フレーム.

    Returns
    -------
    None
        なし.

    """
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    if subprocess_instances:
        print("すべてのサブプロセスを終了します...")
        while subprocess_instances:  # リストが空になるまでループ
            instance = subprocess_instances.pop(
                0
            )  # リストの先頭から取得して削除
            instance.terminate()  # サブプロセスを終了
            instance.wait()  # 終了を待機
    sys.exit(0)


def terminate_subprocess_at_signal() -> None:
    """
    親プロセス終了時に子プロセス終了のハンドラ登録.

    Returns
    -------
    None
        なし.

    """
    signal.signal(signal.SIGINT, __signal_handler)
    signal.signal(signal.SIGTERM, __signal_handler)


def start_subprocess(command: list) -> None:
    """
    サブプロセスを開始する.

    Parameters
    ----------
    command : list
        実行するコマンド.

    Returns
    -------
    None
        なし.

    """
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    process = subprocess.Popen(command)
    subprocess_instances.append(process)  # サブプロセスをリストに追加
    print(f"サブプロセスを開始しました: {command}")
