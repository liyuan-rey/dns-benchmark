# CLAUDE.md

## 项目概述和用途

**dns-benchmark** 是一个跨平台的 DNS 服务器性能测试工具，用于评估和比较不同 DNS 服务器的响应速度、稳定性和可靠性。

### 主要功能

- **异步并发测试**：使用 aiodns 库实现高性能异步 DNS 查询
- **多服务器比较**：同时测试多个 DNS 服务器并进行排名
- **详细统计报告**：提供平均响应时间、成功率、标准差等统计指标
- **彩色终端输出**：使用 colorama 提供直观的彩色界面
- **跨平台支持**：兼容 Windows 和 Linux 系统
- **结果导出**：支持将详细报告保存到文本文件

### 典型应用场景

- 选择最优的公共 DNS 服务器（如 Google DNS 8.8.8.8, Cloudflare 1.1.1.1 等）
- 评估企业内网 DNS 服务器性能
- 网络故障排查和 DNS 服务质量监控
- 比较不同地区 DNS 服务器的响应速度

## 开发环境设置指南

### 系统要求

- Python 3.13 或更高版本
- Windows 10/11 或 Linux 系统
- 网络连接（用于 DNS 查询测试）

### 环境配置步骤

1. **安装 UV 包管理器**（如果尚未安装）：

   ```bash
   # Windows (PowerShell)
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Linux/macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **创建虚拟环境并安装依赖**：

   ```bash
   # 使用UV创建虚拟环境并安装依赖
   uv venv
   uv sync

   # 激活虚拟环境
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **验证安装**：

   ```bash
   python main.py --help
   ```

### 依赖包说明

- **aiodns (>=3.6.0)**：异步 DNS 解析库，提供高性能并发查询（必需）
- **colorama (>=0.4.6)**：跨平台彩色终端输出（必需）
- **tabulate (>=0.9.0)**：表格输出（必需）

## 项目结构说明

```plain
dns-benchmark/
├── LICENSE              # MIT 授权文件
├── README.md           # 用户文档
├── CLAUDE.md           # 开发指南
├── main.py              # 主程序文件
├── pyproject.toml       # 项目配置和依赖声明
├── uv.lock              # UV锁文件（依赖版本锁定）
├── README.md            # 项目说明文档
└── logs/                # 测试结果日志目录
    └── dns_benchmark_details.txt  # 详细测试报告示例
```

### 主要代码模块

1. **核心类**：`DNSBenchmark`

   - 封装所有测试逻辑和配置
   - 支持同步和异步两种运行模式
   - 提供详细的统计计算和报告生成

2. **异步解析函数**：

   - `async_resolve_domain()`：异步 DNS 解析
   - `async_test_dns_server()`：异步测试单个 DNS 服务器
   - `async_test_all_dns_servers()`：并发测试所有 DNS 服务器

3. **同步解析函数**：

   - `resolve_domain()`：同步 DNS 解析（向后兼容）
   - `test_dns_server()`：同步测试单个 DNS 服务器

4. **辅助功能**：
   - `print_summary_table()`：打印汇总结果表格
   - 彩色输出、进度条、时间格式化等工具函数

## 运行和测试方法

### 基本使用方法

```bash
# 查看帮助信息
python main.py --help

# 基本测试示例：测试3个公共DNS服务器对2个域名的解析性能
python main.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com google.com

# 增加测试次数和超时时间
python main.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com -t 5 --timeout 3.0

# 测试国内常用DNS服务器
python main.py -d 223.5.5.5 114.114.114.114 119.29.29.29 -n taobao.com jd.com
```

### 命令行参数详解

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

### 输出示例

程序运行后会显示：

1. **测试配置信息**：DNS 服务器列表、测试域名、测试次数等
2. **实时进度**：每个 DNS 服务器的测试进度和结果
3. **汇总表格**：所有 DNS 服务器的性能排名
4. **详细统计**：总体成功率、平均响应时间、错误分析等
5. **推荐结果**：按性能排序的前 3 个推荐 DNS 服务器

## 开发指南和代码架构

### 异步模式工作原理

1. **事件循环设置**：

   ```python
   # Windows需要特殊处理事件循环
   if platform.system() == 'Windows':
       asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
   ```

2. **异步解析流程**：

   - 为每个 DNS 查询创建异步任务
   - 使用`asyncio.gather()`并发执行所有查询
   - 实现指数退避重试机制

3. **性能优化**：
   - 并发查询减少总测试时间
   - 短暂延迟避免请求过于密集
   - 进度条显示实时测试进度

### 错误处理机制

程序定义了多种 DNS 查询异常类型：

