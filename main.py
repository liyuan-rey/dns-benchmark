#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNS服务器性能测试工具 - 异步并发版本
支持Windows和Linux系统，提供彩色输出和详细统计
"""

import argparse
import asyncio
import sys
import io
import platform
import time
import statistics
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

# 设置标准输出为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 检查并导入所需模块
# 注意：已移除 dnspython 和 prettytable 依赖

# 尝试导入异步DNS库
try:
    import aiodns

    HAS_AIODNS = True
except ImportError:
    HAS_AIODNS = False

# 尝试导入aiohttp用于HTTP测试
try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

# 尝试导入tabulate用于表格输出（必需依赖）
try:
    from tabulate import tabulate

    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# 尝试导入colorama用于彩色输出
try:
    from colorama import init, Fore, Style, Back

    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

    # 创建虚拟颜色类以便代码可以运行
    class DummyColor:
        def __getattr__(self, name):
            return ""

    Fore = DummyColor()
    Style = DummyColor()
    Back = DummyColor()

# ============================================================================
# 自定义异常类型
# ============================================================================


class DNSQueryError(Exception):
    """DNS查询错误基类"""

    pass


class DNSTimeoutError(DNSQueryError):
    """DNS查询超时错误"""

    pass


class DNSNXDomainError(DNSQueryError):
    """域名不存在错误"""

    pass


class DNSNoAnswerError(DNSQueryError):
    """DNS无应答错误"""

    pass


class DNSNetworkError(DNSQueryError):
    """网络错误"""

    pass


# HTTP测试异常类型
class HTTPTestError(Exception):
    """HTTP测试错误基类"""

    pass


class HTTPConnectionError(HTTPTestError):
    """HTTP连接错误"""

    pass


class HTTPTimeoutError(HTTPTestError):
    """HTTP超时错误"""

    pass


class HTTPSSLError(HTTPTestError):
    """SSL证书错误"""

    pass


class HTTPRedirectError(HTTPTestError):
    """重定向错误"""

    pass


class HTTPStatusCodeError(HTTPTestError):
    """HTTP状态码错误"""

    pass


# ============================================================================
# 辅助函数
# ============================================================================


def print_colored(
    text: str,
    color: str = Fore.WHITE,
    style: str = Style.NORMAL,
    end: str = "\n",
    flush: bool = False,
) -> None:
    """打印彩色文本"""
    print(f"{style}{color}{text}{Style.RESET_ALL}", end=end, flush=flush)


def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds is None:
        return "失败"
    if seconds == float("inf"):
        return "∞"
    return f"{seconds*1000:.1f}ms"


def get_progress_bar(progress: float, width: int = 30) -> str:
    """获取进度条字符串"""
    filled = int(progress * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress*100:.1f}%"


# 检查必需依赖
missing_deps = []
if not HAS_AIODNS:
    missing_deps.append("aiodns")
if not HAS_TABULATE:
    missing_deps.append("tabulate")
if not HAS_COLORAMA:
    missing_deps.append("colorama")
if not HAS_AIOHTTP:
    missing_deps.append("aiohttp")

if missing_deps:
    print_colored("=" * 70, Fore.RED)
    print_colored("错误: 缺少必要的Python模块", Fore.RED, Style.BRIGHT)
    print_colored("=" * 70, Fore.RED)
    print_colored(f"\n未找到模块: {', '.join(missing_deps)}", Fore.YELLOW)
    print_colored("\n请安装所需模块:", Fore.CYAN)
    print_colored("  pip install aiodns colorama tabulate aiohttp", Fore.GREEN)
    print_colored("\n安装完成后重新运行此脚本", Fore.CYAN)
    sys.exit(1)


async def async_resolve_domain(
    dns_server: str, domain: str, timeout: float = 2.0, retries: int = 1
) -> Dict[str, Any]:
    """
    异步DNS解析函数
    使用aiodns进行异步DNS查询
    返回包含响应时间和解析IP地址的字典
    """
    if HAS_AIODNS:
        return await _async_resolve_aiodns(dns_server, domain, timeout, retries)
    else:
        # aiodns 不可用，提示用户安装
        print_colored("错误: aiodns 模块不可用，无法进行DNS查询", Fore.RED)
        print_colored("请安装 aiodns 模块: pip install aiodns", Fore.YELLOW)
        return {"elapsed": None, "ips": [], "error": "aiodns模块不可用"}


async def _async_resolve_aiodns(
    dns_server: str, domain: str, timeout: float = 2.0, retries: int = 1
) -> Dict[str, Any]:
    """
    使用aiodns进行异步DNS解析
    返回包含响应时间和解析IP地址的字典
    """
    last_error = None
    for attempt in range(retries):
        try:
            resolver = aiodns.DNSResolver(nameservers=[dns_server])
            start_time = asyncio.get_event_loop().time()

            # 使用asyncio.wait_for添加超时控制
            try:
                result = await asyncio.wait_for(
                    resolver.query(domain, "A"), timeout=timeout
                )
                end_time = asyncio.get_event_loop().time()
                elapsed = end_time - start_time

                # 提取IP地址
                ips = []
                # 处理不同版本的aiodns返回类型
                if isinstance(result, list):
                    # aiodns 3.0+ 可能直接返回IP地址列表或DNSRecord对象列表
                    for item in result:
                        if isinstance(item, str):
                            # 直接是IP地址字符串
                            ips.append(item)
                        elif hasattr(item, "address"):
                            # DNSRecord对象
                            ips.append(item.address)
                        elif hasattr(item, "host"):
                            # 另一种可能的属性
                            ips.append(item.host)
                elif hasattr(result, "answer"):
                    # 旧版本aiodns的DNSResponse对象
                    for answer in result.answer:
                        if hasattr(answer, "address"):
                            ips.append(answer.address)
                elif hasattr(result, "address"):
                    # 单个DNSRecord对象
                    ips.append(result.address)

                # 短暂延迟避免请求过于密集
                await asyncio.sleep(0.05)
                return {"elapsed": elapsed, "ips": ips, "error": None}

            except asyncio.TimeoutError:
                error_msg = (
                    f"超时 (尝试 {attempt+1}/{retries}): {domain} @ {dns_server}"
                )
                print_colored(f"  {error_msg}", Fore.YELLOW)
                last_error = {
                    "elapsed": None,
                    "ips": [],
                    "error": "TIMEOUT",
                    "error_msg": error_msg,
                }
                if attempt < retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                continue

        except aiodns.error.DNSError as e:
            error_msg = str(e)
            if "NXDOMAIN" in error_msg:
                print_colored(f"  域名不存在: {domain} @ {dns_server}", Fore.YELLOW)
                error_type = "NXDOMAIN"
            elif "SERVFAIL" in error_msg:
                print_colored(f"  服务器失败: {domain} @ {dns_server}", Fore.YELLOW)
                error_type = "SERVFAIL"
            else:
                print_colored(
                    f"  DNS错误: {domain} @ {dns_server} - {error_msg}", Fore.RED
                )
                error_type = "DNS_ERROR"

            last_error = {
                "elapsed": None,
                "ips": [],
                "error": error_type,
                "error_msg": error_msg,
            }
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue

        except Exception as e:
            error_msg = f"未知错误: {domain} @ {dns_server} - {str(e)}"
            print_colored(f"  {error_msg}", Fore.RED)
            last_error = {
                "elapsed": None,
                "ips": [],
                "error": "UNKNOWN",
                "error_msg": error_msg,
            }
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue

    # 所有重试都失败
    if last_error:
        return last_error
    return {"elapsed": None, "ips": [], "error": "UNKNOWN", "error_msg": "未知错误"}


async def async_test_dns_server(
    dns_server: str,
    domains: List[str],
    num_tests: int,
    timeout: float,
    retries: int = 1,
    enable_http_test: bool = False,
    http_timeout: float = 10.0,
    max_http_concurrency: int = 5,
    max_redirects: int = 5,
    user_agent: str = "DNS-Benchmark/1.0",
    verify_ssl: bool = False,
) -> Dict:
    """
    异步测试单个DNS服务器对所有域名的解析性能
    可选启用HTTP性能测试以评估DNS返回IP的实际访问速度
    """
    # HTTP测试信号量，用于控制并发数
    http_semaphore = (
        asyncio.Semaphore(max_http_concurrency) if enable_http_test else None
    )

    # 收集所有解析到的IP地址（跨所有域名）
    all_ips_across_domains = set()

    results = {
        "dns_server": dns_server,
        "domain_stats": {},
        "all_times": [],
        "errors": [],
        "http_test_stats": (
            {
                "enabled": enable_http_test,
                "total_ips": 0,
                "tested_ips": 0,
                "successful_ips": 0,
                "failed_ips": 0,
                "errors": [],
            }
            if enable_http_test
            else None
        ),
    }

    print_colored(f"\n🔍 测试DNS服务器: {dns_server}", Fore.CYAN, Style.BRIGHT)

    total_queries = len(domains) * num_tests
    completed_queries = 0

    for domain_idx, domain in enumerate(domains):
        domain_times = []
        all_ips = set()  # 收集所有解析到的IP地址
        print_colored(
            f"  📡 域名 {domain_idx+1}/{len(domains)}: {domain}",
            Fore.WHITE,
            end="",
            flush=True,
        )

        # 为每个测试创建并发任务
        tasks = []
        for test_num in range(num_tests):
            task = async_resolve_domain(dns_server, domain, timeout, retries)
            tasks.append(task)

        # 并发执行所有测试
        try:
            query_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(query_results):
                completed_queries += 1
                progress = completed_queries / total_queries

                if isinstance(result, Exception):
                    print_colored(" ❌", Fore.RED, end="", flush=True)
                    results["errors"].append(
                        {"domain": domain, "test_num": i, "error": str(result)}
                    )
                    domain_times.append(None)
                elif isinstance(result, dict):
                    if result.get("error") is not None or result.get("elapsed") is None:
                        # DNS查询失败
                        print_colored(" ❌", Fore.RED, end="", flush=True)
                        error_msg = result.get(
                            "error_msg", result.get("error", "未知错误")
                        )
                        results["errors"].append(
                            {"domain": domain, "test_num": i, "error": error_msg}
                        )
                        domain_times.append(None)
                    else:
                        # DNS查询成功
                        elapsed = result["elapsed"]
                        ips = result.get("ips", [])
                        print_colored(
                            f" {elapsed*1000:.1f}ms", Fore.GREEN, end="", flush=True
                        )
                        domain_times.append(elapsed)

                        # 收集IP地址
                        for ip in ips:
                            if ip:  # 确保IP地址不为空
                                all_ips.add(ip)
                else:
                    # 未知结果类型（向后兼容）
                    print_colored(" ❌", Fore.RED, end="", flush=True)
                    domain_times.append(None)

                # 显示进度
                if (completed_queries % 5 == 0) or (completed_queries == total_queries):
                    progress_bar = get_progress_bar(progress)
                    print_colored(
                        f" {progress_bar}",
                        Fore.BLUE,
                        end="\r" if completed_queries < total_queries else "\n",
                    )

        except Exception as e:
            print_colored(f"  测试过程中发生错误: {str(e)}", Fore.RED)
            for _ in range(num_tests):
                domain_times.append(None)

        # 计算该域名的统计
        valid_times = [t for t in domain_times if t is not None]
        if valid_times:
            stats = {
                "min": min(valid_times),
                "max": max(valid_times),
                "avg": statistics.mean(valid_times),
                "std": statistics.stdev(valid_times) if len(valid_times) > 1 else 0,
                "success_rate": len(valid_times) / len(domain_times) * 100,
                "times": domain_times,
                "resolved_ips": list(all_ips),  # DNS解析到的IP地址列表
                "http_stats": {},  # HTTP测试统计，key为IP地址（待填充）
            }
        else:
            stats = {
                "min": None,
                "max": None,
                "avg": None,
                "std": None,
                "success_rate": 0,
                "times": domain_times,
                "resolved_ips": list(all_ips),  # DNS解析到的IP地址列表
                "http_stats": {},  # HTTP测试统计，key为IP地址（待填充）
            }

        results["domain_stats"][domain] = stats
        results["all_times"].extend(valid_times)

        # 将解析到的IP地址添加到全局集合
        for ip in all_ips:
            if ip:
                all_ips_across_domains.add(ip)

        # 显示域名统计结果
        if stats["avg"] is not None:
            color = (
                Fore.GREEN
                if stats["success_rate"] >= 80
                else Fore.YELLOW if stats["success_rate"] >= 50 else Fore.RED
            )
            print_colored(
                f"   | 平均: {stats['avg']*1000:.1f}ms, 成功率: {stats['success_rate']:.1f}%",
                color,
            )
        else:
            print_colored("   | 全部失败", Fore.RED)

    # 执行HTTP性能测试（如果启用）
    if enable_http_test and all_ips_across_domains:
        print_colored(
            f"\n🌐 开始HTTP性能测试 ({len(all_ips_across_domains)}个IP地址)",
            Fore.CYAN,
            Style.BRIGHT,
        )

        # 为每个域名测试其解析到的IP地址
        http_test_tasks = []
        for domain, domain_stats in results["domain_stats"].items():
            resolved_ips = domain_stats.get("resolved_ips", [])
            if not resolved_ips:
                continue

            for ip_address in resolved_ips:
                # 创建HTTP测试任务
                task = _test_ip_with_semaphore(
                    ip_address,
                    domain,
                    http_semaphore,
                    http_timeout,
                    max_redirects,
                    user_agent,
                    verify_ssl,
                )
                http_test_tasks.append((domain, ip_address, task))

        # 并发执行所有HTTP测试任务
        if http_test_tasks:
            http_results = []
            for domain, ip_address, task in http_test_tasks:
                try:
                    http_result = await task
                    http_results.append((domain, ip_address, http_result))
                except Exception as e:
                    error_msg = f"HTTP测试任务执行错误: {str(e)}"
                    print_colored(f"  ❌ {error_msg}", Fore.RED)
                    if results["http_test_stats"]:
                        results["http_test_stats"]["errors"].append(error_msg)

            # 处理HTTP测试结果
            for domain, ip_address, http_result in http_results:
                # 更新HTTP测试统计
                if results["http_test_stats"]:
                    results["http_test_stats"]["total_ips"] += 1
                    results["http_test_stats"]["tested_ips"] += 1
                    if http_result.get("success"):
                        results["http_test_stats"]["successful_ips"] += 1
                    else:
                        results["http_test_stats"]["failed_ips"] += 1

                # 将HTTP测试结果存储到对应域名的统计中
                if domain in results["domain_stats"]:
                    results["domain_stats"][domain]["http_stats"][
                        ip_address
                    ] = http_result

                    # 显示HTTP测试结果
                    if http_result.get("success"):
                        total_time = http_result.get("total_time")
                        if total_time:
                            print_colored(
                                f"  ✅ {domain} @ {ip_address}: {total_time*1000:.1f}ms, "
                                f"大小: {http_result.get('data_size', 0)} bytes",
                                Fore.GREEN,
                            )
                    else:
                        error_msg = http_result.get("error", "未知错误")
                        print_colored(
                            f"  ❌ {domain} @ {ip_address}: {error_msg}", Fore.RED
                        )

        print_colored("🌐 HTTP性能测试完成", Fore.CYAN, Style.BRIGHT)

    return results


async def _test_ip_with_semaphore(
    ip_address: str,
    domain: str,
    http_semaphore: asyncio.Semaphore,
    http_timeout: float,
    max_redirects: int,
    user_agent: str,
    verify_ssl: bool,
) -> Dict[str, Any]:
    """
    使用信号量控制并发的HTTP测试包装函数
    """
    if http_semaphore:
        async with http_semaphore:
            return await async_test_http_performance(
                ip_address,
                domain,
                http_timeout,
                max_redirects,
                user_agent,
                verify_ssl,
            )
    else:
        return await async_test_http_performance(
            ip_address,
            domain,
            http_timeout,
            max_redirects,
            user_agent,
            verify_ssl,
        )


async def async_test_http_performance(
    ip_address: str,
    domain: str,
    timeout: float = 10.0,
    max_redirects: int = 5,
    user_agent: str = "DNS-Benchmark/1.0",
    verify_ssl: bool = False,
) -> Dict[str, Any]:
    """
    异步测试指定IP地址的HTTP性能

    Args:
        ip_address: 要测试的IP地址
        domain: 原始域名（用于Host头）
        timeout: 超时时间（秒）
        max_redirects: 最大重定向次数
        user_agent: User-Agent字符串
        verify_ssl: 是否验证SSL证书

    Returns:
        包含HTTP性能指标的字典
    """
    if not HAS_AIOHTTP:
        print_colored("错误: aiohttp 模块不可用，无法进行HTTP测试", Fore.RED)
        print_colored("请安装 aiohttp 模块: pip install aiohttp", Fore.YELLOW)
        return {
            "ip_address": ip_address,
            "connection_time": None,
            "ttfb": None,
            "total_time": None,
            "data_size": None,
            "status_code": None,
            "success": False,
            "error": "aiohttp模块不可用",
            "redirects": [],
        }

    try:
        from urllib.parse import urljoin, urlparse
        from aiohttp import ClientSession, ClientTimeout, TCPConnector

        start_time = asyncio.get_event_loop().time()
        redirects = []
        current_url = f"https://{ip_address}/"

        # 创建TCP连接器（用于SSL验证设置）
        connector = TCPConnector(ssl=verify_ssl)
        async with ClientSession(connector=connector) as session:
            for redirect_count in range(max_redirects + 1):  # 包括初始请求
                if redirect_count >= max_redirects:
                    raise HTTPRedirectError(f"重定向次数超过最大限制: {max_redirects}")

                # 测量连接时间
                conn_start = asyncio.get_event_loop().time()

                try:
                    # 解析当前URL获取主机名，用于Host头
                    parsed_url = urlparse(current_url)
                    host_header = parsed_url.netloc if parsed_url.netloc else domain

                    async with session.get(
                        current_url,
                        headers={
                            "Host": host_header,
                            "User-Agent": user_agent,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept-Encoding": "gzip, deflate",
                            "Connection": "close",
                        },
                        timeout=ClientTimeout(total=timeout),
                        allow_redirects=False,  # 手动处理重定向
                    ) as response:
                        conn_time = asyncio.get_event_loop().time() - conn_start

                        # 读取响应体
                        content = await response.read()
                        end_time = asyncio.get_event_loop().time()

                        # 检查是否需要重定向
                        if response.status in (301, 302, 303, 307, 308):
                            location = response.headers.get("Location")
                            if not location:
                                raise HTTPRedirectError(f"重定向响应缺少Location头: {response.status}")
                            # 检测重定向循环
                            if current_url in redirects:
                                raise HTTPRedirectError(f"检测到重定向循环: {current_url}")
                            redirects.append(current_url)
                            # 使用urljoin正确处理相对路径重定向
                            current_url = urljoin(current_url, location)
                            continue  # 处理重定向

                        # 成功获取最终响应
                        return {
                            "ip_address": ip_address,
                            "connection_time": conn_time,
                            # "ttfb": (
                            #     response._response._start_time - conn_start
                            #     if hasattr(response._response, "_start_time")
                            #     and response._response._start_time is not None
                            #     else None
                            # ),
                            "total_time": end_time - start_time,
                            "data_size": len(content),
                            "status_code": response.status,
                            "success": response.status < 400,
                            "error": (
                                None
                                if response.status < 400
                                else f"HTTP {response.status}"
                            ),
                            "redirects": redirects,
                        }

                except asyncio.TimeoutError:
                    raise HTTPTimeoutError(f"HTTP请求超时: {timeout}秒")
                except aiohttp.ClientConnectorError as e:
                    raise HTTPConnectionError(f"连接错误: {str(e)}")
                except aiohttp.ClientSSLError as e:
                    raise HTTPSSLError(f"SSL错误: {str(e)}")
                except Exception as e:
                    raise HTTPTestError(f"HTTP请求错误: {str(e)}")

        # 理论上不会执行到这里
        raise HTTPTestError("未知错误")

    except (
        HTTPTimeoutError,
        HTTPConnectionError,
        HTTPSSLError,
        HTTPRedirectError,
        HTTPStatusCodeError,
        HTTPTestError,
    ) as e:
        return {
            "ip_address": ip_address,
            "connection_time": None,
            "ttfb": None,
            "total_time": None,
            "data_size": None,
            "status_code": None,
            "success": False,
            "error": str(e),
            "redirects": redirects,
        }
    except Exception as e:
        return {
            "ip_address": ip_address,
            "connection_time": None,
            "ttfb": None,
            "total_time": None,
            "data_size": None,
            "status_code": None,
            "success": False,
            "error": f"未知错误: {str(e)}",
            "redirects": redirects,
        }


async def async_test_all_dns_servers(
    dns_servers: List[str],
    domains: List[str],
    num_tests: int,
    timeout: float,
    retries: int = 1,
    enable_http_test: bool = False,
    http_timeout: float = 10.0,
    max_http_concurrency: int = 5,
    max_redirects: int = 5,
    user_agent: str = "DNS-Benchmark/1.0",
    verify_ssl: bool = False,
) -> List[Dict]:
    """
    并发测试所有DNS服务器
    可选启用HTTP性能测试以评估DNS返回IP的实际访问速度
    """
    print_colored(
        f"\n🚀 开始并发测试 {len(dns_servers)} 个DNS服务器...", Fore.CYAN, Style.BRIGHT
    )

    if enable_http_test:
        print_colored("🌐 HTTP性能测试已启用", Fore.YELLOW, Style.BRIGHT)

    tasks = []
    for dns_server in dns_servers:
        task = async_test_dns_server(
            dns_server,
            domains,
            num_tests,
            timeout,
            retries,
            enable_http_test,
            http_timeout,
            max_http_concurrency,
            max_redirects,
            user_agent,
            verify_ssl,
        )
        tasks.append(task)

    # 并发执行所有DNS服务器测试
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理可能出现的异常
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print_colored(
                f"❌ DNS服务器 {dns_servers[i]} 测试失败: {str(result)}", Fore.RED
            )
            # 创建失败的结果记录
            final_results.append(
                {
                    "dns_server": dns_servers[i],
                    "domain_stats": {},
                    "all_times": [],
                    "errors": [str(result)],
                }
            )
        else:
            final_results.append(result)

    return final_results


# ============================================================================
# DNSBenchmark 类
# ============================================================================


class DNSBenchmark:
    """
    DNS性能测试基准类
    封装所有测试逻辑和配置
    """

    def __init__(self, retries: int = 1):
        """
        初始化DNS基准测试器

        Args:
            retries: 查询失败时的重试次数
        """
        self.retries = retries
        self.results = []
        self.dns_servers = []
        self.domains = []
        self.num_tests = 3
        self.timeout = 2.0
        self.start_time = None
        self.end_time = None

        # HTTP测试相关配置
        self.enable_http_test = False
        self.http_timeout = 10.0
        self.max_http_concurrency = 5
        self.max_redirects = 5
        self.user_agent = "DNS-Benchmark/1.0"
        self.verify_ssl = False

        if HAS_AIODNS:
            print_colored("✅ 使用异步模式进行测试", Fore.GREEN)
        else:
            print_colored("❌ aiodns不可用，无法进行异步DNS测试", Fore.RED)
            print_colored("请安装 aiodns 模块: pip install aiodns", Fore.YELLOW)

    def set_config(
        self,
        dns_servers: List[str],
        domains: List[str],
        num_tests: int = 3,
        timeout: float = 2.0,
        enable_http_test: bool = False,
        http_timeout: float = 10.0,
        max_http_concurrency: int = 5,
        max_redirects: int = 5,
        user_agent: str = "DNS-Benchmark/1.0",
        verify_ssl: bool = False,
    ) -> None:
        """设置测试配置"""
        self.dns_servers = dns_servers
        self.domains = domains
        self.num_tests = num_tests
        self.timeout = timeout
        self.enable_http_test = enable_http_test
        self.http_timeout = http_timeout
        self.max_http_concurrency = max_http_concurrency
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl

    async def run_async(self) -> List[Dict]:
        """异步运行基准测试"""
        self.start_time = time.time()
        print_colored(
            f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Fore.CYAN
        )

        # 检查aiodns是否可用
        if not HAS_AIODNS:
            raise RuntimeError(
                "aiodns 模块不可用，无法进行异步DNS测试。请安装 aiodns: pip install aiodns"
            )

        self.results = await async_test_all_dns_servers(
            self.dns_servers,
            self.domains,
            self.num_tests,
            self.timeout,
            self.retries,
            self.enable_http_test,
            self.http_timeout,
            self.max_http_concurrency,
            self.max_redirects,
            self.user_agent,
            self.verify_ssl,
        )

        self.end_time = time.time()
        elapsed = self.end_time - self.start_time
        print_colored(
            f"\n✅ 测试完成! 总耗时: {elapsed:.2f}秒", Fore.GREEN, Style.BRIGHT
        )

        return self.results

    def calculate_overall_statistics(self) -> Dict:
        """计算总体统计信息"""
        if not self.results:
            return {}

        total_queries = len(self.dns_servers) * len(self.domains) * self.num_tests
        successful_queries = 0
        all_times = []

        for result in self.results:
            successful_queries += len(result["all_times"])
            all_times.extend(result["all_times"])

        if all_times:
            return {
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "success_rate": (successful_queries / total_queries) * 100,
                "overall_avg": statistics.mean(all_times),
                "overall_min": min(all_times),
                "overall_max": max(all_times),
                "overall_std": statistics.stdev(all_times) if len(all_times) > 1 else 0,
                "total_time": self.end_time - self.start_time if self.end_time else 0,
            }
        else:
            return {
                "total_queries": total_queries,
                "successful_queries": 0,
                "success_rate": 0,
                "overall_avg": None,
                "overall_min": None,
                "overall_max": None,
                "overall_std": None,
                "total_time": self.end_time - self.start_time if self.end_time else 0,
            }

    def print_detailed_report(self) -> None:
        """打印详细报告"""
        stats = self.calculate_overall_statistics()
        if not stats:
            return

        print_colored("\n" + "=" * 90, Fore.CYAN)
        print_colored("📊 DNS性能测试详细报告", Fore.CYAN, Style.BRIGHT)
        print_colored("=" * 90, Fore.CYAN)

        print_colored("\n📈 总体统计:", Fore.WHITE)
        print_colored(f"   总查询次数: {stats['total_queries']}", Fore.WHITE)
        print_colored(f"   成功查询: {stats['successful_queries']}", Fore.GREEN)
        print_colored(
            f"   失败查询: {stats['total_queries'] - stats['successful_queries']}",
            Fore.RED,
        )
        print_colored(
            f"   成功率: {stats['success_rate']:.1f}%",
            (
                Fore.GREEN
                if stats["success_rate"] >= 80
                else Fore.YELLOW if stats["success_rate"] >= 50 else Fore.RED
            ),
        )

        if stats["overall_avg"] is not None:
            print_colored(
                f"   平均响应时间: {stats['overall_avg']*1000:.1f}ms", Fore.WHITE
            )
            print_colored(f"   最快响应: {stats['overall_min']*1000:.1f}ms", Fore.GREEN)
            print_colored(
                f"   最慢响应: {stats['overall_max']*1000:.1f}ms", Fore.YELLOW
            )
            if stats["overall_std"] is not None:
                print_colored(
                    f"   响应时间标准差: {stats['overall_std']*1000:.1f}ms", Fore.WHITE
                )

        print_colored(f"   总测试时间: {stats['total_time']:.2f}秒", Fore.WHITE)

        # 错误统计
        self._print_error_statistics()

    def _print_error_statistics(self) -> None:
        """打印错误统计"""
        if not self.results:
            return

        error_stats = {
            "timeout": 0,
            "nxdomain": 0,
            "no_answer": 0,
            "network": 0,
            "other": 0,
        }

        total_errors = 0

        for result in self.results:
            if "errors" in result:
                for error_info in result["errors"]:
                    error_msg = error_info.get("error", "").lower()
                    if "timeout" in error_msg:
                        error_stats["timeout"] += 1
                    elif "nxdomain" in error_msg or "domain not found" in error_msg:
                        error_stats["nxdomain"] += 1
                    elif "no answer" in error_msg or "no response" in error_msg:
                        error_stats["no_answer"] += 1
                    elif "network" in error_msg or "connection" in error_msg:
                        error_stats["network"] += 1
                    else:
                        error_stats["other"] += 1
                    total_errors += 1

        if total_errors > 0:
            print_colored("\n🔍 错误分析:", Fore.WHITE)
            print_colored(f"   总错误数: {total_errors}", Fore.YELLOW)

            if error_stats["timeout"] > 0:
                print_colored(
                    f"   超时错误: {error_stats['timeout']} ({error_stats['timeout']/total_errors*100:.1f}%)",
                    Fore.YELLOW,
                )
            if error_stats["nxdomain"] > 0:
                print_colored(
                    f"   域名不存在: {error_stats['nxdomain']} ({error_stats['nxdomain']/total_errors*100:.1f}%)",
                    Fore.YELLOW,
                )
            if error_stats["no_answer"] > 0:
                print_colored(
                    f"   无应答错误: {error_stats['no_answer']} ({error_stats['no_answer']/total_errors*100:.1f}%)",
                    Fore.YELLOW,
                )
            if error_stats["network"] > 0:
                print_colored(
                    f"   网络错误: {error_stats['network']} ({error_stats['network']/total_errors*100:.1f}%)",
                    Fore.RED,
                )
            if error_stats["other"] > 0:
                print_colored(
                    f"   其他错误: {error_stats['other']} ({error_stats['other']/total_errors*100:.1f}%)",
                    Fore.RED,
                )

    def _print_http_test_report(self) -> None:
        """打印HTTP测试报告"""
        if not self.results or not self.enable_http_test:
            return

        print_colored("\n" + "=" * 90, Fore.CYAN)
        print_colored("🌐 HTTP性能测试详细报告", Fore.CYAN, Style.BRIGHT)
        print_colored("=" * 90, Fore.CYAN)

        # 总体HTTP统计
        total_ips = 0
        tested_ips = 0
        successful_ips = 0
        failed_ips = 0
        http_times = []
        connection_times = []
        ttfb_times = []
        total_data_size = 0

        # HTTP错误分类统计
        http_error_stats = {
            "connection": 0,
            "timeout": 0,
            "ssl": 0,
            "redirect": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        }

        for result in self.results:
            http_test_stats = result.get("http_test_stats")
            if not http_test_stats or not http_test_stats.get("enabled"):
                continue

            total_ips += http_test_stats.get("total_ips", 0)
            tested_ips += http_test_stats.get("tested_ips", 0)
            successful_ips += http_test_stats.get("successful_ips", 0)
            failed_ips += http_test_stats.get("failed_ips", 0)

            # 收集HTTP时间数据和错误统计
            for _, domain_stats in result["domain_stats"].items():
                http_stats_dict = domain_stats.get("http_stats", {})
                for _, http_result in http_stats_dict.items():
                    if http_result.get("success"):
                        total_time = http_result.get("total_time")
                        conn_time = http_result.get("connection_time")
                        ttfb_time = http_result.get("ttfb")
                        data_size = http_result.get("data_size")

                        if total_time is not None:
                            http_times.append(total_time)
                        if conn_time is not None:
                            connection_times.append(conn_time)
                        if ttfb_time is not None:
                            ttfb_times.append(ttfb_time)
                        if data_size is not None:
                            total_data_size += data_size
                    else:
                        # 错误分类
                        error_msg = http_result.get("error", "").lower()
                        if "connection" in error_msg:
                            http_error_stats["connection"] += 1
                        elif "timeout" in error_msg:
                            http_error_stats["timeout"] += 1
                        elif "ssl" in error_msg:
                            http_error_stats["ssl"] += 1
                        elif "redirect" in error_msg:
                            http_error_stats["redirect"] += 1
                        elif "http 4" in error_msg:
                            http_error_stats["4xx"] += 1
                        elif "http 5" in error_msg:
                            http_error_stats["5xx"] += 1
                        else:
                            http_error_stats["other"] += 1

        # 显示总体统计
        print_colored("\n📈 HTTP总体统计:", Fore.WHITE)
        print_colored(f"   总IP地址数: {total_ips}", Fore.WHITE)
        print_colored(f"   已测试IP数: {tested_ips}", Fore.GREEN)
        print_colored(f"   成功测试数: {successful_ips}", Fore.GREEN)
        print_colored(f"   失败测试数: {failed_ips}", Fore.RED)

        if total_ips > 0:
            success_rate = (successful_ips / total_ips) * 100
            color = (
                Fore.GREEN
                if success_rate >= 80
                else Fore.YELLOW if success_rate >= 50 else Fore.RED
            )
            print_colored(f"   HTTP成功率: {success_rate:.1f}%", color)

        # 显示时间统计
        if http_times:
            avg_http_time = statistics.mean(http_times)
            min_http_time = min(http_times)
            max_http_time = max(http_times)
            print_colored("\n⏱️  HTTP时间统计:", Fore.WHITE)
            print_colored(f"   平均总时间: {avg_http_time*1000:.1f}ms", Fore.WHITE)
            print_colored(f"   最短总时间: {min_http_time*1000:.1f}ms", Fore.GREEN)
            print_colored(f"   最长总时间: {max_http_time*1000:.1f}ms", Fore.YELLOW)

        if connection_times:
            avg_conn_time = statistics.mean(connection_times)
            print_colored(f"   平均连接时间: {avg_conn_time*1000:.1f}ms", Fore.WHITE)

        if ttfb_times:
            avg_ttfb_time = statistics.mean(ttfb_times)
            print_colored(f"   平均TTFB: {avg_ttfb_time*1000:.1f}ms", Fore.WHITE)

        if total_data_size > 0:
            data_size_mb = total_data_size / (1024 * 1024)
            print_colored(f"   总下载数据: {data_size_mb:.2f} MB", Fore.CYAN)

        # 显示错误统计
        total_errors = sum(http_error_stats.values())
        if total_errors > 0:
            print_colored("\n🔍 HTTP错误分析:", Fore.WHITE)
            print_colored(f"   总错误数: {total_errors}", Fore.YELLOW)

            for error_type, count in http_error_stats.items():
                if count > 0:
                    percentage = (count / total_errors) * 100
                    if error_type in ["connection", "timeout", "ssl"]:
                        color = Fore.RED
                    elif error_type in ["4xx", "5xx"]:
                        color = Fore.YELLOW
                    else:
                        color = Fore.WHITE

                    error_type_name = {
                        "connection": "连接错误",
                        "timeout": "超时错误",
                        "ssl": "SSL错误",
                        "redirect": "重定向错误",
                        "4xx": "客户端错误(4xx)",
                        "5xx": "服务器错误(5xx)",
                        "other": "其他错误",
                    }.get(error_type, error_type)

                    print_colored(
                        f"   {error_type_name}: {count} ({percentage:.1f}%)", color
                    )

        # 按DNS服务器显示详细HTTP结果
        print_colored("\n📋 各DNS服务器HTTP测试结果:", Fore.WHITE)
        for result in self.results:
            http_test_stats = result.get("http_test_stats")
            if not http_test_stats or not http_test_stats.get("enabled"):
                continue

            dns_server = result["dns_server"]
            total_ips_server = http_test_stats.get("total_ips", 0)
            successful_ips_server = http_test_stats.get("successful_ips", 0)
            failed_ips_server = http_test_stats.get("failed_ips", 0)

            if total_ips_server > 0:
                success_rate_server = (successful_ips_server / total_ips_server) * 100
                color = (
                    Fore.GREEN
                    if success_rate_server >= 80
                    else Fore.YELLOW if success_rate_server >= 50 else Fore.RED
                )
                print_colored(
                    f"   {dns_server}: {successful_ips_server}成功/{failed_ips_server}失败/{total_ips_server}总计 ({success_rate_server:.1f}%)",
                    color,
                )

    def save_results_to_file(self, filename: str = "dns_benchmark_report.txt") -> bool:
        """保存结果到文件"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("DNS性能测试详细报告\n")
                f.write("=" * 90 + "\n")
                f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"DNS服务器: {', '.join(self.dns_servers)}\n")
                f.write(f"测试域名: {', '.join(self.domains)}\n")
                f.write(f"每个域名测试次数: {self.num_tests}\n")
                f.write(f"超时设置: {self.timeout}秒\n")
                f.write("使用异步模式: 是\n")
                f.write("=" * 90 + "\n\n")

                stats = self.calculate_overall_statistics()
                f.write("总体统计:\n")
                f.write(f"  总查询次数: {stats['total_queries']}\n")
                f.write(f"  成功查询: {stats['successful_queries']}\n")
                f.write(f"  成功率: {stats['success_rate']:.1f}%\n")
                if stats["overall_avg"] is not None:
                    f.write(f"  平均响应时间: {stats['overall_avg']*1000:.1f}ms\n")
                    f.write(f"  最快响应: {stats['overall_min']*1000:.1f}ms\n")
                    f.write(f"  最慢响应: {stats['overall_max']*1000:.1f}ms\n")
                    if stats["overall_std"] is not None:
                        f.write(
                            f"  响应时间标准差: {stats['overall_std']*1000:.1f}ms\n"
                        )
                f.write(f"  总测试时间: {stats['total_time']:.2f}秒\n\n")

                f.write("各DNS服务器详细结果:\n")
                f.write("=" * 90 + "\n")
                for result in self.results:
                    f.write(f"\nDNS服务器: {result['dns_server']}\n")
                    f.write("-" * 90 + "\n")
                    for domain, domain_stats in result["domain_stats"].items():
                        f.write(f"  域名: {domain}\n")
                        if domain_stats["avg"] is not None:
                            f.write(f"    平均: {domain_stats['avg']*1000:.2f}ms\n")
                            f.write(f"    最短: {domain_stats['min']*1000:.2f}ms\n")
                            f.write(f"    最长: {domain_stats['max']*1000:.2f}ms\n")
                            f.write(f"    标准差: {domain_stats['std']*1000:.2f}ms\n")
                            f.write(
                                f"    成功率: {domain_stats['success_rate']:.1f}%\n"
                            )
                            times_str = ", ".join(
                                [
                                    f"{t*1000:.1f}ms" if t is not None else "失败"
                                    for t in domain_stats["times"]
                                ]
                            )
                            f.write(f"    详细结果: [{times_str}]\n")
                        else:
                            f.write("    状态: 全部解析失败\n")
                        f.write("\n")

            print_colored(f"📄 详细报告已保存到: {filename}", Fore.GREEN)
            return True

        except Exception as e:
            print_colored(f"❌ 保存报告失败: {str(e)}", Fore.RED)
            return False


