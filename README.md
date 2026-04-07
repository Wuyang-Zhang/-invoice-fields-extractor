# 发票字段提取说明

这个项目用于从类似 `1.jpg` 这样的图片中，自动提取上下两张发票的以下字段：

- 发票号码
- 开票日期
- 税额
- 价税合计（小写）

当前脚本文件是 `11.py`。

## 运行环境

需要满足以下条件：

- Windows 10 / Windows 11
- 已安装 Python 3.8+
- 已安装 `Pillow` 和 `numpy`
- 系统可用 Windows 自带 OCR 组件

## 安装依赖

在当前目录打开 PowerShell，执行：

```powershell
pip install pillow numpy
```

如果你有多个 Python，也可以这样：

```powershell
python -m pip install pillow numpy
```

## 文件准备

把待识别图片放到当前目录，例如：

```text
C:\Users\ZHIQIN ZHANG\Desktop\liuyi\1.jpg
```

## 运行方式

在当前目录打开 PowerShell，执行：

```powershell
python 11.py 1.jpg
```

如果不传图片路径，默认也会读取当前目录下的 `1.jpg`：

```powershell
python 11.py
```

## 运行结果

输出是 JSON，示例：

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

脚本大致流程：

1. 自动定位图片里上下两张发票区域。
2. 分别裁剪每张发票的右上角和右下角关键区域。
3. 调用 Windows 自带 OCR 做文字识别。
4. 从识别结果中解析出发票号码、开票日期、税额和价税合计（小写）。

## 常见问题

### 1. 提示找不到 `PIL` 或 `numpy`

说明依赖没装好，执行：

```powershell
python -m pip install pillow numpy
```

### 2. 运行后没有识别结果

先检查：

- 图片是不是和 `1.jpg` 类似的版式
- 图片是否太模糊、倾斜过大、分辨率太低
- 图片里是否确实是上下两张发票

这个版本对你当前这类样图效果是正常的，但如果后面图片版式差异很大，可能需要调整裁剪比例。

### 3. OCR 在别的机器上不工作

这个脚本依赖 Windows 自带 OCR。如果系统相关组件不可用，脚本就无法正常识别。

## 你现在可以直接这样用

```powershell
cd C:\Users\ZHIQIN ZHANG\Desktop\liuyi
python 11.py 1.jpg
```

如果你要，我下一步可以继续帮你加：

- 批量识别整个文件夹
- 结果导出 Excel / CSV
- 做成双击可用的桌面小工具
