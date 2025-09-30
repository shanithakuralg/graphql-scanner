#!/usr/bin/env python3

import argparse
import requests
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException
import threading
import queue
from colorama import Fore, Style, init
import signal
import sys
import time
import urllib3
import os
from datetime import datetime

# Disable InsecureRequestWarning for cleaner output
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

# Global variables
total_tasks = 0
tasks_completed = 0
continue_execution = True
lock = threading.Lock()
found_endpoints = []
scan_start_time = None
current_target = ""
start_time = None

# Clean, professional banner
BANNER = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════════════╗
║                          {Fore.WHITE}{Style.BRIGHT}GRAPHQL ENDPOINT SCANNER{Style.RESET_ALL}{Fore.CYAN}                          ║
║                              {Fore.YELLOW}Advanced Detection Tool{Style.RESET_ALL}{Fore.CYAN}                              ║
╠════════════════════════════════════════════════════════════════════════╣
║ {Fore.WHITE}Author:{Style.RESET_ALL}    Saurabh Tomar                                             {Fore.CYAN}║
║ {Fore.WHITE}Version:{Style.RESET_ALL}   1.6 (Clean Progress)                                     {Fore.CYAN}║
║ {Fore.WHITE}GitHub:{Style.RESET_ALL}    https://github.com/shanithakuralg                      {Fore.CYAN}║
╚════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

DEFAULT_PAYLOADS = [
    '/__graphql', '/altair', '/api/gql', '/api/graphql', '/api/query', '/explorer',
    '/gql', '/graphiql', '/graphiql/index', '/graphql', '/graphql-console',
    '/graphql-explorer', '/graphql-playground', '/graphql/api', '/graphql/endpoint',
    '/graphql/query', '/graphql/ui', '/playground', '/query', '/v1/graphql',
    '/v2/graphql', '/___graphql', '/api/graphql', '/graph', '/graphiql.css',
    '/graphiql.js', '/graphiql.min.css', '/graphiql.min.js', '/graphiql.php',
    '/graphiql/finland', '/graphql-devtools', '/graphql.php', '/graphql/console',
    '/graphql/schema.json', '/graphql/schema.xml', '/graphql/schema.yaml',
    '/je/graphql', '/subscriptions', '/v1/altair', '/v1/api/graphql',
    '/v1/explorer', '/v1/graph', '/v1/graphiql', '/v1/graphiql.css',
    '/v1/graphiql.js', '/v1/graphiql.min.css', '/v1/graphiql.min.js',
    '/v1/graphiql.php', '/v1/graphiql/finland', '/v1/graphql-explorer',
    '/v1/graphql.php', '/v1/graphql/console', '/v1/graphql/schema.json',
    '/v1/graphql/schema.xml', '/v1/graphql/schema.yaml', '/v1/playground',
    '/v1/subscriptions', '/v2/altair', '/v2/api/graphql', '/v2/explorer',
    '/v2/graph', '/v2/graphiql', '/v2/graphiql.css', '/v2/graphiql.js',
    '/v2/graphiql.min.css', '/v2/graphiql.min.js', '/v2/graphiql.php',
    '/v2/graphiql/finland', '/v2/graphql-explorer', '/v2/graphql.php',
    '/v2/graphql/console', '/v2/graphql/schema.json', '/v2/graphql/schema.xml',
    '/v2/graphql/schema.yaml', '/v2/playground', '/v2/subscriptions',
    '/v3/altair', '/v3/api/graphql', '/v3/explorer', '/v3/graph', '/v3/graphiql',
    '/v3/graphiql.css', '/v3/graphiql.js', '/v3/graphiql.min.css',
    '/v3/graphiql.min.js', '/v3/graphiql.php', '/v3/graphiql/finland',
    '/v3/graphql-explorer', '/v3/graphql.php', '/v3/graphql/console',
    '/v3/graphql/schema.json', '/v3/graphql/schema.xml', '/v3/graphql/schema.yaml',
    '/v3/playground', '/v3/subscriptions', '/v4/altair', '/v4/api/graphql',
    '/v4/explorer', '/v4/graph', '/v4/graphiql', '/v4/graphiql.css',
    '/v4/graphiql.js', '/v4/graphiql.min.css', '/v4/graphiql.min.js',
    '/v4/graphiql.php', '/v4/graphiql/finland', '/v4/graphql-explorer',
    '/v4/graphql.php', '/v4/graphql/console', '/v4/graphql/schema.json',
    '/v4/graphql/schema.xml', '/v4/graphql/schema.yaml', '/v4/playground',
    '/v4/subscriptions', '/api/now/graphql', '/rw/graphql', 
    '/graphql?query=query{__schema{types{name}}}'
]