def print_summary_table(
    results: List[Dict],
    num_tests: int,
    domains: List[str],
    enable_http_test: bool = False,
):
    """
    打印汇总结果表格
    修复统计计算问题，使用None代替float('inf')
    支持HTTP测试结果显示和综合排名
    """
    print_colored("\n" + "=" * 90, Fore.CYAN)
    print_colored("📊 DNS服务器性能测试汇总", Fore.CYAN, Style.BRIGHT)
    print_colored("=" * 90, Fore.CYAN)

    # 准备汇总数据
    table_data = []
    for result in results:
        dns_server = result["dns_server"]
        all_times = result["all_times"]

        # 计算成功率
        total_queries = num_tests * len(domains)
        successful_queries = len(all_times)
        success_rate = (
            (successful_queries / total_queries * 100) if total_queries > 0 else 0
        )

        # 计算统计信息
        if all_times:
            try:
                avg_time = statistics.mean(all_times)
                min_time = min(all_times)
                max_time = max(all_times)
            except statistics.StatisticsError:
                avg_time = None
                min_time = None
                max_time = None
        else:
            avg_time = None
            min_time = None
            max_time = None

        # 计算成功域名数
        successful_domains = 0
        for domain, stats in result["domain_stats"].items():
            if stats.get("avg") is not None:
                successful_domains += 1

        # HTTP测试统计（如果启用）
        http_stats = None
        combined_score = None
        if enable_http_test and result.get("http_test_stats"):
            http_test_stats = result["http_test_stats"]
            http_enabled = http_test_stats.get("enabled", False)
            http_success_rate = 0.0
            avg_http_time = None
            avg_connection_time = None
            avg_ttfb = None
            total_data_size = 0
            http_test_count = 0

            if http_enabled:
                # 计算HTTP测试平均指标
                http_times = []
                connection_times = []
                ttfb_times = []

                for domain, domain_stats in result["domain_stats"].items():
                    http_stats_dict = domain_stats.get("http_stats", {})
                    for _, http_result in http_stats_dict.items():
                        if http_result.get("success"):
                            total_time = http_result.get("total_time")
                            conn_time = http_result.get("connection_time")
                            ttfb_time = http_result.get("ttfb")
                            data_size = http_result.get("data_size")

                            if total_time is not None:
                                http_times.append(total_time)
                            if conn_time is not None:
                                connection_times.append(conn_time)
                            if ttfb_time is not None:
                                ttfb_times.append(ttfb_time)
                            if data_size is not None:
                                total_data_size += data_size

                            http_test_count += 1

                # 计算统计
                if http_times:
                    avg_http_time = statistics.mean(http_times)
                if connection_times:
                    avg_connection_time = statistics.mean(connection_times)
                if ttfb_times:
                    avg_ttfb = statistics.mean(ttfb_times)

                total_ips = http_test_stats.get("total_ips", 0)
                successful_ips = http_test_stats.get("successful_ips", 0)
                if total_ips > 0:
                    http_success_rate = (successful_ips / total_ips) * 100

            http_stats = {
                "enabled": http_enabled,
                "success_rate": http_success_rate,
                "avg_total_time": avg_http_time,
                "avg_connection_time": avg_connection_time,
                "avg_ttfb": avg_ttfb,
                "total_data_size": total_data_size,
                "total_tests": http_test_count,
                "successful_tests": http_test_stats.get("successful_ips", 0),
                "failed_tests": http_test_stats.get("failed_ips", 0),
            }

            # 计算综合得分（DNS占40%，HTTP占60%）
            if avg_time is not None and http_stats["enabled"]:
                # DNS得分（响应时间越小越好，成功率越高越好）
                dns_time_score = max(
                    0, min(1, 1.0 - (avg_time / 5.0))
                )  # 假设5秒为最大可接受时间
                dns_success_score = success_rate / 100.0
                dns_score = (
                    dns_time_score * 0.7 + dns_success_score * 0.3
                )  # 时间权重70%，成功率30%

                # HTTP得分
                http_time_score = 0
                http_success_score = http_success_rate / 100.0

                if avg_http_time is not None:
                    http_time_score = max(
                        0, min(1, 1.0 - (avg_http_time / 30.0))
                    )  # 假设30秒为最大可接受时间

                http_score = (
                    http_time_score * 0.5 + http_success_score * 0.5
                )  # 时间权重50%，成功率50%

                # 综合得分（DNS占40%，HTTP占60%）
                combined_score = dns_score * 0.4 + http_score * 0.6

        table_data.append(
            {
                "dns_server": dns_server,
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "success_rate": success_rate,
                "total_domains": len(domains),
                "successful_domains": successful_domains,
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "http_stats": http_stats,
                "combined_score": combined_score,
            }
        )

    # 排序逻辑
    def sort_key(x):
        # 如果启用了HTTP测试且有综合得分，按综合得分排序（得分越高越好）
        if enable_http_test and x.get("combined_score") is not None:
            score = x["combined_score"]
            return (
                -score,
                x["avg_time"] if x["avg_time"] is not None else float("inf"),
            )

        # 否则按DNS平均时间排序（时间越短越好）
        avg = x["avg_time"]
        if avg is None:
            return (float("inf"), -x["success_rate"])
        return (avg, -x["success_rate"])

    table_data.sort(key=sort_key)

    # 打印表格
    if HAS_TABULATE:
        # 使用tabulate输出表格
        if enable_http_test:
            # 扩展表格头以包含HTTP测试信息
            headers = [
                "DNS服务器",
                "DNS平均",
                "DNS最短",
                "DNS最长",
                "DNS成功率",
                "可用域名",
                "HTTP成功率",
                "HTTP平均",
                "综合得分",
            ]
        else:
            headers = [
                "DNS服务器",
                "平均耗时",
                "最短耗时",
                "最长耗时",
                "成功率",
                "可用域名",
            ]
        rows = []

        for row in table_data:
            if row["avg_time"] is not None:
                avg_str = f"{row['avg_time']*1000:.1f}ms"
                min_str = f"{row['min_time']*1000:.1f}ms"
                max_str = f"{row['max_time']*1000:.1f}ms"
            else:
                avg_str = "失败"
                min_str = "-"
                max_str = "-"

            if enable_http_test:
                # 有HTTP测试的行
                http_stats = row.get("http_stats")
                if http_stats and http_stats.get("enabled"):
                    http_success_rate = http_stats.get("success_rate", 0)
                    http_avg_time = http_stats.get("avg_total_time")

                    if http_avg_time is not None:
                        http_avg_str = f"{http_avg_time*1000:.1f}ms"
                    else:
                        http_avg_str = "-"

                    # 综合得分
                    combined_score = row.get("combined_score")
                    if combined_score is not None:
                        combined_str = f"{combined_score:.3f}"
                    else:
                        combined_str = "-"
                else:
                    http_avg_str = "-"
                    combined_str = "-"
                    http_success_rate = 0

                rows.append(
                    [
                        row["dns_server"],
                        avg_str,
                        min_str,
                        max_str,
                        f"{row['success_rate']:.1f}%",
                        f"{row['successful_domains']}/{row['total_domains']}",
                        f"{http_success_rate:.1f}%" if http_success_rate > 0 else "-",
                        http_avg_str,
                        combined_str,
                    ]
                )
            else:
                # 无HTTP测试的行
                rows.append(
                    [
                        row["dns_server"],
                        avg_str,
                        min_str,
                        max_str,
                        f"{row['success_rate']:.1f}%",
                        f"{row['successful_domains']}/{row['total_domains']}",
                    ]
                )

        print(tabulate(rows, headers=headers, tablefmt="grid"))

    else:
        # tabulate 不可用，提示用户安装
        print_colored("=" * 70, Fore.YELLOW)
        print_colored("警告: 缺少表格输出模块", Fore.YELLOW, Style.BRIGHT)
        print_colored("=" * 70, Fore.YELLOW)
        print_colored("\n未找到模块: tabulate", Fore.YELLOW)
        print_colored("\n请安装所需模块:", Fore.CYAN)
        print_colored("  pip install tabulate", Fore.GREEN)
        print_colored("\n安装后重新运行程序以获得更好的表格显示效果。", Fore.CYAN)

        # 仍然显示简单的结果摘要
        print_colored("\n" + "=" * 90, Fore.CYAN)
        if enable_http_test:
            print_colored("测试结果摘要（DNS+HTTP综合）:", Fore.CYAN, Style.BRIGHT)
        else:
            print_colored("测试结果摘要:", Fore.CYAN, Style.BRIGHT)
        print_colored("=" * 90, Fore.CYAN)

        for row in table_data:
            if row["avg_time"] is not None:
                if enable_http_test:
                    http_stats = row.get("http_stats")
                    combined_score = row.get("combined_score")
                    if (
                        http_stats
                        and http_stats.get("enabled")
                        and combined_score is not None
                    ):
                        http_success_rate = http_stats.get("success_rate", 0)
                        http_avg_time = http_stats.get("avg_total_time")

                        if http_avg_time is not None:
                            http_str = f", HTTP: {http_avg_time*1000:.1f}ms ({http_success_rate:.1f}%), 综合: {combined_score:.3f}"
                        else:
                            http_str = f", HTTP: - ({http_success_rate:.1f}%), 综合: {combined_score:.3f}"
                    elif http_stats and http_stats.get("enabled"):
                        http_success_rate = http_stats.get("success_rate", 0)
                        http_str = f", HTTP成功率: {http_success_rate:.1f}%"
                    else:
                        http_str = ", HTTP: 未测试"

                    print_colored(
                        f"{row['dns_server']}: DNS: {row['avg_time']*1000:.1f}ms ({row['success_rate']:.1f}%){http_str}",
                        (
                            Fore.GREEN
                            if row["success_rate"] >= 80
                            else Fore.YELLOW if row["success_rate"] >= 50 else Fore.RED
                        ),
                    )
                else:
                    print_colored(
                        f"{row['dns_server']}: 平均 {row['avg_time']*1000:.1f}ms, 成功率 {row['success_rate']:.1f}%",
                        (
                            Fore.GREEN
                            if row["success_rate"] >= 80
                            else Fore.YELLOW if row["success_rate"] >= 50 else Fore.RED
                        ),
                    )
            else:
                print_colored(f"{row['dns_server']}: ❌ 失败", Fore.RED)

    # 打印推荐
    print_colored("\n" + "=" * 90, Fore.CYAN)
    if enable_http_test:
        print_colored(
            "🏆 综合推荐DNS服务器（DNS+HTTP性能综合排名）:", Fore.CYAN, Style.BRIGHT
        )
    else:
        print_colored(
            "🏆 推荐DNS服务器（按平均响应时间和稳定性排序）:", Fore.CYAN, Style.BRIGHT
        )
    print_colored("=" * 90, Fore.CYAN)

    recommendations = 0
    for i, row in enumerate(table_data, 1):
        # 判断是否可推荐
        recommendable = False

        if enable_http_test:
            # HTTP测试模式：要求有DNS成功结果，且HTTP测试已启用或有综合得分
            http_stats = row.get("http_stats")
            if row["avg_time"] is not None and row["success_rate"] >= 50:
                if http_stats and http_stats.get("enabled"):
                    # 有HTTP测试数据，检查成功率
                    http_success_rate = http_stats.get("success_rate", 0)
                    if http_success_rate >= 30:  # HTTP成功率至少30%
                        recommendable = True
                else:
                    # 没有HTTP测试数据，仅基于DNS推荐
                    recommendable = True
        else:
            # 仅DNS测试模式：要求有DNS成功结果且成功率>=50%
            if row["avg_time"] is not None and row["success_rate"] >= 50:
                recommendable = True

        if recommendable:
            color = Fore.GREEN if row["success_rate"] >= 80 else Fore.YELLOW
            if enable_http_test:
                http_stats = row.get("http_stats")
                combined_score = row.get("combined_score")
                if (
                    http_stats
                    and http_stats.get("enabled")
                    and combined_score is not None
                ):
                    http_success_rate = http_stats.get("success_rate", 0)
                    http_avg_time = http_stats.get("avg_total_time")

                    if http_avg_time is not None:
                        print_colored(
                            f"{i}. {row['dns_server']} - 综合得分: {combined_score:.3f}, "
                            f"DNS: {row['avg_time']*1000:.1f}ms ({row['success_rate']:.1f}%), "
                            f"HTTP: {http_avg_time*1000:.1f}ms ({http_success_rate:.1f}%)",
                            color,
                        )
                    else:
                        print_colored(
                            f"{i}. {row['dns_server']} - 综合得分: {combined_score:.3f}, "
                            f"DNS: {row['avg_time']*1000:.1f}ms ({row['success_rate']:.1f}%), "
                            f"HTTP: - ({http_success_rate:.1f}%)",
                            color,
                        )
                else:
                    # 有DNS数据但没有HTTP测试数据或综合得分
                    print_colored(
                        f"{i}. {row['dns_server']} - DNS: {row['avg_time']*1000:.1f}ms, 成功率 {row['success_rate']:.1f}% (无HTTP测试数据)",
                        color,
                    )
            else:
                # 仅DNS模式
                print_colored(
                    f"{i}. {row['dns_server']} - 平均 {row['avg_time']*1000:.1f}ms, 成功率 {row['success_rate']:.1f}%",
                    color,
                )
            recommendations += 1
            if recommendations >= 3:
                break

    if recommendations == 0:
        if enable_http_test:
            print_colored(
                "⚠️  没有找到同时满足DNS和HTTP性能要求的DNS服务器推荐", Fore.YELLOW
            )
        else:
            print_colored("⚠️  没有找到可靠的DNS服务器推荐", Fore.YELLOW)

    # 打印详细数据到文件（可选）
    try:
        with open("logs/dns_benchmark_details.txt", "w", encoding="utf-8") as f:
            f.write("DNS性能测试详细报告\n")
            f.write("=" * 90 + "\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试域名: {', '.join(domains)}\n")
            f.write(f"每个域名测试次数: {num_tests}\n")
            f.write("=" * 90 + "\n\n")

            for result in results:
                f.write(f"DNS服务器: {result['dns_server']}\n")
                f.write("-" * 90 + "\n")

                for domain, stats in result["domain_stats"].items():
                    f.write(f"  域名: {domain}\n")
                    if stats.get("avg") is not None:
                        f.write(f"    平均: {stats['avg']*1000:.2f}ms\n")
                        f.write(f"    最短: {stats['min']*1000:.2f}ms\n")
                        f.write(f"    最长: {stats['max']*1000:.2f}ms\n")
                        if "std" in stats and stats["std"] is not None:
                            f.write(f"    标准差: {stats['std']*1000:.2f}ms\n")
                        if "success_rate" in stats:
                            f.write(f"    成功率: {stats['success_rate']:.1f}%\n")

                        # 转换times列表
                        times_details = []
                        for t in stats["times"]:
                            if t is not None:
                                times_details.append(f"{t*1000:.1f}ms")
                            else:
                                times_details.append("失败")
                        f.write(f"    详情: [{', '.join(times_details)}]\n")
                    else:
                        f.write("    状态: 全部解析失败\n")
                    f.write("\n")

        print_colored(
            "\n📄 详细测试数据已保存到: logs/dns_benchmark_details.txt", Fore.GREEN
        )
    except Exception as e:
        print_colored(f"\n⚠️  无法保存详细数据到文件: {e}", Fore.YELLOW)


