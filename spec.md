# Git Clone Tool - 设计规格

## 背景

在中国大陆使用 Git 克隆 GitHub 仓库时，经常需要走 VPN/代理。但终端命令行默认不走 VPN，
每次需要手动配置 `git config http.proxy`，克隆完还需改回来，操作繁琐且容易遗忘。

## 功能概述

一个 Windows 本地 GUI 工具，双击 exe 即可运行。用户输入 Git 仓库地址和（可选的）代理配置，
程序自动完成代理设置 → 克隆 → 代理还原的全流程。

## 技术栈

- Python 3 + tkinter（标准库，无需安装额外依赖）
- PyInstaller 打包为单文件 exe

## UI 布局

- 左侧：表单区（仓库地址、代理端口、协议选择、保存目录）+ 日志输出
- 右侧：历史记录列表

## 核心逻辑

1. 用户在表单输入仓库地址，可选填代理端口和协议
2. 未填端口 → 直接 git clone
3. 填了端口 → 先设置 `git config --global http.https://github.com.proxy {protocol}://127.0.0.1:{port}`
   → 执行 git clone → 无论成功失败，立即 `git config --global --unset http.https://github.com.proxy`
4. 克隆过程实时输出日志
5. 记录每次操作到历史（地址、端口、协议、目录、时间、成功/失败）

## 历史记录

- 存储为 `clone_history.json`，与程序同目录
- 记录字段：仓库地址、代理端口、协议、保存目录、时间戳、成功/失败状态、错误信息
- 点击历史记录自动回填表单

## 保存目录

- 每次点击"浏览"选择目录，默认展示上次选择的目录
- 首次默认为程序所在目录

## 出错处理

- 克隆失败日志区显示完整 stderr
- 代理配置确保还原（try-finally）
- 历史记录标记失败并记录错误信息
