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
- pip：内置于 Python 3.8

## 报错

```
ValueError: check_hostname requires server_hostname
```

所有 `pip install` 命令均失败，包括 `pip install --upgrade pip`。

## 尝试过的无效方案

| 方案 | 结果 |
|---|---|
| `--trusted-host` | 同报错 |
| `--proxy ""` | 同报错 |
| 环境变量 `HTTPS_PROXY`/`HTTP_PROXY` 均为空 | — |
| `netsh winhttp show proxy` 显示直接访问 | — |

## 根因

pip 的 vendored urllib3 即使无代理配置也进入了 `_connect_tls_proxy` 分支，`ssl_context.wrap_socket()` 在无 `server_hostname` 时抛出异常。pip/urllib3 版本兼容性 bug。

## 绕过方案

curl 下载 wheel → 本地 pip install：

```bash
curl -s "https://pypi.org/pypi/<package>/<version>/json" |
  python -c "import sys,json; d=json.load(sys.stdin);
    [print(u['url']) for u in d['urls'] if 'win_amd64' in u['url']]"

curl -L -o "<package>.whl" "<url>"
pip install --no-deps "<package>.whl"
```