def get_elapsed_time():
    """Get formatted elapsed time"""
    if start_time:
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
    return "00:00"

def update_progress():
    """Update progress bar like dirsearch - single line update"""
    global tasks_completed, total_tasks, current_target, found_endpoints
    
    if total_tasks == 0:
        return
        
    progress = (tasks_completed / total_tasks) * 100
    elapsed = get_elapsed_time()
    
    # Calculate ETA
    if tasks_completed > 0 and start_time:
        rate = tasks_completed / (time.time() - start_time)
        eta_seconds = (total_tasks - tasks_completed) / rate if rate > 0 else 0
        eta_minutes = int(eta_seconds // 60)
        eta_secs = int(eta_seconds % 60)
        eta = f"{eta_minutes:02d}:{eta_secs:02d}"
    else:
        eta = "00:00"
    
    # Create progress bar
    bar_width = 20
    filled = int((progress / 100) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    
    # Status line like dirsearch
    status_line = (f"\r{Fore.CYAN}[{elapsed}] [{bar}] {progress:5.1f}% - "
                  f"{tasks_completed}/{total_tasks} - "
                  f"Found: {Fore.GREEN}{len(found_endpoints)}{Fore.CYAN} - "
                  f"ETA: {eta}{Style.RESET_ALL}")
    
    print(status_line, end='', flush=True)

def print_found(message):
    """Print found endpoints without messing up progress bar"""
    print(f"\r{' ' * 100}\r{Fore.GREEN}[+] {message}{Style.RESET_ALL}")
    update_progress()

def print_info(message):
    """Print info messages"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {message}")

def signal_handler(sig, frame):
    """Enhanced interrupt handler - dirsearch style"""
    global continue_execution, found_endpoints
    
    print(f"\n\n{Fore.YELLOW}╔══════════════════════════════════════╗")
    print(f"{Fore.YELLOW}║          SCAN INTERRUPTED           ║")
    print(f"{Fore.YELLOW}╚══════════════════════════════════════╝{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Options:{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}[c]{Style.RESET_ALL} continue")
    print(f"  {Fore.YELLOW}[n]{Style.RESET_ALL} next (skip current target)")  
    print(f"  {Fore.RED}[q]{Style.RESET_ALL} quit")
    
    try:
        choice = input(f"\n{Fore.CYAN}Choice: {Style.RESET_ALL}").lower().strip()
        
        if choice == 'c':
            print_info("Continuing scan...")
            update_progress()
        elif choice == 'n':
            print_info("Skipping to next target...")
            update_progress()
        elif choice == 'q':
            print_info("Stopping scan...")
            continue_execution = False
            show_final_results()
            sys.exit(0)
        else:
            print_info("Invalid choice. Continuing...")
            update_progress()
    except (EOFError, KeyboardInterrupt):
        print_info("Force quit...")
        continue_execution = False
        show_final_results()
        sys.exit(0)

def worker(q, args):
    """Enhanced worker thread with clean progress tracking"""
    global tasks_completed, continue_execution, found_endpoints, current_target
    
    while continue_execution:
        try:
            target_url = q.get(timeout=1)
            
            with lock:
                current_target = target_url
            
            endpoints_found_for_target = []
            
            for endpoint in DEFAULT_PAYLOADS:
                if not continue_execution:
                    break
                    
                url_to_test = f"{target_url}{endpoint}"
                
                try:
                    response = requests.post(
                        url_to_test,
                        json={"query": "{ __typename }"},
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "GraphQL-Scanner/1.6"
                        },
                        timeout=args.timeout,
                        verify=False,
                        allow_redirects=False,
                        proxies={"http": args.proxy, "https": args.proxy} if args.proxy else None
                    )
                    
                    if response.status_code == 200 and '"__typename":"Query"' in response.text:
                        endpoint_info = {
                            'url': url_to_test,
                            'target': target_url,
                            'endpoint': endpoint,
                            'status': response.status_code,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        with lock:
                            found_endpoints.append(endpoint_info)
                            endpoints_found_for_target.append(endpoint)
                            
                        if not args.quiet:
                            print_found(f"GraphQL endpoint: {url_to_test}")
                            
                except (ConnectionError, Timeout, TooManyRedirects, RequestException):
                    if args.verbose:
                        pass  # Silent for clean output
                        
                except Exception:
                    if args.verbose:
                        pass  # Silent for clean output
            
            q.task_done()
            with lock:
                tasks_completed += 1
                if not args.quiet:
                    update_progress()
                    
        except queue.Empty:
            continue

def show_final_results():
    """Display comprehensive final results"""
    global found_endpoints, start_time
    
    scan_duration = time.time() - start_time if start_time else 0
    
    print(f"\n\n{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║                              SCAN RESULTS                                ║")
    print(f"{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    print(f"\n{Fore.WHITE}{Style.BRIGHT}📊 SUMMARY:{Style.RESET_ALL}")
    print(f"   • Total targets scanned: {Fore.YELLOW}{tasks_completed}{Style.RESET_ALL}")
    print(f"   • GraphQL endpoints found: {Fore.GREEN}{len(found_endpoints)}{Style.RESET_ALL}")
    print(f"   • Scan duration: {Fore.CYAN}{scan_duration:.2f} seconds{Style.RESET_ALL}")
    
    if found_endpoints:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}🎯 DISCOVERED ENDPOINTS:{Style.RESET_ALL}")
        
        # Group by target
        targets_dict = {}
        for endpoint in found_endpoints:
            target = endpoint['target']
            if target not in targets_dict:
                targets_dict[target] = []
            targets_dict[target].append(endpoint)
        
        for i, (target, endpoints) in enumerate(targets_dict.items(), 1):
            print(f"\n   {Fore.CYAN}[{i}] Target: {target}{Style.RESET_ALL}")
            for j, endpoint in enumerate(endpoints, 1):
                print(f"       {Fore.GREEN}└─ [{j}] {endpoint['url']}{Style.RESET_ALL}")
                if len(endpoints) > 1:
                    print(f"           {Fore.YELLOW}Endpoint: {endpoint['endpoint']}{Style.RESET_ALL}")
        
        # Save results to file
        save_results_to_file()
        
    else:
        print(f"\n{Fore.YELLOW}   No GraphQL endpoints were discovered in this scan.{Style.RESET_ALL}")
        print(f"   {Fore.WHITE}Consider trying different payloads or checking target accessibility.{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║                            SCAN COMPLETED                                ║")
    print(f"{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")

def save_results_to_file():
    """Save results to a formatted file"""
    global found_endpoints
    
    if not found_endpoints:
        return
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"graphql_scan_results_{timestamp}.txt"
    
    try:
        with open(filename, 'w') as f:
            f.write("GraphQL Endpoint Scan Results\n")
            f.write("=" * 50 + "\n")
            f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Endpoints Found: {len(found_endpoints)}\n\n")
            
            # Group by target
            targets_dict = {}
            for endpoint in found_endpoints:
                target = endpoint['target']
                if target not in targets_dict:
                    targets_dict[target] = []
                targets_dict[target].append(endpoint)
            
            for target, endpoints in targets_dict.items():
                f.write(f"Target: {target}\n")
                f.write("-" * (len(target) + 8) + "\n")
                for endpoint in endpoints:
                    f.write(f"  • {endpoint['url']}\n")
                    f.write(f"    Endpoint: {endpoint['endpoint']}\n")
                    f.write(f"    Status: {endpoint['status']}\n")
                    f.write(f"    Found at: {endpoint['timestamp']}\n\n")
                f.write("\n")
        
        print_info(f"Results saved to: {filename}")
        
    except Exception as e:
        print_info(f"Failed to save results: {str(e)}")

def validate_url(url):
    """Validate and normalize URL format"""
    url = url.strip().rstrip('/')
    if not url.startswith(('http://', 'https://')):
        return [f'https://{url}', f'http://{url}']
    return [url]

def main():
    """Enhanced main function with dirsearch-style progress"""
    global total_tasks, continue_execution, start_time
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(BANNER)
    
    parser = argparse.ArgumentParser(
        description=f"{Fore.YELLOW}Enhanced GraphQL endpoint detection tool with clean progress.{Style.RESET_ALL}",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', '--domain', help='Single domain to test (e.g., example.com)')
    group.add_argument('-l', '--list', help='File containing list of domains/subdomains')
    
    parser.add_argument('-t', '--threads', type=int, default=50, 
                       help='Number of threads (default: 50)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Verbose mode')
    parser.add_argument('-q', '--quiet', action='store_true', 
                       help='Quiet mode (only show results)')
    parser.add_argument('-p', '--proxy', help='HTTP/SOCKS proxy')
    parser.add_argument('--timeout', type=int, default=10, 
                       help='Request timeout (default: 10)')
    
    args = parser.parse_args()
    
    # Input processing
    urls_to_scan = []
    
    if args.domain:
        urls_to_scan.extend(validate_url(args.domain))
        print_info(f"Single domain mode: {args.domain}")
    else:
        try:
            with open(args.list, 'r') as f:
                domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            for domain in domains:
                urls_to_scan.extend(validate_url(domain))
                
            print_info(f"Loaded {len(domains)} domains from {args.list}")
            
        except FileNotFoundError:
            print_info(f"Error: Domain list file '{args.list}' not found")
            sys.exit(1)
        except Exception as e:
            print_info(f"Error reading domain list: {str(e)}")
            sys.exit(1)
    
    if not urls_to_scan:
        print_info("Error: No valid URLs to scan")
        sys.exit(1)
    
    # Remove duplicates
    urls_to_scan = list(dict.fromkeys(urls_to_scan))
    total_tasks = len(urls_to_scan)
    
    print_info(f"Prepared {total_tasks} URLs for scanning")
    print_info(f"Using {args.threads} threads with {args.timeout}s timeout")
    
    if args.proxy:
        print_info(f"Using proxy: {args.proxy}")
    
    # Create work queue
    work_queue = queue.Queue()
    for url in urls_to_scan:
        work_queue.put(url)
    
    # Start threads
    threads = []
    start_time = time.time()
    
    print_info("Starting GraphQL endpoint scan...")
    print()  # Empty line before progress
    
    for _ in range(min(args.threads, total_tasks)):
        t = threading.Thread(target=worker, args=(work_queue, args))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Initial progress display
    if not args.quiet:
        update_progress()
    
    # Wait for completion
    try:
        work_queue.join()
    except KeyboardInterrupt:
        pass
    
    # Final progress update
    if not args.quiet:
        print(f"\r{' ' * 100}\r", end='')
    
    # Show final results
    show_final_results()

if __name__ == "__main__":
    main()