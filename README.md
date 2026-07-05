# Git Clone Tool

一个带代理支持的 Git 克隆 GUI 工具，适用于需要通过 VPN/代理访问 GitHub 的场景。

## 背景

在中国大陆使用终端命令行克隆 GitHub 仓库时，经常遇到网络不稳定需要走 VPN 的情况。但终端默认不走系统 VPN，每次都需要手动执行：

```bash
git config --global http.https://github.com.proxy socks5://127.0.0.1:10808
git clone https://github.com/xxx/xxx.git
git config --global --unset http.https://github.com.proxy
```

步骤繁琐且容易忘记还原代理配置，导致 VPN 关闭后无法正常克隆。本工具将这些操作封装为图形化界面，自动完成 **设置代理 → 克隆 → 还原代理** 的全流程。

## 功能

- 🔗 输入 Git 仓库地址进行克隆
- 🔌 可选配置代理端口和协议（SOCKS5 / HTTP）
- 📁 选择本地保存目录，自动记住上次路径
- 📋 实时显示克隆进度和日志
- 📜 历史记录：记录每次克隆的地址、代理、时间、成功/失败状态，点击可回填表单
- 🛡️ 无论克隆成功与否，代理配置自动还原，不留残留

## 运行方式

### 方式一：直接下载 exe（推荐）

从 `dist/` 目录下载 `Git_Clone_Tool.exe`，双击即可运行，无需安装 Python。

### 方式二：运行 Python 脚本

```bash
python git_clone_tool.py
```

需要 Python 3.6+，`tkinter` 为 Python 标准库，无需额外安装。

### 方式三：自行打包

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=clone_icon.ico --name "Git_Clone_Tool" git_clone_tool.py
```

打包后的 exe 在 `dist/` 目录下。

## 使用说明

1. 填入 Git 仓库地址（如 `https://github.com/xxx/xxx.git`）
2. 如需走代理，填入端口号（如 `10808`），选择协议（SOCKS5 / HTTP）；不留空则直连
3. 选择保存目录（默认记住上次选择）
4. 点击「开始克隆」
5. 日志区实时显示进度，完成后历史记录自动更新

历史记录存储在程序同目录的 `clone_history.json` 文件中。

## Vibe Coding

本项目由 [Claude Code](https://claude.ai/code) 辅助开发，通过自然语言对话完成从需求分析、UI 设计到代码实现的全流程。没有手写一行代码，全靠"聊天写代码" —— 这就是 Vibe Coding。

🫡 致敬 [Vibe Coding](https://x.com/karpathy/status/1887422622618787911) 精神。

