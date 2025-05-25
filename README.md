# pythonパッケージダウンローダー

このプロジェクトは、指定されたプラットフォームやPythonバージョンに対応したパッケージをダウンロードできるPythonパッケージダウンローダーです。さまざまな環境での依存関係管理を簡単にすることを目的としています。

## プロジェクト構成

```
python_package_downloader
├── python_package_downloader.py  # パッケージダウンローダーのメインスクリプト
├── requirements.txt              # 依存関係のあるPythonパッケージのリスト
├── .gitignore                    # Gitで無視するファイルやディレクトリ
├── package_list.txt              # パッケージリストサンプル
├── downloads                     # ダウンロードフォルダ
└── README.md                     # プロジェクトのドキュメント
```

## インストール

必要な依存関係をインストールするには、以下のコマンドを実行してください:
pipを使用してダウンロードする場合はインストール不要です。

```
pip install pypi-simple request cryptography
```

## 使用方法

1. リポジトリをダウンロードして、python_package_downloader.py を実行する


1. ダウンロード情報を入力する

    画面項目は以下のとおり。 

    | 画面項目 | 説明 |
    | ---- | ---- |
    | ダウンロード方法 | 必須項目<br>PyPISimpleとrequestsが未インストールの場合は強制的にpipを使う。<br>pipを使う： ダウンロード環境の pip を使って pip download する <br> pipを使わない： PyPISimpleとrequestsを使用してパッケージをダウンロードする |
    | OSを選択 | Windows,Linux,macOS を選択する |
    | Pythonバージョン | 必須項目,複数選択可<br>ターゲットのpythonバージョンを選択する |
    | パッケージリスト | 必須項目<br>パッケージリスト(テキストファイル)のパスを指定する<br>スクリプト格納場所の package_list.txt が初期値 |
    | ダウンロード先 | 必須項目<br>ダウンロード先のフォルダを指定する。<br>スクリプト格納場所の downloads が初期値 | 
    | pipのパス | pipを使う場合必須項目<br>ダウンロード環境にある pip を探して初期ひょうじする |
    | プロキシを使用する<br>ユーザ～ポート | 任意項目<br>プロキシを使う場合、入力する |
    | ソース形式を含める | 任意項目<br> ダウンロードできなかった場合、tar.gz形式のダウンロードを試みる |  


1. 「ダウンロード開始」ボタンを押す

## ビルド方法

1. Nuitka をインストールする

1. mingw64 をインストールする

1. build_for_nuitka.bat のパスを編集する

1. build_for_nuitka.bat を実行する

## 署名方法

Nuitkaで実行ファイルにするとWindowsDefenderなどでウィルスを誤検知するので、自己証明書を作成して実行ファイルに署名してみてください。

[こちらの記事を参考にしました](https://qiita.com/tada0724/items/d37c26d447de86cd7285)

管理者権限のMS-DOSコマンドプロンプトで実行する

```dos

:: 通常の名称 適当に変えてください
set yourname=yourname

:: 組織名称 適当に変えてください
set orgname=orgname

:: 出力ディレクトリ 適当にかえてください
set outdir="C:\Users\youername\Documents\python_package_downloader"

:: アプリケーションパス
set aplicationpath="%outdir%\python_package_downloader.exe"

:: パスワード 適当に変えてください
set passwd=password

:: 秘密鍵ファイル(.pvkファイル)
set pvkfile="%outdir%\%yourname%.pvk"

:: 証明書ファイル(.cerファイル)
set cerfile="%outdir%\%yourname%.cer"

:: 秘密鍵ファイル(.pvkファイル)と証明書ファイル(.cerファイル)の作成
makecert ^
    /a sha256 ^
    /n "CN=%yourname%,O=%orgname%,C=JP" ^
    /r /h 0 ^
    /eku "1.3.6.1.5.5.7.3.3,1.3.6.1.4.1.311.10.3.13" ^
    /sv %pvkfile% %cerfile%

:: Transit XV Pack プロジェクトファイル().pfxファイル)
set pfxfile="%outdir%\%yourname%.pfx"

:: Transit XV Pack プロジェクトファイル().pfxファイル)の作成
pvk2pfx ^
    /pvk %pvkfile% ^
    /pi %passwd% ^
    /spc %cerfile% ^
    /pfx %pfxfile% ^
    /po %passwd%

:: 電子署名
signtool sign ^
    /fd sha256 ^
    /f %pfxfile% ^
    /p %passwd% ^
    /t http://timestamp.digicert.com ^
    %aplicationpath%

```

## コントリビューション

コントリビューションは大歓迎です！機能の改善やバグ修正については、プルリクエストを送るか、イシューを作成してください。

## ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細については、LICENSEファイルをご覧ください。
