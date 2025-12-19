# CLAUDE.md

## 开发文档

**dns-benchmark** 开发文档。本文件为开发者和贡献者提供详细的技术说明、架构指南和开发规范。

> **注意**：这是面向开发者的技术文档。用户文档请参阅 [README.md](README.md)。

## 开发环境设置指南

### 系统要求

- Python 3.13 或更高版本
- uv 包管理器
- 网络连接（用于 DNS 查询测试）
- Windows 10/11 或 Linux 系统

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
   .venv\\Scripts\\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **验证安装**：

   ```bash
   uv run main.py --help
   ```

### 依赖包说明

- **aiodns (>=3.6.0)**：异步 DNS 解析库，提供高性能并发查询（必需）
- **colorama (>=0.4.6)**：跨平台彩色终端输出（必需）
- **tabulate (>=0.9.0)**：表格输出（必需）
- **aiohttp (>=3.9.0)**：异步 HTTP 客户端库，用于 HTTP 性能测试（必需）

## 项目结构说明

```plain
dns-benchmark/
├── LICENSE              # MIT 授权文件
├── README.md           # 项目说明文档
├── CLAUDE.md           # 开发指南
├── main.py              # 主程序文件
├── pyproject.toml       # 项目配置和依赖声明
├── uv.lock              # UV锁文件（依赖版本锁定）
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

3. **辅助功能**：
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

# 启用HTTP性能测试（测试DNS返回IP的实际访问速度）
python main.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com --enable-http-test

# 完整HTTP测试配置
python main.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com github.com \
  --enable-http-test --http-timeout 10.0 --max-http-concurrency 3
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

**HTTP 性能测试选项（可选）**:

| 参数                     | 说明                                                      | 默认值              |
| ------------------------ | --------------------------------------------------------- | ------------------- |
| `--enable-http-test`     | 启用 HTTP 性能测试（测试 DNS 返回 IP 的实际访问速度）     | 否                  |
| `--http-timeout`         | HTTP 请求超时时间（秒）                                   | 10.0                |
| `--max-http-concurrency` | HTTP 测试最大并发数                                       | 5                   |
| `--max-redirects`        | HTTP 最大重定向次数                                       | 5                   |
| `--verify-ssl`           | 启用 SSL 证书验证（默认禁用，因 IP 访问时证书验证会失败） | 否                  |
| `--user-agent`           | 自定义 User-Agent 字符串                                  | "DNS-Benchmark/1.0" |

### 输出示例

程序运行后会显示：

1. **测试配置信息**：DNS 服务器列表、测试域名、测试次数、HTTP 测试设置等
2. **实时进度**：每个 DNS 服务器的测试进度和结果，包括 HTTP 测试进度
3. **汇总表格**：所有 DNS 服务器的性能排名（启用 HTTP 测试时包含综合得分）
4. **详细统计**：总体成功率、平均响应时间、错误分析等
5. **HTTP 测试报告**：HTTP 性能统计、时间指标、错误分类（启用 HTTP 测试时显示）
6. **推荐结果**：按性能排序的前 3 个推荐 DNS 服务器（综合考虑 DNS 和 HTTP 性能）

**启用 HTTP 测试时的额外输出**：

- HTTP 总体统计：成功率、平均响应时间、连接时间、TTFB 等
- HTTP 错误分析：连接错误、超时错误、SSL 错误等分类统计
- 综合得分：基于 DNS 性能（40%）和 HTTP 性能（60%）的综合评分

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

**HTTP 测试异常类型**（启用 HTTP 测试时）：

- `HTTPTestError`：HTTP 测试错误基类
- `HTTPConnectionError`：HTTP 连接错误
- `HTTPTimeoutError`：HTTP 超时错误
- `HTTPSSLError`：SSL 证书错误
- `HTTPRedirectError`：重定向错误
- `HTTPStatusCodeError`：HTTP 状态码错误

### 统计计算方法

#### DNS 性能统计

1. **成功率计算**：

   ```plain
   成功率 = (成功查询次数 / 总查询次数) × 100%
   ```

2. **响应时间统计**：

   - 平均值：所有成功查询的平均响应时间
   - 最小值：最快响应时间
   - 最大值：最慢响应时间
   - 标准差：响应时间的离散程度

#### HTTP 性能统计（启用 HTTP 测试时）

1. **HTTP 成功率**：

   ```plain
   HTTP成功率 = (成功HTTP测试数 / 总HTTP测试数) × 100%
   ```

2. **HTTP 时间指标**：

   - 连接时间：TCP 连接建立时间
   - TTFB：Time to First Byte（首字节时间）
   - 总时间：从开始请求到响应完全接收的时间
   - 数据大小：响应体大小（字节）

3. **HTTP 错误分类**：

   - 连接错误、超时错误、SSL 错误
   - 重定向错误、4xx 客户端错误、5xx 服务器错误

#### 综合排名算法

1. **DNS 得分计算**：

   ```plain
   DNS得分 = (时间得分 × 0.7) + (成功率得分 × 0.3)
   时间得分 = max(0, 1 - 平均响应时间/5.0)  # 假设5秒为最大可接受时间
   成功率得分 = 成功率 / 100
   ```

2. **HTTP 得分计算**：

   ```plain
   HTTP得分 = (时间得分 × 0.5) + (成功率得分 × 0.5)
   时间得分 = max(0, 1 - 平均HTTP时间/30.0)  # 假设30秒为最大可接受时间
   成功率得分 = HTTP成功率 / 100
   ```

3. **综合得分**：

   ```plain
   综合得分 = DNS得分 × 0.4 + HTTP得分 × 0.6
   ```

   默认权重：DNS 占 40%，HTTP 占 60%

4. **排序规则**：

   - 启用 HTTP 测试时：按综合得分降序排序（得分越高越好）
   - 未启用 HTTP 测试时：按 DNS 平均响应时间升序排序
   - 成功率低于 50%的服务器不参与推荐
   - None 值（完全失败）排在最后

### Git 提交规范

遵循 `Conventional Commits` 规范，详见 https://www.conventionalcommits.org/

### 扩展开发建议

#### HTTP 测试相关扩展

1. **增强 HTTP 测试功能**：

   - 支持 HTTPS 协议测试（需处理 SSL 证书验证问题）
   - 添加 HTTP 请求头自定义功能
   - 实现 POST 等其他 HTTP 方法测试
   - 支持自定义测试路径（非根路径）

2. **性能优化**：

   - 实现 HTTP 连接池复用
   - 添加 DNS 结果缓存以减少重复测试
   - 支持增量测试（仅测试新解析的 IP 地址）

3. **高级功能**：
   - 添加网页内容验证（检查特定元素是否存在）
   - 支持性能基准比较（与历史数据对比）
   - 实现地理信息识别（基于 IP 地址的位置信息）

#### DNS 测试相关扩展

1. **添加新的 DNS 查询类型**：

   - 修改`async_resolve_domain()`函数支持 A、AAAA、MX、CNAME 等记录类型
   - 在`DNSBenchmark`类中添加相应的配置选项

2. **增强报告功能**：

   - 支持 JSON/CSV 格式导出
   - 添加图表生成功能（matplotlib）
   - 实现历史数据对比和趋势分析

3. **网络优化**：
   - 添加代理支持
   - 实现 DNS over HTTPS/TLS（DoH/DoT）
   - 支持自定义 DNS 端口和查询协议

#### 综合优化建议

1. **配置文件支持**：

   - 支持从配置文件读取测试参数
   - 实现测试模板和预设配置

2. **测试策略优化**：

   - 添加智能测试策略（根据网络状况调整参数）
   - 支持定时任务和自动化测试

3. **用户界面改进**：
   - 添加 GUI 界面
   - 实现实时监控仪表盘
   - 支持 Web API 接口

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

#### 问题 1：异步模式不可用

```plain
错误: aiodns 模块不可用，无法进行DNS测试
```

**解决方案**：

```bash
# 使用UV安装依赖
uv sync
```

注意：本工具仅支持异步模式，需要 aiodns 模块才能运行。

#### 问题 2：DNS 查询超时

```plain
超时: google.com @ 8.8.8.8 (2.0s)
```

**解决方案**：

1. 检查网络连接
2. 增加超时时间：`--timeout 5.0`
3. 增加重试次数：`--retries 3`
4. 尝试其他 DNS 服务器

#### 问题 3：Windows 平台事件循环错误

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

#### 问题 4：彩色输出异常

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

**最后更新**：2025-12-19
**维护者**：项目开发团队
