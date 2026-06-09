---
name: pip-ssl-check-hostname-error
description: pip 的 vendored urllib3 报 ValueError: check_hostname requires server_hostname，无法连接 PyPI
date: 2026-06-08
status: workaround
---

# pip SSL `check_hostname requires server_hostname` 错误

## 环境

- OS：Windows 11（开发机）
- Python：3.8.10
- pip：内置于 Python 3.8，vendored urllib3

## 完整报错

```
ERROR: Exception:
Traceback (most recent call last):
  File "...\pip\_internal\cli\base_command.py", line 180, in _main
    ...
  File "...\pip\_vendor\urllib3\connection.py", line 500, in _connect_tls_proxy
    return ssl_wrap_socket(...)
  File "...\pip\_vendor\urllib3\util\ssl_.py", line 474, in _ssl_wrap_socket_impl
    return ssl_context.wrap_socket(sock)
  File "...\ssl.py", line 997, in _create
    raise ValueError("check_hostname requires server_hostname")
ValueError: check_hostname requires server_hostname
```

## 影响范围

所有 `pip install` 命令均失败，包括 `pip install --upgrade pip` 本身。

## 尝试过的无效方案

| 方案 | 结果 |
|---|---|
| `--trusted-host pypi.org --trusted-host files.pythonhosted.org` | 同报错 |
| `--proxy ""` | 同报错 |
| 检查环境变量 `HTTPS_PROXY`/`HTTP_PROXY` | 均为空 |
| `netsh winhttp show proxy` | 直接访问（无代理） |
| pip config 各级均无 proxy 配置 | — |

## 根因

pip 的 vendored urllib3 在 `_connect_tls_proxy` 方法中，即使没有配置任何代理，仍进入了 TLS 代理连接分支，导致 `ssl_context.wrap_socket()` 在无 `server_hostname` 的情况下调用 `check_hostname`，触发 Python `ssl` 模块的参数校验异常。

这是 pip/urllib3 的已知兼容性 bug，与系统代理配置无关。

## 绕过方案

用 curl 直接下载 wheel 文件，然后 `pip install` 本地文件：

```bash
# 1. 通过 PyPI JSON API 获取准确下载 URL
curl -s "https://pypi.org/pypi/<package>/<version>/json" |
  python -c "import sys,json; d=json.load(sys.stdin);
    [print(u['url']) for u in d['urls'] if 'win_amd64' in u['url']]"

# 2. curl 下载 wheel
curl -L -o "<package>.whl" "<url>"

# 3. 本地安装
pip install --no-deps "<package>.whl"
```

## 关联

此问题在修复 [[pdf-extractor-win7-packaging-fix]] 过程中触发——需要安装 `cryptography==3.3.2` 时发现 pip 无法连接 PyPI。
