---
name: cryptography-rust-dll-win7
description: cryptography>=3.4 的 Rust _rust.pyd 在 Win7 上 DLL load failed + 缺少 VC++/UCRT 运行时
date: 2026-06-08
status: resolved
---

# cryptography _rust.pyd + 运行时 DLL 缺失（Win7 离线）

## 环境

- 目标系统：Windows 7 SP1（离线，无 VC++ Redist，无 KB2999226）
- 开发机：Windows 11，Python 3.8.10
- 打包工具：PyInstaller 4.10 --onefile

## 问题 1：_rust.pyd DLL 加载失败

### 报错
```
ImportError: DLL load failed while importing _rust: 找不到指定的程序。
```
调用链：`main.py` → `pdfplumber` → `pdfminer` → `cryptography` → `_rust.pyd`

### 根因
`cryptography>=3.4.0` 用 Rust 重写了核心模块，开发机安装的 `47.0.0` 打包后 `_rust.pyd` 在 Win7 上加载时找不到对应 Windows API。

### 修复
锁定 `cryptography==3.3.2`（最后一个纯 C 扩展版本，无 Rust）。

## 问题 2：缺少 VC++ 运行时 / Universal CRT DLL

### 根因
Win7 未安装 VC++ 2015-2022 Redistributable 和 KB2999226（Universal CRT）。

### 修复
将 24 个运行时 DLL 打包进 EXE：

| 类别 | DLL |
|---|---|
| UCRT 转发器 ×15 | api-ms-win-crt-conio/convert/environment/filesystem/heap/locale/math/multibyte/private/process/runtime/stdio/string/time/utility-l1-1-0.dll |
| UCRT 核心 | ucrtbase.dll |
| VC++ 运行时 | vcruntime140.dll, vcruntime140_1.dll, msvcp140.dll, msvcp140_1.dll, msvcp140_2.dll, msvcp140_codecvt_ids.dll, concrt140.dll, vccorlib140.dll |

DLL 来源：`EpicGamesLauncher\Engine\Binaries\Win64\`，存放在 `src/pdf_extractor/redist/`，通过 `.spec` 的 `binaries` 参数自动打包。

## 涉及文件

| 文件 | 修改 |
|---|---|
| `src/pdf_extractor/requirements.txt` | 钉 `cryptography==3.3.2`，加 `six==1.17.0` |
| `src/pdf_extractor/PDF信息提取工具.spec` | `hiddenimports` + `binaries`（redist DLL）+ `datas` |
| `src/pdf_extractor/redist/` | 24 个运行时 DLL（新增目录） |
| `src/pdf_extractor/app_utils.py` | `get_exe_dir()` / `get_app_dir()` 路径分离 |
| `src/pdf_extractor/main.py` | 样式表加载路径修复 |
| `src/pdf_extractor/main_window.py` | 配置文件加载路径修复 |
| `src/pdf_extractor/session_manager.py` | 使用 `get_exe_dir()` |
| `src/pdf_extractor/config_manager.py` | `get_default()` 双路径查找 |
| `src/pdf_extractor/build.bat` | 改用 .spec 打包 |
