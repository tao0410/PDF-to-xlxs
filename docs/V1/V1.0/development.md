# PDF信息提取与Excel生成工具 最终技术文档
## 1. 技术概述
### 1.1 文档目的
本文档明确PDF信息提取与Excel生成工具的技术架构、模块划分、组件选型和实现规范，为Cursor代码生成提供**精确、可执行**的技术指导。所有功能均使用成熟开源组件实现，禁止手动开发重复功能，确保生成的代码完全兼容Windows 7离线环境。

### 1.2 核心技术原则
1. **零造轮子原则**：所有核心功能必须使用经过验证的开源库实现，禁止手动开发PDF解析、Excel生成、GUI控件等基础功能
2. **纯本地运行原则**：不引入任何需要网络连接的依赖，不调用任何云服务或API
3. **Windows 7优先原则**：所有组件版本选择以支持Windows 7 SP1为唯一标准
4. **最小依赖原则**：只引入必要的依赖库，严格控制最终exe文件大小
5. **模块化原则**：代码按功能划分为独立模块，模块间通过明确接口交互

## 2. 系统架构
### 2.1 整体架构
采用**单层桌面应用架构**，所有功能模块在本地进程内运行，无客户端/服务器分离。

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层 (PyQt5)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   主窗口    │  │  确认窗口   │  │  配置/预览窗口      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    业务逻辑层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ PDF提取器   │  │ Excel生成器 │  │  配置管理器        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    数据存储层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ JSON配置文件│  │ 日志文件    │  │  临时数据          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向
1. 用户通过主界面选择PDF文件和加载配置
2. 配置管理器读取JSON格式的提取规则
3. PDF提取器根据规则从PDF文件中提取结构化数据
4. 提取结果通过确认窗口展示给用户进行编辑
5. 确认后的数据传递给Excel生成器
6. Excel生成器按编号排序后生成.xlsx文件
7. 所有操作和错误信息通过Python标准日志库记录到本地文件

## 3. 技术选型（**必须严格遵守版本号**）
| 技术领域 | 组件名称 | 精确版本号 | 选择理由 | 禁止替代方案 |
|---------|---------|------------|---------|-------------|
| 开发语言 | Python | 3.8.10 | 最后一个官方支持Windows 7的Python版本 | Python 3.9+ |
| GUI框架 | PyQt5 | 5.15.2 | 最后一个官方支持Windows 7的PyQt5版本，提供完整Windows原生控件 | PyQt6、PySide6、Tkinter、Electron |
| PDF内容提取 | pdfplumber | 0.9.0 | 支持精确坐标定位提取，文本提取准确率最高，完全离线运行 | PyPDF2、pdfminer |
| PDF渲染与框选 | PyMuPDF (fitz) | 1.20.2 | 最后一个支持Python 3.8和Windows 7的版本，渲染速度快，坐标系统与pdfplumber完全一致 | 任何其他PDF渲染库 |
| Excel生成 | openpyxl | 3.0.10 | 支持生成.xlsx格式文件，无需安装Microsoft Excel | xlwt、xlsxwriter |
| 配置文件 | JSON | - | Python原生支持，无需额外依赖，易于读写 | XML、YAML、INI |
| 日志系统 | logging | - | Python标准库，功能完善，无需额外依赖 | 任何第三方日志库 |
| 打包工具 | PyInstaller | 4.10 | 最后一个官方支持Windows 7的版本，可打包为单个exe文件 | cx_Freeze、py2exe |
| 压缩工具 | UPX | 4.0.2 | 可执行文件压缩工具，兼容Windows 7 | 任何其他压缩工具 |

## 4. 模块设计（**Cursor必须严格按照此划分生成代码**）
### 4.1 模块划分
共分为9个独立模块，每个模块对应一个.py文件，模块间只能通过公开接口交互。

| 模块文件名 | 模块职责 | 依赖模块 |
|-----------|---------|---------|
| main.py | 应用程序入口，初始化Qt环境，创建主窗口 | main_window.py |
| main_window.py | 主界面逻辑，文件选择、处理控制、总内容编辑 | pdf_extractor.py, excel_generator.py, config_dialog.py, single_confirm_dialog.py, batch_confirm_dialog.py |
| config_dialog.py | 提取规则配置窗口，规则的增删改查和保存加载 | config_manager.py, pdf_preview_dialog.py |
| pdf_preview_dialog.py | PDF预览与可视化框选窗口，坐标提取 | 无 |
| single_confirm_dialog.py | 单文件模式下的内容确认窗口 | 无 |
| batch_confirm_dialog.py | 多文件模式下的批量确认窗口 | 无 |
| pdf_extractor.py | 封装pdfplumber，提供统一的PDF内容提取接口 | config_manager.py |
| excel_generator.py | 封装openpyxl，提供统一的Excel生成接口 | 无 |
| config_manager.py | 配置文件的读取和写入，JSON格式处理 | 无 |

