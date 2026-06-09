---
name: pdf-extractor-win7-packaging-fix
description: Win7 离线运行 EXE 报错的打包配置修复 — 8 个文件的修改汇总（含 cryptography Rust DLL 根因）
metadata:
  type: project
---

# PDF 提取工具 Win7 兼容性修复（2026-06-08）

## 背景

在 Win7 离线环境下运行 `PDF信息提取工具.exe` 时出现报错，两轮诊断和修复：

**第一轮**：修复打包配置缺陷（资源未内嵌、路径解析不支持 `--onefile`、缺少隐式导入）。
**第二轮**：用户给出具体报错 → `ImportError: DLL load failed while importing _rust` → 定位到 `cryptography` 的 Rust 组件在 Win7 上不兼容。

## 根因分析

### 实际报错
```
ImportError: DLL load failed while importing _rust: 找不到指定的程序。
```
调用链：`main.py` → `main_window.py` → `extraction_worker.py` → `pdf_extractor.py` → `pdfplumber` → `pdfminer` → `cryptography` → `_rust.pyd`

### 原因
- 开发机安装了 `cryptography==47.0.0`（2026 年最新版），其 Rust 编译的 `_rust.pyd` 链接了 Win7 不支持的 Windows API
- `cryptography>=3.4.0`（2021 年起）引入了 Rust 重写的核心模块，`_rust.pyd` 在旧版 Windows 上直接无法加载
- `pdfplumber` → `pdfminer` 依赖 `cryptography`，所以整个依赖链在 Win7 上崩溃

### 修复方案
- 钉 `cryptography==3.3.2`，这是**最后一个纯 C 扩展版本**（无 Rust），完全兼容 Win7 SP1
- `pdfminer.six` 要求 `cryptography>=2.1`，3.3.2 满足兼容性要求
- 仅在处理加密 PDF 时需要 cryptography，未加密 PDF 不受影响

## 修改文件清单（共 8 个文件）

### 1. [app_utils.py](src/pdf_extractor/app_utils.py)
- 新增 `get_exe_dir()` 函数：始终返回 EXE 所在目录（用于可写文件：`logs/`、`workspace.json`、用户覆盖的 `default.cfg`）
- 修正 `get_app_dir()`：frozen 模式下返回 `sys._MEIPASS`（PyInstaller 资源解压临时目录），用于读取内置只读资源
- `setup_logging()`：改用 `get_exe_dir()`，确保日志写入 EXE 目录而非临时目录

### 2. [main.py](src/pdf_extractor/main.py)
- 导入 `get_exe_dir`
- 样式表加载：优先 `_MEIPASS` 内置 `styles.qss`，回退 EXE 目录外置覆盖

### 3. [main_window.py](src/pdf_extractor/main_window.py)
- 导入 `get_exe_dir`
- 配置文件加载：优先 EXE 目录下用户覆盖的 `default.cfg`，回退 `_MEIPASS` 内置默认

### 4. [session_manager.py](src/pdf_extractor/session_manager.py)
- 改用 `get_exe_dir()` 确定 `workspace.json` 路径（`_MEIPASS` 为只读临时目录，不可写）

### 5. [config_manager.py](src/pdf_extractor/config_manager.py)
- 导入 `get_exe_dir`
- `get_default()`：遍历 `(get_exe_dir(), get_app_dir())` 两个位置查找 `default.cfg`

### 6. [PDF信息提取工具.spec](src/pdf_extractor/PDF信息提取工具.spec)
- `datas`：添加 `default.cfg` 和 `resources/styles.qss` 打包进 EXE
- `hiddenimports`：添加 PyQt5 子模块、pdfplumber/pdfminer 隐式依赖、**cryptography C 绑定模块**（`_openssl`/`_padding`/`_constant_time`）、PyMuPDF (fitz)、openpyxl 等
- `excludes`：排除 tkinter/unittest/pip/numpy 等减小体积

### 7. [build.bat](src/pdf_extractor/build.bat)
- 改用 `.spec` 文件打包（`py -m PyInstaller --clean "PDF信息提取工具.spec"`）
- 自动复制 `default.cfg` 和 `resources/styles.qss` 到 `dist/`
- 新增 Win7 部署提示（VC++ Redist、KB2999226）

### 8. [requirements.txt](src/pdf_extractor/requirements.txt) ← 第二轮新增
- 新增 `cryptography==3.3.2`，锁定最后一个支持 Win7 的纯 C 扩展版本

## Win7 常见报错速查

| 报错 | 根因 | 方案 |
|---|---|---|
| `DLL load failed while importing _rust` | cryptography≥3.4 的 Rust _rust.pyd 不兼容 Win7 | 钉 cryptography==3.3.2 重新打包 |
| 缺少 `api-ms-win-crt-*.dll` | 缺少 Universal CRT | 安装 KB2999226 |
| 缺少 `VCRUNTIME140.dll` / `MSVCP140.dll` | 缺少 VC++ 2015-2022 Redist | 安装 vc_redist |
| "no Qt platform plugin could be initialized" | Qt 平台插件未打包 | 已通过 hiddenimports 修复，重新打包 |
| 双击无反应 | 程序启动崩溃 | cmd 运行查看输出；检查 logs/app.log |

**Why:** `--onefile` 打包后，PyInstaller 将资源解压到 `_MEIPASS` 临时目录，但原代码的 `get_app_dir()` 一直返回 EXE 目录，导致内置资源无法读取；同时可写文件（日志、会话）不应写入临时目录。`cryptography>=3.4` 引入的 Rust `_rust.pyd` 在编译时链接了 Win7 不支持的 API，导致整个 pdfplumber→pdfminer→cryptography 依赖链加载失败。

**How to apply:**
1. `pip install -r requirements.txt` 安装加密版本
2. 运行 `build.bat` 重新打包
3. 将 `dist/` 目录完整拷贝到 Win7 目标机器
4. Win7 目标机器需预装 VC++ 2015-2022 Redistributable 和 KB2999226（Universal CRT）
