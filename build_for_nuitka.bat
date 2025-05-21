REM 実行パスのディレクトリ取得
set TMP_BAT_DIR=%~dp0
set BAT_DIR=%TMP_BAT_DIR:~0,-1%

REM パスの設定 適当に変えてください
SET PATH=%PATH%;%USERPROFILE%\AppData\Roaming\mingw64\bin
SET PATH=%PATH%;%USERPROFILE%\AppData\Roaming\Python\Python312\Scripts
SET PATH=%PATH%;C:\Program Files\Python312\Scripts

REM 出力先ディレクトリ設定
SET DST_DIR=%BAT_DIR%\binary

REM 出力先ディレクトリ削除
rmdir /S /Q %DST_DIR%
REM 出力先ディレクトリ生成
mkdir %DST_DIR%

nuitka ^
    --onefile ^
    --standalone ^
    --mingw64 ^
    --follow-imports ^
    --output-dir=%DST_DIR% ^
    --output-filename=python_package_downloader.exe ^
    --windows-product-name=python_package_downloader ^
    --windows-file-description="python_package_downloader" ^
    --windows-product-version=0.0.0.1 ^
    --windows-company-name="fangface" ^
    --enable-plugins=tk-inter ^
    --noinclude-pytest-mode=nofollow ^
    --noinclude-unittest-mode=nofollow ^
    --jobs=4 ^
    %BAT_DIR%\python_package_downloader.py

pause