### 4.2 模块接口规范
所有模块必须实现以下公开接口，接口参数和返回值类型必须严格匹配。

#### 4.2.1 PdfExtractor接口
```python
class PdfExtractor:
    def __init__(self, config: dict):
        """初始化PDF提取器
        Args:
            config: 提取规则配置字典，格式由ConfigManager定义
        """
    
    def extract_single(self, pdf_path: str) -> dict:
        """提取单个PDF文件内容
        Args:
            pdf_path: PDF文件绝对路径
        Returns:
            提取结果字典，包含所有配置字段的值和提取状态
        """
    
    def extract_batch(self, pdf_paths: list[str]) -> list[dict]:
        """批量提取多个PDF文件内容
        Args:
            pdf_paths: PDF文件绝对路径列表
        Returns:
            提取结果列表，每个元素对应一个PDF文件的提取结果
        """
```

#### 4.2.2 ExcelGenerator接口
```python
class ExcelGenerator:
    def __init__(self, columns: list[str]):
        """初始化Excel生成器
        Args:
            columns: Excel列标题列表，包含"来源文件"列
        """
    
    def generate(self, data: list[dict], output_path: str, sort_key: str = "编号") -> bool:
        """生成Excel文件
        Args:
            data: 要写入的数据列表
            output_path: 输出文件绝对路径
            sort_key: 排序字段名称，默认按"编号"升序
        Returns:
            生成成功返回True，失败返回False
        """
```

#### 4.2.3 ConfigManager接口
```python
class ConfigManager:
    @staticmethod
    def save(config: dict, file_path: str) -> bool:
        """保存配置到JSON文件
        Args:
            config: 配置字典
            file_path: 配置文件绝对路径
        Returns:
            保存成功返回True，失败返回False
        """
    
    @staticmethod
    def load(file_path: str) -> dict:
        """从JSON文件加载配置
        Args:
            file_path: 配置文件绝对路径
        Returns:
            配置字典，加载失败返回默认配置
        """
    
    @staticmethod
    def get_default() -> dict:
        """获取默认配置
        Returns:
            默认配置字典，包含编号、名称、日期、金额四个字段
        """
```

## 5. 关键功能实现规范（**Cursor必须使用指定组件实现，禁止手动开发**）
### 5.1 PDF可视化框选功能
- **必须使用PyQt5.QtWidgets.QRubberBand组件**实现拖拽框选效果，禁止手动绘制矩形
- **必须使用PyMuPDF(fitz)**渲染PDF页面，禁止使用任何其他渲染方式
- **必须统一使用PDF原生坐标系统**（原点在页面左下角），确保框选坐标与pdfplumber提取坐标完全一致
- 坐标转换逻辑必须在pdf_preview_dialog.py模块中实现，禁止在其他模块中进行坐标转换

### 5.2 多线程处理功能
- **必须使用PyQt5.QtCore.QThread**实现PDF提取的后台线程，禁止使用threading模块
- 必须通过pyqtSignal实现线程间通信，禁止使用全局变量传递数据
- 提取进度和当前文件名必须通过信号实时更新到主界面
- 必须支持取消操作，取消后线程必须安全退出

### 5.3 表格编辑功能
- **必须使用PyQt5.QtWidgets.QTableWidget**实现所有表格功能，禁止手动开发表格控件
- 必须使用QTableWidget的原生编辑功能，禁止手动实现单元格编辑
- 必须使用QTableWidget的原生选择功能，支持单行和多行选择
- 异常单元格必须使用setBackground()方法设置背景色，禁止手动绘制

### 5.4 异常处理功能
- 所有可能抛出异常的操作必须包含try-except块
- 所有异常必须通过PyQt5.QtWidgets.QMessageBox显示友好的中文提示
- 所有异常必须通过Python标准logging模块记录到日志文件
- 单个PDF提取失败不能影响其他PDF的处理

### 5.5 配置文件功能
- **必须使用Python标准json模块**处理配置文件，禁止使用任何第三方配置库
- 配置文件必须使用UTF-8编码，确保中文正常显示
- 配置文件格式必须为标准JSON格式，禁止自定义格式
- 必须提供默认配置，当配置文件不存在或损坏时自动加载默认配置

