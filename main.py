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
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 检查并导入所需模块
# 注意：已移除 dnspython 和 prettytable 依赖

# 尝试导入异步DNS库
try:
    import aiodns
    HAS_AIODNS = True
except ImportError:
    HAS_AIODNS = False

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
            return ''
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

# ============================================================================
# 辅助函数
# ============================================================================

def print_colored(text: str, color: str = Fore.WHITE, style: str = Style.NORMAL,
                   end: str = '\n', flush: bool = False) -> None:
    """打印彩色文本"""
    print(f"{style}{color}{text}{Style.RESET_ALL}", end=end, flush=flush)

def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds is None:
        return "失败"
    if seconds == float('inf'):
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

if missing_deps:
    print_colored("="*70, Fore.RED)
    print_colored("错误: 缺少必要的Python模块", Fore.RED, Style.BRIGHT)
    print_colored("="*70, Fore.RED)
    print_colored(f"\n未找到模块: {', '.join(missing_deps)}", Fore.YELLOW)
    print_colored("\n请安装所需模块:", Fore.CYAN)
    print_colored("  pip install aiodns colorama tabulate", Fore.GREEN)
    print_colored("\n安装完成后重新运行此脚本", Fore.CYAN)
    sys.exit(1)




async def async_resolve_domain(dns_server: str, domain: str, timeout: float = 2.0,
                               retries: int = 1) -> Optional[float]:
    """
    异步DNS解析函数
    使用aiodns进行异步DNS查询
    """
    if HAS_AIODNS:
        return await _async_resolve_aiodns(dns_server, domain, timeout, retries)
    else:
        # aiodns 不可用，提示用户安装
        print_colored("错误: aiodns 模块不可用，无法进行DNS查询", Fore.RED)
        print_colored("请安装 aiodns 模块: pip install aiodns", Fore.YELLOW)
        return None


async def _async_resolve_aiodns(dns_server: str, domain: str, timeout: float = 2.0,
                                retries: int = 1) -> Optional[float]:
    """
    使用aiodns进行异步DNS解析
    """
    for attempt in range(retries):
        try:
            resolver = aiodns.DNSResolver(nameservers=[dns_server])
            start_time = asyncio.get_event_loop().time()

            # 使用asyncio.wait_for添加超时控制
            try:
                await asyncio.wait_for(
                    resolver.query(domain, 'A'),
                    timeout=timeout
                )
                end_time = asyncio.get_event_loop().time()
                elapsed = end_time - start_time

                # 短暂延迟避免请求过于密集
                await asyncio.sleep(0.05)
                return elapsed

            except asyncio.TimeoutError:
                print_colored(f"  超时 (尝试 {attempt+1}/{retries}): {domain} @ {dns_server}", Fore.YELLOW)
                if attempt < retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                continue

        except aiodns.error.DNSError as e:
            error_msg = str(e)
            if "NXDOMAIN" in error_msg:
                print_colored(f"  域名不存在: {domain} @ {dns_server}", Fore.YELLOW)
            elif "SERVFAIL" in error_msg:
                print_colored(f"  服务器失败: {domain} @ {dns_server}", Fore.YELLOW)
            else:
                print_colored(f"  DNS错误: {domain} @ {dns_server} - {error_msg}", Fore.RED)

            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue

        except Exception as e:
            print_colored(f"  未知错误: {domain} @ {dns_server} - {str(e)}", Fore.RED)
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue

    return None  # 所有重试都失败




