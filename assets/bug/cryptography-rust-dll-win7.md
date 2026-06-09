---
name: cryptography-rust-dll-win7
description: cryptography>=3.4 的 Rust _rust.pyd 在 Win7 上报 DLL load failed，需锁定 3.3.2
date: 2026-06-08
status: resolved
---

# cryptography _rust.pyd DLL 加载失败（Win7 离线）

## 环境

- 目标系统：Windows 7 SP1（离线）
- 开发机：Windows 11，Python 3.8.10，cryptography==47.0.0
- 打包工具：PyInstaller 4.10 --onefile

## 完整报错

```
Traceback (most recent call last):
  File "main.py", line 10, in <module>
    ...
  File "pdfplumber/__init__.py", line 14, in <module>
  File "pdfplumber/pdf.py", line 8, in <module>
  File "pdfminer/layout.py", line 20, in <module>
  File "pdfminer/pdfinterp.py", line 12, in <module>
  File "pdfminer/pdfdevice.py", line 17, in <module>
  File "pdfminer/pdfpage.py", line 7, in <module>
  File "pdfminer/pdfdocument.py", line 23, in <module>
  File "cryptography/hazmat/primitives/ciphers/__init__.py", line 11, in <module>
  File "cryptography/hazmat/primitives/ciphers/base.py", line 10, in <module>
ImportError: DLL load failed while importing _rust: 找不到指定的程序。
```

## 调用链

```
main.py
  → main_window.py
    → extraction_worker.py
      → pdf_extractor.py
        → pdfplumber
          → pdfminer
            → cryptography
              → _rust.pyd  ←❌ Win7 不兼容
```

## 根因

- `cryptography` 从 **3.4.0**（2021 年 2 月）起用 Rust 重写了核心加密模块
- `_rust.pyd` 编译时链接了 Win7 不支持的 Windows API
- 开发机的 `cryptography==47.0.0` 打包进 EXE 后，在 Win7 加载时找不到对应 API 入口点

## 解决方案

锁定 `cryptography==3.3.2`（最后一个纯 C 扩展版本，无 Rust 依赖）。

## 涉及文件

| 文件 | 修改 |
|---|---|
| `src/pdf_extractor/requirements.txt` | 新增 `cryptography==3.3.2` |
| `src/pdf_extractor/PDF信息提取工具.spec` | `hiddenimports` 补齐 cryptography C 绑定模块 |

## 修复步骤

```bash
# pip 有 SSL bug 时用 curl 下载 wheel 本地安装
curl -L -o "cryptography-3.3.2.whl" "<pypi-url>"
pip install --no-deps "cryptography-3.3.2.whl"

# 验证
pip show cryptography   # 应显示 3.3.2

# 重新打包
build.bat
```

## 关联

- [[pip-ssl-check-hostname-error]] — 修复过程中发现 pip 无法连接 PyPI
