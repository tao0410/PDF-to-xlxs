# -*- mode: python ; coding: utf-8 -*-

import glob
import os
import sys

block_cipher = None

# 确定 PyQt5 插件目录（用于平台插件）
import PyQt5

_pyqt5_dir = os.path.dirname(PyQt5.__file__)
_platform_plugin_dir = os.path.join(_pyqt5_dir, "Qt5", "plugins")

# 收集 Win7 运行时 DLL（VC++ Redist + Universal CRT）
_redist_dir = os.path.join(SPECPATH, "redist")
_bundled_dlls = []
if os.path.isdir(_redist_dir):
    for _dll in glob.glob(os.path.join(_redist_dir, "*.dll")):
        _bundled_dlls.append((_dll, "."))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_bundled_dlls,
    datas=[
        ('default.cfg', '.'),
        ('resources/styles.qss', 'resources'),
        ('resources/app_icon.ico', 'resources'),
    ],
    hiddenimports=[
        # PyQt5 核心模块
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # pdfplumber 隐式依赖
        'pdfminer',
        'pdfminer.pdfparser',
        'pdfminer.pdftypes',
        'pdfminer.pdfdocument',
        'pdfminer.pdfpage',
        'pdfminer.pdfinterp',
        'pdfminer.converter',
        'pdfminer.layout',
        'pdfminer.cmapdb',
        'pdfminer.encodingdb',
        'pdfminer.glyphlist',
        'pdfminer.utils',
        'pdfplumber',
        # cryptography (非 Rust 版本 3.3.2 — C 扩展绑定)
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.bindings._openssl',
        'cryptography.hazmat.bindings._padding',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.ciphers',
        'cryptography.hazmat.primitives.ciphers.algorithms',
        'cryptography.hazmat.primitives.ciphers.modes',
        'cryptography.hazmat.primitives.padding',
        # PyMuPDF
        'fitz',
        # openpyxl
        'openpyxl',
        # 标准库隐式模块
        'json',
        'logging',
        're',
        'os',
        'sys',
        'datetime',
        'collections',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型包以减小体积
        'tkinter',
        'unittest',
        'test',
        'pydoc',
        'distutils',
        'setuptools',
        'pip',
        'matplotlib',
        'numpy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDF信息提取工具_v2.1',
    icon='resources/app_icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