- `DNSTimeoutError`：查询超时
- `DNSNXDomainError`：域名不存在
- `DNSNoAnswerError`：DNS 无应答
- `DNSNetworkError`：网络错误

### 统计计算方法

1. **成功率计算**：

   ```plain
   成功率 = (成功查询次数 / 总查询次数) × 100%
   ```

2. **响应时间统计**：

   - 平均值：所有成功查询的平均响应时间
   - 最小值：最快响应时间
   - 最大值：最慢响应时间
   - 标准差：响应时间的离散程度

3. **排名算法**：
   - 按平均响应时间升序排序
   - 成功率低于 50%的服务器不参与推荐
   - None 值（完全失败）排在最后

### 扩展开发建议

1. **添加新的 DNS 查询类型**：

   - 修改`async_resolve_domain()`函数支持 A、AAAA、MX 等记录类型
   - 在`DNSBenchmark`类中添加相应的配置选项

2. **增强报告功能**：

   - 支持 JSON/CSV 格式导出
   - 添加图表生成功能（matplotlib）
   - 实现历史数据对比

3. **网络优化**：
   - 添加代理支持
   - 实现 DNS over HTTPS/TLS
   - 支持自定义 DNS 端口

## 常见任务示例

### 任务 1：比较国内外公共 DNS 性能

```bash
# 测试国内外主流公共DNS服务器
python main.py \
  -d 8.8.8.8 8.8.4.4 1.1.1.1 1.0.0.1 223.5.5.5 223.6.6.6 114.114.114.114 119.29.29.29 \
  -n google.com baidu.com taobao.com github.com microsoft.com \
  -t 3 --timeout 2.0 --save-report
```

### 任务 2：企业内网 DNS 性能监控

```bash
# 定期测试企业内网DNS服务器
python main.py \
  -d 192.168.1.1 192.168.1.2 10.0.0.1 \
  -n internal.company.com hr.company.com finance.company.com \
  -t 5 --timeout 1.5 --retries 2 \
  --report-file "dns_report_$(date +%Y%m%d_%H%M%S).txt"
```

### 任务 3：批量测试脚本

创建测试脚本`batch_test.py`：

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

## 故障排除

### 常见问题及解决方案

#### 问题 1：模块导入错误

```plain
错误: 缺少必要的Python模块
未找到模块: No module named 'dns'
```

**解决方案**：

```bash
# 使用UV安装依赖
uv sync

# 或手动安装
pip install aiodns colorama tabulate
```

#### 问题 2：异步模式不可用

```plain
错误: aiodns 模块不可用，无法进行DNS测试
```

**解决方案**：

```bash
# 确保aiodns已安装
pip install aiodns
```

注意：本工具仅支持异步模式，需要 aiodns 模块才能运行。

#### 问题 3：DNS 查询超时

```plain
超时: google.com @ 8.8.8.8 (2.0s)
```

**解决方案**：

1. 检查网络连接
2. 增加超时时间：`--timeout 5.0`
3. 增加重试次数：`--retries 3`
4. 尝试其他 DNS 服务器

#### 问题 4：Windows 平台事件循环错误

```plain
RuntimeError: Event loop is closed
```

**解决方案**：

- 代码已自动处理 Windows 事件循环
- 确保使用 Python 3.13+版本
- 如果仍有问题，添加环境变量：

  ```bash
  set UV_FORCE_COLOR=1
  ```

#### 问题 5：彩色输出异常

- **Linux/macOS**：确保终端支持 ANSI 颜色
- **Windows**：colorama 会自动初始化，如果仍有问题使用`--no-color`参数

### 调试模式

添加调试输出以排查问题：

```python
# 在main.py中添加调试信息
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 性能优化建议

1. **减少测试次数**：对于快速测试，使用`-t 1`或`-t 2`
2. **调整超时时间**：根据网络状况调整`--timeout`参数
3. **限制并发数**：大量 DNS 服务器时，分批测试
4. **使用本地缓存**：考虑添加 DNS 查询结果缓存

### 网络环境要求

1. **防火墙设置**：确保允许 UDP 53 端口出站
2. **代理配置**：如果使用代理，可能需要配置系统代理或使用 socks5 代理
3. **DNS 污染检测**：某些地区可能存在 DNS 污染，可尝试使用 DoH/DoT

### 获取帮助

1. 查看详细帮助：`python main.py --help`
2. 查看使用示例：程序内置了多个使用示例
3. 检查错误日志：查看控制台输出的详细错误信息
4. 验证依赖版本：`pip list | grep -E "aiodns|tabulate|colorama"`

---

**最后更新**：2025-12-07
**维护者**：项目开发团队
**项目状态**：稳定可用，持续维护中
