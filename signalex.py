#! python3
"""シグナル拡張."""
import subprocess
import signal
import sys
import select
import threading

from loggingex import generate_logger

# グローバル変数でサブプロセスを追跡
subprocess_instances = []

logger = generate_logger(name=__name__, debug=__debug__, filepath=__file__)


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
        logger.info("すべてのサブプロセスを終了します...")
        while subprocess_instances:  # リストが空になるまでループ
            instance = subprocess_instances.pop(
                0
            )  # リストの先頭から取得して削除
            instance.terminate()  # サブプロセスを終了
            instance.wait()  # 終了を待機
    sys.exit(0)


def stream_output(pipe, log_func):
    """リアルタイムで出力をログに記録"""
    for line in iter(pipe.readline, ""):
        log_func(line.strip())


def run_command(command: list[str]) -> None:
    """コマンドの実行結果をパイプでログ出力する.

    Parameters
    ----------
    command : _type_
        コマンド
    """
    global subprocess_instances  # pylint: disable=global-variable-not-assigned
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    subprocess_instances.append(process)  # サブプロセスをリストに追加

    if sys.platform == "win32":
        # Windowsでは `threading` を使用
        stdout_thread = threading.Thread(
            target=stream_output, args=(process.stdout, logger.info)
        )
        stderr_thread = threading.Thread(
            target=stream_output, args=(process.stderr, logger.error)
        )

        stdout_thread.start()
        stderr_thread.start()
        try:
            process.wait(timeout=10.0)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        except TimeoutError:
            logger.error("Timeout command=%s", command)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        stdout_thread.join()
        stderr_thread.join()
    else:
        # Unix系では `select` を使用
        while True:
            reads = [process.stdout, process.stderr]
            readable, _, _ = select.select(reads, [], [], 0.1)

            for stream in readable:
                line = stream.readline().strip()
                if line:
                    if stream == process.stdout:
                        logger.info(line)
                    else:
                        logger.error(line)

            if process.poll() is not None:
                break
        try:
            process.wait(timeout=10.0)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        except TimeoutError:
            logger.error("Timeout command=%s", command)
            subprocess_instances.remove(process)  # サブプロセスをリストから削除
        logger.info("サブプロセスを終了しました: %s", command)


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
    logger.info("サブプロセスを開始しました: %s", command)
