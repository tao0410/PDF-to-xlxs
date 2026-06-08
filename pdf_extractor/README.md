# PDF信息提取与Excel生成工具

一款轻量级、纯本地运行的 Windows 桌面应用，从格式统一的 PDF 文档中按坐标提取结构化信息，经确认后生成 Excel 汇总表。

## 运行环境

- Windows 7 SP1 及以上（32/64 位）
- 开发环境：Python 3.8.10

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python main.py
```

### 3. 打包为 exe

```bash
build.bat
```

或手动执行：

```bash
pyinstaller --onefile --windowed --name=PDF信息提取工具 main.py
```

将 `default.cfg` 复制到 `dist` 目录，与 exe 放在同一文件夹。

## 使用流程

1. **配置提取规则**：点击「配置提取规则」，添加字段；使用「选择PDF预览并框选」在 PDF 上拖拽框选区域，自动填充坐标。
2. **选择 PDF 文件**：点击「打开」或拖拽 PDF 到主界面。
3. **开始处理**：
   - 仅 1 个文件：提取后弹出单文件确认窗口
   - 2 个及以上：批量提取后弹出统一确认窗口
4. **编辑确认**：检查并修正提取结果，点击确认。
5. **生成 Excel**：全部文件处理完成后，点击「生成Excel」，按编号升序导出。

## 配置文件

- `default.cfg`：默认提取规则（JSON 格式）
- `workspace.json`：自动保存的工作区状态（文件列表、已确认数据）
- `logs/`：运行日志，按日轮转，保留 30 天

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开 PDF 文件 |
| Ctrl+S | 保存当前配置 |
| Delete | 删除总表中选中行 |

## 目录结构

```
pdf_extractor/
├── main.py                  # 程序入口
├── main_window.py           # 主窗口
├── config_dialog.py         # 规则配置
├── pdf_preview_dialog.py    # PDF 预览与框选
├── single_confirm_dialog.py # 单文件确认
├── batch_confirm_dialog.py  # 批量确认
├── pdf_extractor.py         # PDF 提取
├── excel_generator.py       # Excel 生成
├── config_manager.py        # 配置管理
├── session_manager.py       # 会话持久化
├── extraction_worker.py     # 后台提取线程
├── default.cfg              # 默认配置
└── resources/styles.qss     # 界面样式
```

## 常见问题

**Q: 提取内容为空？**  
检查框选坐标是否与 PDF 页面匹配，可在配置窗口重新框选。

**Q: 无法生成 Excel？**  
确认所有文件均已「已确认」或「已跳过」；检查目标文件是否被 Excel 占用。

**Q: 关闭后数据会丢失吗？**  
不会。工作区状态自动保存到 `workspace.json`，下次启动自动恢复。