## 6. 开发环境搭建
### 6.1 系统要求
- 操作系统：Windows 7 SP1 64位（开发和测试环境）
- 内存：4GB以上
- 磁盘空间：1GB以上可用空间

### 6.2 环境安装命令
**必须严格按照以下顺序执行，确保版本正确**：
```bash
# 1. 安装Python 3.8.10 64位（从官网下载）
# 2. 升级pip到最新版本
python -m pip install --upgrade pip

# 3. 安装所有依赖库（精确版本号）
pip install PyQt5==5.15.2
pip install pdfplumber==0.9.0
pip install PyMuPDF==1.20.2
pip install openpyxl==3.0.10
pip install pyinstaller==4.10
```

### 6.3 项目目录结构
**Cursor必须严格按照此结构生成文件**：
```
pdf_extractor/
├── main.py                  # 主程序入口
├── main_window.py           # 主窗口模块
├── config_dialog.py         # 提取规则配置窗口
├── pdf_preview_dialog.py    # PDF预览与框选窗口
├── single_confirm_dialog.py # 单个文件确认窗口
├── batch_confirm_dialog.py  # 批量确认窗口
├── pdf_extractor.py         # PDF提取器模块
├── excel_generator.py       # Excel生成器模块
├── config_manager.py        # 配置管理器模块
├── resources/               # 资源文件目录
│   └── app.ico              # 应用程序图标（可选）
├── default.cfg              # 默认配置文件（JSON格式）
└── README.md                # 使用说明文档
```

## 7. 打包与部署规范
### 7.1 打包命令
**必须使用以下命令打包，确保生成单个exe文件且兼容Windows 7**：
```bash
pyinstaller --onefile --windowed --icon=resources/app.ico --name=PDF信息提取工具 main.py
```

**打包参数说明**：
- `--onefile`：打包为单个exe文件
- `--windowed`：不显示控制台窗口
- `--icon`：指定应用程序图标
- `--name`：指定生成的exe文件名

### 7.2 文件大小优化
- 必须使用UPX 4.0.2压缩可执行文件，可将文件大小减少约30%
- 打包时添加`--upx-dir`参数指定UPX路径：
  ```bash
  pyinstaller --onefile --windowed --icon=resources/app.ico --name=PDF信息提取工具 --upx-dir=path/to/upx main.py
  ```

### 7.3 部署要求
- 生成的exe文件可以直接在Windows 7 SP1及以上系统上运行
- 无需安装任何额外的运行环境
- 必须将default.cfg配置文件与exe文件放在同一目录下
- 应用程序会在运行目录下自动创建logs文件夹存储日志文件

## 8. 测试要求
### 8.1 功能测试点
- 单文件和多文件两种处理模式
- PDF可视化框选和坐标自动填充功能
- 提取规则的保存和加载功能
- 表格编辑和批量删除功能
- Excel生成和按编号排序功能
- 所有异常情况的处理

### 8.2 兼容性测试点
- Windows 7 32位系统
- Windows 7 64位系统
- Windows 10/11系统（向下兼容）
- PDF 1.4至1.7版本
- Microsoft Excel 2007至2019版本

## 9. Cursor代码生成指导
### 9.1 生成顺序
**必须按照以下顺序生成代码，确保依赖关系正确**：
1. config_manager.py（配置管理器）
2. pdf_extractor.py（PDF提取器）
3. excel_generator.py（Excel生成器）
4. pdf_preview_dialog.py（PDF预览与框选窗口）
5. config_dialog.py（提取规则配置窗口）
6. single_confirm_dialog.py（单个文件确认窗口）
7. batch_confirm_dialog.py（批量确认窗口）
8. main_window.py（主窗口）
9. main.py（主程序入口）
10. default.cfg（默认配置文件）
11. README.md（使用说明文档）

### 9.2 生成原则
1. 严格按照本文档中的模块划分和接口定义生成代码
2. 所有功能必须使用本文档指定的组件和库实现，禁止引入任何未提及的依赖
3. 所有用户可见的文本必须使用中文
4. 所有异常必须被捕获并显示友好的错误提示
5. 代码必须添加必要的中文注释，说明函数和类的用途
6. 禁止生成任何与需求无关的功能

### 9.3 绝对禁止事项
1. 禁止引入任何需要网络连接的库或功能
2. 禁止使用本文档中未指定的任何组件或库
3. 禁止修改本文档中指定的组件版本号
4. 禁止手动开发任何已有开源组件可以实现的功能
5. 禁止生成任何需要安装额外运行环境的代码
