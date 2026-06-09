# 📁 工作区结构 (Workspace)

## 🌳 目录树

```
workspace/
├── WORKSPACE.md              ← 你在这
├── docs/                     # 📄 产品文档 (PRD / UI / 开发 / 手册 / 变更日志)
├── assets/
│   ├── design/               # 🎨 设计稿、原型、交互稿
│   ├── bug/                  # 🐛 Bug 截图、录屏、复现记录
│   └── reference/            # 📚 竞品截图、图标素材、视觉参考
├── notes/                    # 📝 学习笔记 (新知识、踩坑、调研)
├── src/                      # 💻 独立代码模块
│   └── pdf_extractor/        #   PDF 信息提取工具
└── .cursor/                  # Cursor IDE 配置
```

## 🗂️ 用途一览

| 放什么 | 放哪里 |
|--------|--------|
| 产品需求、设计说明、用户手册 | `docs/` |
| 设计稿、图标、视觉素材 | `assets/design/` |
| Bug 截图/录屏 | `assets/bug/` |
| 参考图、竞品素材 | `assets/reference/` |
| 学习笔记、技术调研 | `notes/` |
| 独立子项目代码 | `src/` 或根目录独立文件夹 |

## 🚀 快速开始

```bash
# 新建学习笔记
touch notes/$(date +%F)-主题.md
```
