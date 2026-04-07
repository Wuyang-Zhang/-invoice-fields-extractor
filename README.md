# 发票字段提取说明

这个项目用于从类似 `1.jpg` 这样的图片中，自动提取上下两张发票的以下字段：

- 发票号码
- 开票日期
- 税额
- 价税合计（小写）

当前提供两种使用方式：

- 命令行脚本：`11.py`
- 双击图形界面：`Launch_GUI.bat`

## 运行环境

需要满足以下条件：

- Windows 10 / Windows 11
- 已安装 Python 3.8+
- 已安装 `Pillow` 和 `numpy`
- 系统可用 Windows 自带 OCR 组件

## 安装依赖

在当前目录打开 PowerShell，执行：

```powershell
python -m pip install pillow numpy
```

## 目录说明

当前目录下的主要文件：

- `11.py`：命令行识别脚本
- `invoice_gui.pyw`：图形界面入口
- `Launch_GUI.bat`：双击启动图形界面
- `1.jpg`：示例图片

## 方式一：命令行运行

在当前目录打开 PowerShell，执行：

```powershell
cd C:\Users\ZHIQIN ZHANG\Desktop\liuyi
python 11.py 1.jpg
```

如果不传图片路径，默认读取当前目录下的 `1.jpg`：

```powershell
python 11.py
```

## 方式二：双击运行

如果你不想敲命令，可以直接双击：

```text
Launch_GUI.bat
```

双击后会打开一个窗口，操作流程如下：

1. 点击 `Select Image`
2. 选择待识别图片
3. 点击 `Run Extraction`
4. 在窗口下方查看 JSON 结果

如果当前目录下已经有 `1.jpg`，你也可以不选文件，直接点击 `Run Extraction`。

## 运行结果示例

输出结果是 JSON，例如：

```json
[
  {
    "invoice_number": "26117000000002012307",
    "issue_date": "2026-02-11",
    "tax_amount": "127.01",
    "total_amount": "1104.00"
  },
  {
    "invoice_number": "26112000000564374836",
    "issue_date": "2026-02-11",
    "tax_amount": "71.72",
    "total_amount": "1267.00"
  }
]
```

## 脚本做了什么

识别流程大致如下：

1. 自动定位图片里上下两张发票区域
2. 分别裁剪每张发票的右上角和右下角关键区域
3. 调用 Windows 自带 OCR 做文字识别
4. 从识别结果中解析出发票号码、开票日期、税额和价税合计（小写）

## 常见问题

### 1. 提示找不到 `PIL` 或 `numpy`

说明依赖没有安装，执行：

```powershell
python -m pip install pillow numpy
```

### 2. 双击 `Launch_GUI.bat` 没反应

先检查：

- `python` / `pyw` 是否已经加入系统 PATH
- 依赖是否已经安装完成
- 是否仍在 Windows 环境下运行

你也可以先用命令行确认脚本本身可以运行：

```powershell
python 11.py 1.jpg
```

### 3. 运行后没有识别结果

先检查：

- 图片是不是和 `1.jpg` 类似的版式
- 图片是否太模糊、倾斜过大、分辨率太低
- 图片里是否确实是上下两张发票

这个版本对你当前这类样图效果正常，但如果后续图片版式差异很大，可能需要调整裁剪比例。

### 4. OCR 在别的机器上不工作

这个脚本依赖 Windows 自带 OCR。如果系统相关组件不可用，脚本就无法正常识别。

## 你现在可以直接这样用

命令行：

```powershell
cd C:\Users\ZHIQIN ZHANG\Desktop\liuyi
python 11.py 1.jpg
```

双击方式：

```text
直接双击 Launch_GUI.bat
```
