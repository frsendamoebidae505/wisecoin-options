# 00wisecoin_options_backup.py - 开发文档

## 文件概述

期权数据备份工具，用于自动备份期权和期货相关的 Excel 文件及配置文件。

## 作者

playbonze

## 功能描述

备份 WiseCoin 期权数据文件，包括移动指定的 Excel 文件和拷贝 JSON 配置文件到带时间戳的备份目录。

## 核心函数

### `backup_wisecoin_data()`

主备份函数，执行以下操作：

1. 在 `wisecoin_options_backup` 目录下创建带时间戳的子目录
2. 移动 9 个指定的 `.xlsx` 文件到备份目录
3. 拷贝 `wisecoin-symbol-params.json` 到备份目录

## 备份文件列表

| 文件名 | 说明 |
|--------|------|
| wisecoin-货权联动.xlsx | 货权联动数据 |
| wisecoin-期货行情-无期权.xlsx | 无期权标的的期货行情 |
| wisecoin-期货行情.xlsx | 期货行情数据 |
| wisecoin-期权参考.xlsx | 期权参考数据 |
| wisecoin-期权排行.xlsx | 期权排行数据 |
| wisecoin-期权品种.xlsx | 期权品种信息 |
| wisecoin-期权行情.xlsx | 期权行情数据 |
| wisecoin-市场概览.xlsx | 市场概览数据 |
| wisecoin-openctp数据.xlsx | OpenCTP 数据 |
| wisecoin-symbol-params.json | 品种参数配置 |

## 时间戳格式

备份目录名格式：`YYYYMMDD_HHMM`，例如：`20260104_0947`

## 使用方式

```bash
python 00wisecoin_options_backup.py
```

## 依赖模块

- `os`: 文件路径操作
- `shutil`: 文件移动和拷贝
- `datetime`: 时间戳生成

## 输出示例

```
============================================================
WiseCoin 期权数据备份工具
============================================================

✅ 创建备份目录: /path/to/wisecoin_options_backup/20260104_0947

开始移动 Excel 文件...
  ✅ 已移动: wisecoin-货权联动.xlsx
  ...

开始拷贝配置文件...
  ✅ 已拷贝: wisecoin-symbol-params.json

============================================================
📦 备份完成!
📁 备份位置: /path/to/wisecoin_options_backup/20260104_0947
✅ 成功移动: 9 个文件
⚠️  跳过/失败: 0 个文件
============================================================
```

## 注意事项

- 如果文件不存在会跳过并记录警告
- 文件移动操作（非拷贝），原位置文件会被移走
- 备份根目录不存在时会自动创建