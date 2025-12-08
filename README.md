# DNS 性能测试工具

一个跨平台的 DNS 服务器性能测试工具，用于评估和比较不同 DNS 服务器的响应速度、稳定性和可靠性。

[![Python 版本](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![许可证](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 功能特性

- **异步并发测试**：使用 aiodns 库实现高性能异步 DNS 查询
- **多服务器比较**：同时测试多个 DNS 服务器并进行排名
- **HTTP 性能测试**：测试 DNS 返回 IP 地址的实际网页访问性能（可选）
- **综合评分系统**：结合 DNS 响应时间和 HTTP 访问时间进行综合排名
- **详细统计报告**：提供平均响应时间、成功率、标准差等统计指标
- **HTTP 测试报告**：HTTP 成功率、连接时间、TTFB、数据大小等详细指标
- **彩色终端输出**：使用 colorama 提供直观的彩色界面
- **跨平台支持**：兼容 Windows 和 Linux 系统
- **结果导出**：支持将详细报告保存到文本文件

## 典型应用场景

- **选择最优的公共 DNS 服务器**：比较 Google DNS (8.8.8.8)、Cloudflare (1.1.1.1)、阿里云 DNS (223.5.5.5) 等公共 DNS 的性能
- **评估企业内网 DNS 服务器**：监控内部 DNS 服务器的响应速度和稳定性
- **网络故障排查**：诊断 DNS 解析问题，识别慢速或不可靠的 DNS 服务器
- **跨地区 DNS 性能测试**：比较不同地区 DNS 服务器的响应速度差异
- **HTTP 访问性能评估**：测试 DNS 解析结果的实际网页访问速度（启用 HTTP 测试时）
- **DNS 服务质量监控**：定期测试 DNS 服务器，确保服务质量符合要求

## 系统要求

- **Python 3.13 或更高版本**
- **Windows 10/11 或 Linux 系统**
- **网络连接**：用于 DNS 查询测试
- **防火墙设置**：确保允许 UDP 53 端口出站
- **终端支持**：支持 ANSI 颜色编码的终端（彩色输出）

## 安装

### 使用 UV（推荐）

```bash
# 安装 UV 包管理器（如果尚未安装）
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
uv sync

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 验证安装
python main.py --help
```

### 使用 pip

```bash
# 基本依赖（必需）
pip install aiodns colorama tabulate aiohttp
```

## 快速开始

### 基本用法

```bash
# 查看帮助信息
python main.py --help

# 测试3个公共DNS服务器对2个域名的解析性能
python main.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com google.com

# 增加测试次数和超时时间
python main.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com -t 5 --timeout 3.0

# 测试国内常用DNS服务器
python main.py -d 223.5.5.5 114.114.114.114 119.29.29.29 -n taobao.com jd.com

# 启用HTTP性能测试（测试DNS返回IP的实际访问速度）
python main.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com --enable-http-test

# 完整HTTP测试配置
python main.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com github.com \
  --enable-http-test --http-timeout 10.0 --max-http-concurrency 3
```

### 命令行参数

#### 基本参数

| 参数            | 缩写 | 说明                           | 默认值                   |
| --------------- | ---- | ------------------------------ | ------------------------ |
| `--dns`         | `-d` | DNS 服务器 IP 地址列表（必需） | -                        |
| `--names`       | `-n` | 要解析的域名列表（必需）       | -                        |
| `--tests`       | `-t` | 每个域名测试次数               | 3                        |
| `--timeout`     | -    | DNS 查询超时时间（秒）         | 2.0                      |
| `--retries`     | -    | 查询失败时的重试次数           | 1                        |
| `--no-color`    | -    | 禁用彩色输出                   | 否                       |
| `--save-report` | -    | 保存详细报告到文件             | 否                       |
| `--report-file` | -    | 报告文件名                     | dns_benchmark_report.txt |

#### HTTP 性能测试选项（可选）

| 参数                     | 说明                                                      | 默认值              |
| ------------------------ | --------------------------------------------------------- | ------------------- |
| `--enable-http-test`     | 启用 HTTP 性能测试（测试 DNS 返回 IP 的实际访问速度）     | 否                  |
| `--http-timeout`         | HTTP 请求超时时间（秒）                                   | 10.0                |
| `--max-http-concurrency` | HTTP 测试最大并发数                                       | 5                   |
| `--max-redirects`        | HTTP 最大重定向次数                                       | 5                   |
| `--verify-ssl`           | 启用 SSL 证书验证（默认禁用，因 IP 访问时证书验证会失败） | 否                  |
| `--user-agent`           | 自定义 User-Agent 字符串                                  | "DNS-Benchmark/1.0" |

## 使用示例

### 示例 1：比较国内外公共 DNS 性能

```bash
python main.py \
  -d 8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1 223.5.5.5 223.6.6.6 114.114.114.114 119.29.29.29 \
  -n google.com baidu.com taobao.com github.com microsoft.com \
  -t 3 --timeout 2.0 --save-report
```

### 示例 2：企业内网 DNS 性能监控

```bash
python main.py \
  -d 192.168.1.1 192.168.1.2 10.0.0.1 \
  -n internal.company.com hr.company.com finance.company.com \
  -t 5 --timeout 1.5 --retries 2 \
  --report-file "dns_report_$(date +%Y%m%d_%H%M%S).txt"
```

### 示例 3：批量测试脚本

创建 `batch_test.py`：

```python
import asyncio
import subprocess
import sys

test_cases = [
    {
        'name': '国内网站测试',
        'dns': ['223.5.5.5', '114.114.114.114', '119.29.29.29'],
        'domains': ['baidu.com', 'taobao.com', 'jd.com', 'qq.com']
    },
    {
        'name': '国际网站测试',
        'dns': ['8.8.8.8', '1.1.1.1', '9.9.9.9'],
        'domains': ['google.com', 'github.com', 'stackoverflow.com', 'wikipedia.org']
    }
]

async def run_test_case(test_case):
    print(f"\n开始测试: {test_case['name']}")
    cmd = [
        sys.executable, 'main.py',
        '-d', *test_case['dns'],
        '-n', *test_case['domains'],
        '-t', '3',
        '--timeout', '2.0',
        '--save-report'
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()

async def main():
    tasks = [run_test_case(tc) for tc in test_cases]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
```

## 输出说明

程序运行后会显示：

1. **测试配置信息**：DNS 服务器列表、测试域名、测试次数、HTTP 测试设置等
2. **实时进度**：每个 DNS 服务器的测试进度和结果，包括 HTTP 测试进度（如果启用）
3. **汇总表格**：所有 DNS 服务器的性能排名（启用 HTTP 测试时包含综合得分）
4. **详细统计**：总体成功率、平均响应时间、错误分析等
5. **HTTP 测试报告**（如果启用）：HTTP 性能统计、连接时间、TTFB、数据大小、错误分类等
6. **推荐结果**：按性能排序的前 3 个推荐 DNS 服务器（综合考虑 DNS 和 HTTP 性能）

### 排名算法说明

- **DNS 性能得分**：基于响应时间（70%）和成功率（30%）计算
- **HTTP 性能得分**：基于 HTTP 响应时间（50%）和 HTTP 成功率（50%）计算
- **综合得分**：DNS 得分 × 40% + HTTP 得分 × 60%（启用 HTTP 测试时）
- **排序规则**：
  - 启用 HTTP 测试时：按综合得分降序排序（得分越高越好）
  - 未启用 HTTP 测试时：按 DNS 平均响应时间升序排序
  - 成功率低于 50%的服务器不参与推荐

## 项目结构

```plain
dns-benchmark/
├── LICENSE              # MIT 授权文件
├── README.md           # 用户文档
├── CLAUDE.md           # 开发指南（用于 Claude Code）
├── main.py              # 主程序文件
├── pyproject.toml       # 项目配置和依赖声明
├── uv.lock              # UV 锁文件（依赖版本锁定）
└── logs/                # 测试结果日志目录
    └── dns_benchmark_details.txt  # 详细测试报告示例
```

## 依赖包

- **aiodns (>=3.6.0)**：异步 DNS 解析库，提供高性能并发查询（必需）
- **colorama (>=0.4.6)**：跨平台彩色终端输出（必需）
- **tabulate (>=0.9.0)**：表格输出（必需）
- **aiohttp (>=3.9.0)**：异步 HTTP 客户端库，用于 HTTP 性能测试（必需）

## 故障排除

### 常见问题

1. **模块导入错误**：

   ```bash
   # 使用UV安装依赖
   uv sync

   # 或手动安装
   pip install aiodns colorama tabulate
   ```

2. **异步模式不可用**：

   ```bash
   # 确保aiodns已安装
   pip install aiodns
   ```

   注意：本工具仅支持异步模式，需要 aiodns 模块才能运行。

3. **DNS 查询超时**：

   - 检查网络连接
   - 增加超时时间：`--timeout 5.0`
   - 增加重试次数：`--retries 3`
   - 尝试其他 DNS 服务器

4. **Windows 平台事件循环错误**：

   ```plain
   RuntimeError: Event loop is closed
   ```

   - 代码已自动处理 Windows 事件循环
   - 确保使用 Python 3.13+版本
   - 如果仍有问题，设置环境变量：

     ```bash
     set UV_FORCE_COLOR=1
     ```

5. **彩色输出异常**：
   - **Linux/macOS**：确保终端支持 ANSI 颜色
   - **Windows**：colorama 会自动初始化，如果仍有问题使用 `--no-color` 参数

### 性能优化建议

1. 减少测试次数：对于快速测试，使用 `-t 1` 或 `-t 2`
2. 调整超时时间：根据网络状况调整 `--timeout` 参数
3. 限制并发数：大量 DNS 服务器时，分批测试
4. 使用本地缓存：考虑添加 DNS 查询结果缓存

## 开发指南

详细开发指南请参阅 [CLAUDE.md](CLAUDE.md) 文件。

## 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 联系方式

如有问题或建议：

- 提交 [Issue](https://github.com/yourusername/dns-benchmark/issues)
- 邮箱：your-email@example.com

---

**最后更新**：2025-12-08
**版本**：0.1.0
**状态**：稳定可用，持续维护中