async def async_test_dns_server(dns_server: str, domains: List[str], num_tests: int,
                                timeout: float, retries: int = 1) -> Dict:
    """
    异步测试单个DNS服务器对所有域名的解析性能
    """
    results = {
        'dns_server': dns_server,
        'domain_stats': {},
        'all_times': [],
        'errors': []
    }

    print_colored(f"\n🔍 测试DNS服务器: {dns_server}", Fore.CYAN, Style.BRIGHT)

    total_queries = len(domains) * num_tests
    completed_queries = 0

    for domain_idx, domain in enumerate(domains):
        domain_times = []
        print_colored(f"  📡 域名 {domain_idx+1}/{len(domains)}: {domain}", Fore.WHITE, end='', flush=True)

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
                    print_colored(" ❌", Fore.RED, end='', flush=True)
                    results['errors'].append({
                        'domain': domain,
                        'test_num': i,
                        'error': str(result)
                    })
                    domain_times.append(None)
                elif result is None:
                    print_colored(" ❌", Fore.RED, end='', flush=True)
                    domain_times.append(None)
                else:
                    print_colored(f" {result*1000:.1f}ms", Fore.GREEN, end='', flush=True)
                    domain_times.append(result)

                # 显示进度
                if (completed_queries % 5 == 0) or (completed_queries == total_queries):
                    progress_bar = get_progress_bar(progress)
                    print_colored(f" {progress_bar}", Fore.BLUE, end='\r' if completed_queries < total_queries else '\n')

        except Exception as e:
            print_colored(f"  测试过程中发生错误: {str(e)}", Fore.RED)
            for _ in range(num_tests):
                domain_times.append(None)

        # 计算该域名的统计
        valid_times = [t for t in domain_times if t is not None]
        if valid_times:
            stats = {
                'min': min(valid_times),
                'max': max(valid_times),
                'avg': statistics.mean(valid_times),
                'std': statistics.stdev(valid_times) if len(valid_times) > 1 else 0,
                'success_rate': len(valid_times) / len(domain_times) * 100,
                'times': domain_times
            }
        else:
            stats = {
                'min': None,
                'max': None,
                'avg': None,
                'std': None,
                'success_rate': 0,
                'times': domain_times
            }

        results['domain_stats'][domain] = stats
        results['all_times'].extend(valid_times)

        # 显示域名统计结果
        if stats['avg'] is not None:
            color = Fore.GREEN if stats['success_rate'] >= 80 else Fore.YELLOW if stats['success_rate'] >= 50 else Fore.RED
            print_colored(f"   | 平均: {stats['avg']*1000:.1f}ms, 成功率: {stats['success_rate']:.1f}%", color)
        else:
            print_colored("   | 全部失败", Fore.RED)

    return results