async def async_main():
    """异步主函数"""
    parser = argparse.ArgumentParser(
        description="跨平台DNS服务器性能测试工具 - 异步并发版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 测试常见公共DNS（异步模式）
  python main.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com google.com github.com

  # 增加测试次数和超时时间
  python main.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com -t 5 --timeout 3.0

  # 测试国内常用DNS
  python main.py -d 223.5.5.5 114.114.114.114 119.29.29.29 -n taobao.com jd.com

  # 设置重试次数（当网络不稳定时）
  python main.py -d 8.8.8.8 1.1.1.1 -n google.com --retries 2

  # 综合测试本地及国内外公共DNS
  python main.py -d 202.103.24.68 202.103.44.150 223.5.5.5 114.114.114.114 119.29.29.29 8.8.8.8 1.1.1.1 -n baidu.com toutiao.com weixin.qq.com bilibili.com taobao.com google.com github.com -t 5 --timeout 3
        """,
    )

    # 必需参数
    parser.add_argument(
        "-d", "--dns", nargs="+", required=True, help="DNS服务器IP地址列表 (支持多个)"
    )

    parser.add_argument(
        "-n", "--names", nargs="+", required=True, help="要解析的域名列表 (支持多个)"
    )

    # 可选参数
    parser.add_argument(
        "-t", "--tests", type=int, default=3, help="每个域名测试次数 (默认: 3)"
    )

    parser.add_argument(
        "--timeout", type=float, default=2.0, help="DNS查询超时时间(秒) (默认: 2.0)"
    )

    parser.add_argument(
        "--retries", type=int, default=1, help="查询失败时的重试次数 (默认: 1)"
    )

    # HTTP性能测试选项
    http_group = parser.add_argument_group("HTTP性能测试选项")
    http_group.add_argument(
        "--enable-http-test",
        action="store_true",
        help="启用HTTP性能测试（测试DNS返回IP的实际访问速度）",
    )
    http_group.add_argument(
        "--http-timeout",
        type=float,
        default=10.0,
        help="HTTP请求超时时间(秒) (默认: 10.0)",
    )
    http_group.add_argument(
        "--max-http-concurrency",
        type=int,
        default=5,
        help="HTTP测试最大并发数 (默认: 5)",
    )
    http_group.add_argument(
        "--max-redirects", type=int, default=5, help="HTTP最大重定向次数 (默认: 5)"
    )
    http_group.add_argument(
        "--verify-ssl", action="store_true", help="启用SSL证书验证（默认禁用）"
    )
    http_group.add_argument(
        "--user-agent",
        type=str,
        default="DNS-Benchmark/1.0",
        help="自定义User-Agent字符串",
    )

    parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")

    parser.add_argument("--save-report", action="store_true", help="保存详细报告到文件")

    parser.add_argument(
        "--report-file",
        type=str,
        default="dns_benchmark_report.txt",
        help="报告文件名 (默认: dns_benchmark_report.txt)",
    )

    args = parser.parse_args()

    # 参数验证
    if not args.dns:
        parser.error("DNS服务器列表不能为空")
    if not args.names:
        parser.error("域名列表不能为空")
    if args.tests <= 0:
        parser.error("测试次数必须大于0")
    if args.timeout <= 0:
        parser.error("超时时间必须大于0")
    if args.retries < 1:
        parser.error("重试次数必须大于等于1")

    # HTTP测试参数验证
    if args.http_timeout <= 0:
        parser.error("HTTP超时时间必须大于0")
    if args.max_http_concurrency < 1:
        parser.error("HTTP最大并发数必须大于等于1")
    if args.max_redirects < 0:
        parser.error("HTTP最大重定向次数必须大于等于0")

    # 禁用彩色输出（如果指定）
    global HAS_COLORAMA
    if args.no_color:
        HAS_COLORAMA = False

        class NoColor:
            def __getattr__(self, name):
                return ""

        global Fore, Style, Back
        Fore = NoColor()
        Style = NoColor()
        Back = NoColor()

    # 显示测试信息
    print_colored("=" * 90, Fore.CYAN)
    print_colored("🚀 DNS服务器性能测试工具 - 异步并发版本", Fore.CYAN, Style.BRIGHT)
    print_colored("=" * 90, Fore.CYAN)

    print_colored(
        f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Fore.WHITE
    )
    print_colored(f"🌐 DNS服务器: {len(args.dns)} 个", Fore.WHITE)
    for i, dns in enumerate(args.dns, 1):
        print_colored(f"    {i}. {dns}", Fore.CYAN)

    print_colored(f"📋 测试域名: {len(args.names)} 个", Fore.WHITE)
    for i, domain in enumerate(args.names, 1):
        print_colored(f"    {i}. {domain}", Fore.CYAN)

    print_colored(f"🔁 每个域名测试: {args.tests} 次", Fore.WHITE)
    print_colored(f"⏱️  超时设置: {args.timeout} 秒", Fore.WHITE)
    print_colored(f"🔄 重试次数: {args.retries} 次", Fore.WHITE)

    # HTTP测试配置显示
    if args.enable_http_test:
        print_colored("🌐 HTTP测试: 已启用", Fore.YELLOW, Style.BRIGHT)
        print_colored(f"   ⏱️  HTTP超时: {args.http_timeout} 秒", Fore.WHITE)
        print_colored(f"   🔄 最大并发: {args.max_http_concurrency}", Fore.WHITE)
        print_colored(f"   ↪️  最大重定向: {args.max_redirects}", Fore.WHITE)
        print_colored(
            f"   🔒 SSL验证: {'启用' if args.verify_ssl else '禁用'}", Fore.WHITE
        )
    else:
        print_colored("🌐 HTTP测试: 未启用", Fore.WHITE)

    if HAS_AIODNS:
        print_colored("⚡ 模式: 异步模式", Fore.GREEN)
    else:
        print_colored("⚡ 模式: 异步模式不可用（需要安装aiodns）", Fore.RED)

    print_colored("-" * 90, Fore.WHITE)

    # 创建并配置DNSBenchmark实例
    benchmark = DNSBenchmark(retries=args.retries)

    benchmark.set_config(
        dns_servers=args.dns,
        domains=args.names,
        num_tests=args.tests,
        timeout=args.timeout,
        enable_http_test=args.enable_http_test,
        http_timeout=args.http_timeout,
        max_http_concurrency=args.max_http_concurrency,
        max_redirects=args.max_redirects,
        user_agent=args.user_agent,
        verify_ssl=args.verify_ssl,
    )

    # 运行测试
    try:
        # 运行异步测试
        results = await benchmark.run_async()

        # 打印汇总表格
        print_summary_table(results, args.tests, args.names, args.enable_http_test)

        # 打印详细报告
        benchmark.print_detailed_report()

        # 保存报告（如果指定）
        if args.save_report:
            benchmark.save_results_to_file(args.report_file)

        return 0

    except KeyboardInterrupt:
        print_colored("\n\n⏹️  测试已被用户中断", Fore.YELLOW)
        return 130  # SIGINT退出码
    except Exception as e:
        print_colored(f"\n❌ 发生错误: {str(e)}", Fore.RED)
        import traceback

        traceback.print_exc()
        return 1


def main():
    """主函数入口，处理Windows事件循环"""
    # Windows需要特殊处理事件循环
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print_colored("\n\n⏹️  测试已被用户中断", Fore.YELLOW)
        return 130
    except Exception as e:
        print_colored(f"\n❌ 程序执行错误: {str(e)}", Fore.RED)
        return 1


if __name__ == "__main__":
    sys.exit(main())
