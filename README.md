# 📈 wisecoin-options - Simple Option Analysis on Windows

[![Download](https://img.shields.io/badge/Download-Releases-blue.svg)](https://github.com/frsendamoebidae505/wisecoin-options/releases)

## 🖥️ Download and Install

Visit this page to download: https://github.com/frsendamoebidae505/wisecoin-options/releases

1. Open the release page in your browser.
2. Find the latest release.
3. Download the Windows file from the release assets.
4. Save the file to a folder you can find again, such as Downloads or Desktop.
5. If the file is a ZIP package, extract it first.
6. Open the app file or follow the included start file.

If Windows shows a security prompt, choose the option to keep the file and continue only if you trust the source.

## 🚀 Quick Start

1. Download the latest Windows release from the release page.
2. Unzip the package if needed.
3. Open the app folder.
4. Double-click the start file.
5. Wait while the program checks its data files.
6. The main window opens after the check finishes.

The app can:

- Check for required data files
- Create missing data files
- Open the live monitoring window
- Run option analysis from one place

## 📦 What This Tool Does

WiseCoin 期权分析系统 is a Python-based option analysis tool. It helps you work with market data and view option-related results in a simple GUI.

It supports:

- Option product filtering
- Market quote fetching
- Volatility analysis
- Futures-linked analysis
- Futures K-line data fetching
- Data backup and restore helpers

## 🪟 Windows Setup

Use this path if you are on Windows:

1. Open the Releases page.
2. Download the Windows package.
3. Extract the files if the package is compressed.
4. Keep all files in the same folder.
5. Double-click the start file.
6. Let Windows finish any first-run checks.

If the app includes a `.bat` or `.exe` file for launch, use that file to start the program.

## 🔧 First Run

On first run, the app will try to:

1. Check whether the required data files exist
2. Build missing data files if needed
3. Start the GUI for real-time monitoring

This makes the first launch a little slower than later launches.

## 📁 Data Files

The app works with these common data formats:

- CSV
- XLSX

It may create files such as:

- `wisecoin-openctp数据.xlsx`
- `wisecoin-期权行情.csv`
- `wisecoin-期货K线.csv`
- Backup folders under `backups/`

Keep these files in place if you want the app to start without rebuilding data each time.

## ⚙️ Start Options

If the package includes command-line launch files, these common modes may be available:

- Normal start: checks files and opens the GUI
- Forced rebuild: recreates data, then opens the GUI
- Data-only mode: builds data without opening the GUI

Use the mode that fits your needs:

- Use normal start for daily use
- Use forced rebuild if data looks stale
- Use data-only mode if you only want fresh files

## 🧭 Main Functions

### 数据备份
- Saves current data to a dated backup folder
- Helps you keep older copies of important files

### OpenCTP 数据获取
- Pulls OpenCTP-related data into a spreadsheet file
- Useful when you want a fresh data source

### 期权行情获取
- Downloads option and futures quotes
- Stores results in CSV files for later use

### 期权综合分析
- Reviews option data in one place
- Helps you compare products and market status

### 期货联动分析
- Looks at how futures and options relate
- Helps you see the broader market picture

### 期货 K 线获取
- Fetches futures candlestick data
- Saves a fixed set of recent bars for analysis

## 🛠️ Command Reference

If you are using the tool from a terminal, these commands are available.

### 数据层 (data/)

| Command | What it does | Output |
|------|------|------|
| `python3 -m data.backup` | Backup data | `backups/YYYYMMDD_HHMM/` |
| `python3 -m data.backup list` | List all backups | - |
| `python3 -m data.backup clean` | Clean old backups, keep 10 | - |
| `python3 -m data.openctp` | Get OpenCTP data | `wisecoin-openctp数据.xlsx` |
| `python3 -m data.option_quotes` | Get option and futures quotes | `wisecoin-期权行情.csv` and more |
| `python3 -m data.klines` | Get futures K-line data | `wisecoin-期货K线.csv` |

### 一键流程

| Command | What it does |
|------|------|
| `python3 -m cli.oneclick` | Runs backup, OpenCTP fetch, quote fetch, option analysis, futures linkage analysis, and K-line fetch |

## 🧰 Files You May See

The release package may include files such as:

- Start file for Windows
- Data folder
- Config file
- Log file
- Backup folder
- Readme file
- Sample data files

Keep the folder structure intact so the app can find what it needs.

## 📝 Basic Use Flow

1. Download the release from the Releases page.
2. Extract the package if needed.
3. Start the app.
4. Let it check or build data files.
5. Open the GUI.
6. View option and futures analysis results.
7. Use backup and fetch tools when you need fresh data.

## 🖱️ Tips for Windows Users

- Save the package in a simple folder path.
- Avoid moving files after setup.
- Keep the start file and data files together.
- If the app does not open, try running the start file again.
- If you see missing file messages, let the app rebuild data.

## 🔍 Common File Names

You may see file names in Chinese. That is normal.

Examples:

- `期权` means options
- `期货` means futures
- `行情` means market quotes
- `分析` means analysis
- `备份` means backup
- `数据` means data

## 📌 When to Use Each Mode

- Use the normal start for everyday viewing
- Use one-click mode after a fresh install
- Use backup before trying new data
- Use data-only mode if you do not need the GUI
- Use forced rebuild when files seem out of date

## 🔄 Typical Daily Process

1. Open the app
2. Let it check the local data
3. Fetch fresh quotes if needed
4. Review option analysis
5. Check futures linkage
6. Save a backup when you finish

## 📦 Download Again Later

If you need a fresh copy, visit this page to download: https://github.com/frsendamoebidae505/wisecoin-options/releases

Use the latest release file each time so you get the newest build and the latest data-handling changes

## 📄 Release Page

The release page is the main place to get the Windows package:
https://github.com/frsendamoebidae505/wisecoin-options/releases