async def async_test_all_dns_servers(dns_servers: List[str], domains: List[str],
                                     num_tests: int, timeout: float, retries: int = 1) -> List[Dict]:
    """
    并发测试所有DNS服务器
    """
    print_colored(f"\n🚀 开始并发测试 {len(dns_servers)} 个DNS服务器...", Fore.CYAN, Style.BRIGHT)

    tasks = []
    for dns_server in dns_servers:
        task = async_test_dns_server(dns_server, domains, num_tests, timeout, retries)
        tasks.append(task)

    # 并发执行所有DNS服务器测试
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理可能出现的异常
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print_colored(f"❌ DNS服务器 {dns_servers[i]} 测试失败: {str(result)}", Fore.RED)
            # 创建失败的结果记录
            final_results.append({
                'dns_server': dns_servers[i],
                'domain_stats': {},
                'all_times': [],
                'errors': [str(result)]
            })
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

    def __init__(self, use_async: bool = True, retries: int = 1):
        """
        初始化DNS基准测试器

        Args:
            use_async: 是否使用异步模式（如果可用）
            retries: 查询失败时的重试次数
        """
        self.use_async = use_async and HAS_AIODNS
        self.retries = retries
        self.results = []
        self.dns_servers = []
        self.domains = []
        self.num_tests = 3
        self.timeout = 2.0
        self.start_time = None
        self.end_time = None

        if self.use_async:
            print_colored("✅ 使用异步模式进行测试", Fore.GREEN)
        else:
            print_colored("⚠️  使用同步模式进行测试（aiodns不可用）", Fore.YELLOW)

    def set_config(self, dns_servers: List[str], domains: List[str],
                   num_tests: int = 3, timeout: float = 2.0) -> None:
        """设置测试配置"""
        self.dns_servers = dns_servers
        self.domains = domains
        self.num_tests = num_tests
        self.timeout = timeout

    async def run_async(self) -> List[Dict]:
        """异步运行基准测试"""
        self.start_time = time.time()
        print_colored(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Fore.CYAN)

        if self.use_async:
            self.results = await async_test_all_dns_servers(
                self.dns_servers, self.domains, self.num_tests, self.timeout, self.retries
            )
        else:
            # aiodns 不可用，抛出错误
            raise RuntimeError("aiodns 模块不可用，无法进行异步DNS测试。请安装 aiodns: pip install aiodns")

        self.end_time = time.time()
        elapsed = self.end_time - self.start_time
        print_colored(f"\n✅ 测试完成! 总耗时: {elapsed:.2f}秒", Fore.GREEN, Style.BRIGHT)

        return self.results


    def calculate_overall_statistics(self) -> Dict:
        """计算总体统计信息"""
        if not self.results:
            return {}

        total_queries = len(self.dns_servers) * len(self.domains) * self.num_tests
        successful_queries = 0
        all_times = []

        for result in self.results:
            successful_queries += len(result['all_times'])
            all_times.extend(result['all_times'])

        if all_times:
            return {
                'total_queries': total_queries,
                'successful_queries': successful_queries,
                'success_rate': (successful_queries / total_queries) * 100,
                'overall_avg': statistics.mean(all_times),
                'overall_min': min(all_times),
                'overall_max': max(all_times),
                'overall_std': statistics.stdev(all_times) if len(all_times) > 1 else 0,
                'total_time': self.end_time - self.start_time if self.end_time else 0
            }
        else:
            return {
                'total_queries': total_queries,
                'successful_queries': 0,
                'success_rate': 0,
                'overall_avg': None,
                'overall_min': None,
                'overall_max': None,
                'overall_std': None,
                'total_time': self.end_time - self.start_time if self.end_time else 0
            }

    def print_detailed_report(self) -> None:
        """打印详细报告"""
        stats = self.calculate_overall_statistics()
        if not stats:
            return

        print_colored("\n" + "="*90, Fore.CYAN)
        print_colored("📊 DNS性能测试详细报告", Fore.CYAN, Style.BRIGHT)
        print_colored("="*90, Fore.CYAN)

        print_colored("\n📈 总体统计:", Fore.WHITE)
        print_colored(f"   总查询次数: {stats['total_queries']}", Fore.WHITE)
        print_colored(f"   成功查询: {stats['successful_queries']}", Fore.GREEN)
        print_colored(f"   失败查询: {stats['total_queries'] - stats['successful_queries']}", Fore.RED)
        print_colored(f"   成功率: {stats['success_rate']:.1f}%",
                     Fore.GREEN if stats['success_rate'] >= 80 else
                     Fore.YELLOW if stats['success_rate'] >= 50 else Fore.RED)

        if stats['overall_avg'] is not None:
            print_colored(f"   平均响应时间: {stats['overall_avg']*1000:.1f}ms", Fore.WHITE)
            print_colored(f"   最快响应: {stats['overall_min']*1000:.1f}ms", Fore.GREEN)
            print_colored(f"   最慢响应: {stats['overall_max']*1000:.1f}ms", Fore.YELLOW)
            if stats['overall_std'] is not None:
                print_colored(f"   响应时间标准差: {stats['overall_std']*1000:.1f}ms", Fore.WHITE)

        print_colored(f"   总测试时间: {stats['total_time']:.2f}秒", Fore.WHITE)

        # 错误统计
        self._print_error_statistics()

    def _print_error_statistics(self) -> None:
        """打印错误统计"""
        if not self.results:
            return

        error_stats = {
            'timeout': 0,
            'nxdomain': 0,
            'no_answer': 0,
            'network': 0,
            'other': 0
        }

        total_errors = 0

        for result in self.results:
            if 'errors' in result:
                for error_info in result['errors']:
                    error_msg = error_info.get('error', '').lower()
                    if 'timeout' in error_msg:
                        error_stats['timeout'] += 1
                    elif 'nxdomain' in error_msg or 'domain not found' in error_msg:
                        error_stats['nxdomain'] += 1
                    elif 'no answer' in error_msg or 'no response' in error_msg:
                        error_stats['no_answer'] += 1
                    elif 'network' in error_msg or 'connection' in error_msg:
                        error_stats['network'] += 1
                    else:
                        error_stats['other'] += 1
                    total_errors += 1

        if total_errors > 0:
            print_colored("\n🔍 错误分析:", Fore.WHITE)
            print_colored(f"   总错误数: {total_errors}", Fore.YELLOW)

            if error_stats['timeout'] > 0:
                print_colored(f"   超时错误: {error_stats['timeout']} ({error_stats['timeout']/total_errors*100:.1f}%)", Fore.YELLOW)
            if error_stats['nxdomain'] > 0:
                print_colored(f"   域名不存在: {error_stats['nxdomain']} ({error_stats['nxdomain']/total_errors*100:.1f}%)", Fore.YELLOW)
            if error_stats['no_answer'] > 0:
                print_colored(f"   无应答错误: {error_stats['no_answer']} ({error_stats['no_answer']/total_errors*100:.1f}%)", Fore.YELLOW)
            if error_stats['network'] > 0:
                print_colored(f"   网络错误: {error_stats['network']} ({error_stats['network']/total_errors*100:.1f}%)", Fore.RED)
            if error_stats['other'] > 0:
                print_colored(f"   其他错误: {error_stats['other']} ({error_stats['other']/total_errors*100:.1f}%)", Fore.RED)

    def save_results_to_file(self, filename: str = "dns_benchmark_report.txt") -> bool:
        """保存结果到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("DNS性能测试详细报告\n")
                f.write("="*90 + "\n")
                f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"DNS服务器: {', '.join(self.dns_servers)}\n")
                f.write(f"测试域名: {', '.join(self.domains)}\n")
                f.write(f"每个域名测试次数: {self.num_tests}\n")
                f.write(f"超时设置: {self.timeout}秒\n")
                f.write(f"使用异步模式: {'是' if self.use_async else '否'}\n")
                f.write("="*90 + "\n\n")

                stats = self.calculate_overall_statistics()
                f.write("总体统计:\n")
                f.write(f"  总查询次数: {stats['total_queries']}\n")
                f.write(f"  成功查询: {stats['successful_queries']}\n")
                f.write(f"  成功率: {stats['success_rate']:.1f}%\n")
                if stats['overall_avg'] is not None:
                    f.write(f"  平均响应时间: {stats['overall_avg']*1000:.1f}ms\n")
                    f.write(f"  最快响应: {stats['overall_min']*1000:.1f}ms\n")
                    f.write(f"  最慢响应: {stats['overall_max']*1000:.1f}ms\n")
                    if stats['overall_std'] is not None:
                        f.write(f"  响应时间标准差: {stats['overall_std']*1000:.1f}ms\n")
                f.write(f"  总测试时间: {stats['total_time']:.2f}秒\n\n")

                f.write("各DNS服务器详细结果:\n")
                f.write("="*90 + "\n")
                for result in self.results:
                    f.write(f"\nDNS服务器: {result['dns_server']}\n")
                    f.write("-"*90 + "\n")
                    for domain, domain_stats in result['domain_stats'].items():
                        f.write(f"  域名: {domain}\n")
                        if domain_stats['avg'] is not None:
                            f.write(f"    平均: {domain_stats['avg']*1000:.2f}ms\n")
                            f.write(f"    最短: {domain_stats['min']*1000:.2f}ms\n")
                            f.write(f"    最长: {domain_stats['max']*1000:.2f}ms\n")
                            f.write(f"    标准差: {domain_stats['std']*1000:.2f}ms\n")
                            f.write(f"    成功率: {domain_stats['success_rate']:.1f}%\n")
                            times_str = ', '.join([
                                f"{t*1000:.1f}ms" if t is not None else "失败"
                                for t in domain_stats['times']
                            ])
                            f.write(f"    详细结果: [{times_str}]\n")
                        else:
                            f.write("    状态: 全部解析失败\n")
                        f.write("\n")

            print_colored(f"📄 详细报告已保存到: {filename}", Fore.GREEN)
            return True

        except Exception as e:
            print_colored(f"❌ 保存报告失败: {str(e)}", Fore.RED)
            return False


def print_summary_table(results: List[Dict], num_tests: int, domains: List[str]):
    """
    打印汇总结果表格
    修复统计计算问题，使用None代替float('inf')
    """
    print_colored("\n" + "="*90, Fore.CYAN)
    print_colored("📊 DNS服务器性能测试汇总", Fore.CYAN, Style.BRIGHT)
    print_colored("="*90, Fore.CYAN)

    # 准备汇总数据
    table_data = []
    for result in results:
        dns_server = result['dns_server']
        all_times = result['all_times']

        # 计算成功率
        total_queries = num_tests * len(domains)
        successful_queries = len(all_times)
        success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0

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
        for domain, stats in result['domain_stats'].items():
            if stats.get('avg') is not None:
                successful_domains += 1

        table_data.append({
            'dns_server': dns_server,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'success_rate': success_rate,
            'total_domains': len(domains),
            'successful_domains': successful_domains,
            'total_queries': total_queries,
            'successful_queries': successful_queries
        })

    # 按平均时间排序（None值排在最后）
    def sort_key(x):
        avg = x['avg_time']
        if avg is None:
            return (float('inf'), -x['success_rate'])
        return (avg, -x['success_rate'])

    table_data.sort(key=sort_key)

    # 打印表格
    if HAS_TABULATE:
        # 使用tabulate输出表格
        headers = ["DNS服务器", "平均耗时", "最短耗时", "最长耗时", "成功率", "可用域名"]
        rows = []

        for row in table_data:
            if row['avg_time'] is not None:
                avg_str = f"{row['avg_time']*1000:.1f}ms"
                min_str = f"{row['min_time']*1000:.1f}ms"
                max_str = f"{row['max_time']*1000:.1f}ms"
            else:
                avg_str = "失败"
                min_str = "-"
                max_str = "-"

            rows.append([
                row['dns_server'],
                avg_str,
                min_str,
                max_str,
                f"{row['success_rate']:.1f}%",
                f"{row['successful_domains']}/{row['total_domains']}"
            ])

        print(tabulate(rows, headers=headers, tablefmt="grid"))

    else:
        # tabulate 不可用，提示用户安装
        print_colored("="*70, Fore.YELLOW)
        print_colored("警告: 缺少表格输出模块", Fore.YELLOW, Style.BRIGHT)
        print_colored("="*70, Fore.YELLOW)
        print_colored("\n未找到模块: tabulate", Fore.YELLOW)
        print_colored("\n请安装所需模块:", Fore.CYAN)
        print_colored("  pip install tabulate", Fore.GREEN)
        print_colored("\n安装后重新运行程序以获得更好的表格显示效果。", Fore.CYAN)

        # 仍然显示简单的结果摘要
        print_colored("\n" + "="*90, Fore.CYAN)
        print_colored("测试结果摘要:", Fore.CYAN, Style.BRIGHT)
        print_colored("="*90, Fore.CYAN)

        for row in table_data:
            if row['avg_time'] is not None:
                print_colored(f"{row['dns_server']}: 平均 {row['avg_time']*1000:.1f}ms, 成功率 {row['success_rate']:.1f}%",
                            Fore.GREEN if row['success_rate'] >= 80 else Fore.YELLOW if row['success_rate'] >= 50 else Fore.RED)
            else:
                print_colored(f"{row['dns_server']}: ❌ 失败", Fore.RED)

    # 打印推荐
    print_colored("\n" + "="*90, Fore.CYAN)
    print_colored("🏆 推荐DNS服务器（按平均响应时间和稳定性排序）:", Fore.CYAN, Style.BRIGHT)
    print_colored("="*90, Fore.CYAN)

    recommendations = 0
    for i, row in enumerate(table_data, 1):
        if row['avg_time'] is not None and row['success_rate'] >= 50:
            color = Fore.GREEN if row['success_rate'] >= 80 else Fore.YELLOW
            print_colored(f"{i}. {row['dns_server']} - 平均 {row['avg_time']*1000:.1f}ms, 成功率 {row['success_rate']:.1f}%", color)
            recommendations += 1
            if recommendations >= 3:
                break

    if recommendations == 0:
        print_colored("⚠️  没有找到可靠的DNS服务器推荐", Fore.YELLOW)

    # 打印详细数据到文件（可选）
    try:
        with open('logs/dns_benchmark_details.txt', 'w', encoding='utf-8') as f:
            f.write("DNS性能测试详细报告\n")
            f.write("="*90 + "\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试域名: {', '.join(domains)}\n")
            f.write(f"每个域名测试次数: {num_tests}\n")
            f.write("="*90 + "\n\n")

            for result in results:
                f.write(f"DNS服务器: {result['dns_server']}\n")
                f.write("-"*90 + "\n")

                for domain, stats in result['domain_stats'].items():
                    f.write(f"  域名: {domain}\n")
                    if stats.get('avg') is not None:
                        f.write(f"    平均: {stats['avg']*1000:.2f}ms\n")
                        f.write(f"    最短: {stats['min']*1000:.2f}ms\n")
                        f.write(f"    最长: {stats['max']*1000:.2f}ms\n")
                        if 'std' in stats and stats['std'] is not None:
                            f.write(f"    标准差: {stats['std']*1000:.2f}ms\n")
                        if 'success_rate' in stats:
                            f.write(f"    成功率: {stats['success_rate']:.1f}%\n")

                        # 转换times列表
                        times_details = []
                        for t in stats['times']:
                            if t is not None:
                                times_details.append(f"{t*1000:.1f}ms")
                            else:
                                times_details.append("失败")
                        f.write(f"    详情: [{', '.join(times_details)}]\n")
                    else:
                        f.write("    状态: 全部解析失败\n")
                    f.write("\n")

        print_colored("\n📄 详细测试数据已保存到: logs/dns_benchmark_details.txt", Fore.GREEN)
    except Exception as e:
        print_colored(f"\n⚠️  无法保存详细数据到文件: {e}", Fore.YELLOW)


async def async_main():
    """异步主函数"""
    parser = argparse.ArgumentParser(
        description='跨平台DNS服务器性能测试工具 - 异步并发版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 测试常见公共DNS（异步模式）
  python run-kimi.py -d 8.8.8.8 1.1.1.1 223.5.5.5 -n baidu.com google.com github.com

  # 增加测试次数和超时时间
  python run-kimi.py -d 8.8.8.8 1.1.1.1 -n baidu.com google.com -t 5 --timeout 3.0

  # 测试国内常用DNS
  python run-kimi.py -d 223.5.5.5 114.114.114.114 119.29.29.29 -n taobao.com jd.com

  # 设置重试次数（当网络不稳定时）
  python run-kimi.py -d 8.8.8.8 1.1.1.1 -n google.com --retries 2
        '''
    )

    # 必需参数
    parser.add_argument(
        '-d', '--dns',
        nargs='+',
        required=True,
        help='DNS服务器IP地址列表 (支持多个)'
    )

    parser.add_argument(
        '-n', '--names',
        nargs='+',
        required=True,
        help='要解析的域名列表 (支持多个)'
    )

    # 可选参数
    parser.add_argument(
        '-t', '--tests',
        type=int,
        default=3,
        help='每个域名测试次数 (默认: 3)'
    )

    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='DNS查询超时时间(秒) (默认: 2.0)'
    )

    parser.add_argument(
        '--retries',
        type=int,
        default=1,
        help='查询失败时的重试次数 (默认: 1)'
    )


    parser.add_argument(
        '--no-color',
        action='store_true',
        help='禁用彩色输出'
    )

    parser.add_argument(
        '--save-report',
        action='store_true',
        help='保存详细报告到文件'
    )

    parser.add_argument(
        '--report-file',
        type=str,
        default='dns_benchmark_report.txt',
        help='报告文件名 (默认: dns_benchmark_report.txt)'
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

    # 禁用彩色输出（如果指定）
    global HAS_COLORAMA
    if args.no_color:
        HAS_COLORAMA = False
        class NoColor:
            def __getattr__(self, name):
                return ''
        global Fore, Style, Back
        Fore = NoColor()
        Style = NoColor()
        Back = NoColor()

    # 显示测试信息
    print_colored("="*90, Fore.CYAN)
    print_colored("🚀 DNS服务器性能测试工具 - 异步并发版本", Fore.CYAN, Style.BRIGHT)
    print_colored("="*90, Fore.CYAN)

    print_colored(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Fore.WHITE)
    print_colored(f"🌐 DNS服务器: {len(args.dns)} 个", Fore.WHITE)
    for i, dns in enumerate(args.dns, 1):
        print_colored(f"    {i}. {dns}", Fore.CYAN)

    print_colored(f"📋 测试域名: {len(args.names)} 个", Fore.WHITE)
    for i, domain in enumerate(args.names, 1):
        print_colored(f"    {i}. {domain}", Fore.CYAN)

    print_colored(f"🔁 每个域名测试: {args.tests} 次", Fore.WHITE)
    print_colored(f"⏱️  超时设置: {args.timeout} 秒", Fore.WHITE)
    print_colored(f"🔄 重试次数: {args.retries} 次", Fore.WHITE)

    if HAS_AIODNS:
        print_colored("⚡ 模式: 异步模式", Fore.GREEN)
    else:
        print_colored("⚡ 模式: 异步模式不可用（需要安装aiodns）", Fore.RED)

    print_colored("-"*90, Fore.WHITE)

    # 创建并配置DNSBenchmark实例
    benchmark = DNSBenchmark(
        use_async=HAS_AIODNS,
        retries=args.retries
    )

    benchmark.set_config(
        dns_servers=args.dns,
        domains=args.names,
        num_tests=args.tests,
        timeout=args.timeout
    )

    # 运行测试
    try:
        if benchmark.use_async:
            results = await benchmark.run_async()
        else:
            print_colored("错误: aiodns 模块不可用，无法进行DNS测试", Fore.RED)
            print_colored("请安装 aiodns 模块: pip install aiodns", Fore.YELLOW)
            sys.exit(1)

        # 打印汇总表格
        print_summary_table(results, args.tests, args.names)

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
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print_colored("\n\n⏹️  测试已被用户中断", Fore.YELLOW)
        return 130
    except Exception as e:
        print_colored(f"\n❌ 程序执行错误: {str(e)}", Fore.RED)
        return 1


if __name__ == '__main__':
    sys.exit(main())
