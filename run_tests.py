#!/usr/bin/env python3
"""
Comprehensive test runner for OneDocs RAG system
"""
import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.test_utilities import check_docker_services, save_test_results


def run_command(cmd: List[str], capture_output: bool = True) -> Dict[str, Any]:
    """Run a command and return results"""
    print(f"Running: {' '.join(cmd)}")
    
    try:
        if capture_output:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=project_root
            )
        else:
            result = subprocess.run(cmd, cwd=project_root)
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": getattr(result, 'stdout', ''),
            "stderr": getattr(result, 'stderr', ''),
            "command": ' '.join(cmd)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": ' '.join(cmd)
        }


def check_dependencies() -> bool:
    """Check if all required dependencies are installed"""
    print("Checking dependencies...")
    
    required_packages = [
        "pytest", "pytest-cov", "fastapi", "pymilvus", 
        "minio", "pymupdf", "numpy", "sentence-transformers"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    print("All dependencies are installed ✅")
    return True


def setup_test_environment() -> bool:
    """Set up test environment"""
    print("Setting up test environment...")
    
    # Create test output directory
    test_output = project_root / "test_output"
    test_output.mkdir(exist_ok=True)
    
    # Set environment variables for testing
    test_env = {
        "PYTHONPATH": str(project_root),
        "MILVUS_HOST": "localhost",
        "MILVUS_PORT": "19530",
        "MINIO_ENDPOINT": "localhost:9000",
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "test_key_123"),
        "LLM_PROVIDER": "openai"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("Test environment configured ✅")
    return True


def run_unit_tests(verbose: bool = False, coverage: bool = True) -> Dict[str, Any]:
    """Run unit tests"""
    print("\n" + "="*60)
    print("RUNNING UNIT TESTS")
    print("="*60)
    
    cmd = ["python", "-m", "pytest", "tests/unit/", "-v" if verbose else "", "-x"]
    
    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html:test_output/htmlcov_unit",
            "--cov-report=json:test_output/coverage_unit.json",
            "--cov-report=term-missing"
        ])
    
    cmd.extend([
        "--junitxml=test_output/unit_results.xml",
        "--json-report", "--json-report-file=test_output/unit_report.json"
    ])
    
    # Remove empty strings
    cmd = [c for c in cmd if c]
    
    return run_command(cmd, capture_output=False)


def run_integration_tests(verbose: bool = False, skip_docker: bool = False) -> Dict[str, Any]:
    """Run integration tests"""
    print("\n" + "="*60)
    print("RUNNING INTEGRATION TESTS")
    print("="*60)
    
    if not skip_docker:
        # Check Docker services
        docker_status = check_docker_services()
        if not docker_status["all"]:
            print("⚠️  Some Docker services are not available:")
            for service, status in docker_status.items():
                if service != "all":
                    print(f"  {service}: {'✅' if status else '❌'}")
            print("\nSkipping Docker-dependent tests...")
            skip_docker = True
    
    cmd = ["python", "-m", "pytest", "tests/integration/", "-v" if verbose else ""]
    
    if skip_docker:
        cmd.extend(["-m", "not requires_docker"])
    
    cmd.extend([
        "--junitxml=test_output/integration_results.xml",
        "--json-report", "--json-report-file=test_output/integration_report.json"
    ])
    
    # Remove empty strings
    cmd = [c for c in cmd if c]
    
    return run_command(cmd, capture_output=False)


def run_existing_validation_scripts() -> Dict[str, List[Dict[str, Any]]]:
    """Run existing validation scripts"""
    print("\n" + "="*60)
    print("RUNNING EXISTING VALIDATION SCRIPTS")
    print("="*60)
    
    scripts = [
        "simple_validation.py",
        "test_docker_services.py", 
        "integration_test.py"
    ]
    
    results = {"scripts": []}
    
    for script in scripts:
        script_path = project_root / script
        if script_path.exists():
            print(f"\nRunning {script}...")
            result = run_command(["python", script])
            result["script"] = script
            results["scripts"].append(result)
        else:
            print(f"Script {script} not found, skipping...")
    
    return results


def run_api_tests(verbose: bool = False) -> Dict[str, Any]:
    """Run API endpoint tests"""
    print("\n" + "="*60)
    print("RUNNING API TESTS")
    print("="*60)
    
    cmd = [
        "python", "-m", "pytest", 
        "tests/integration/test_api.py", 
        "-v" if verbose else "",
        "--junitxml=test_output/api_results.xml",
        "--json-report", "--json-report-file=test_output/api_report.json"
    ]
    
    # Remove empty strings
    cmd = [c for c in cmd if c]
    
    return run_command(cmd, capture_output=False)


def run_performance_tests() -> Dict[str, Any]:
    """Run performance tests"""
    print("\n" + "="*60)
    print("RUNNING PERFORMANCE TESTS")
    print("="*60)
    
    cmd = [
        "python", "-m", "pytest", 
        "-m", "slow",
        "tests/",
        "--junitxml=test_output/performance_results.xml",
        "--json-report", "--json-report-file=test_output/performance_report.json"
    ]
    
    return run_command(cmd, capture_output=False)


def generate_test_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive test summary"""
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": str(project_root)
        },
        "docker_services": check_docker_services(),
        "test_results": results,
        "overall_success": True
    }
    
    # Determine overall success
    for test_type, result in results.items():
        if isinstance(result, dict) and not result.get("success", False):
            summary["overall_success"] = False
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and not item.get("success", False):
                    summary["overall_success"] = False
    
    # Count test statistics
    summary["statistics"] = {
        "total_test_suites": len([r for r in results.values() if r]),
        "successful_suites": len([r for r in results.values() if isinstance(r, dict) and r.get("success")]),
        "docker_services_available": sum(summary["docker_services"].values()) - 1  # Exclude 'all' key
    }
    
    return summary


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="OneDocs RAG System Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--api", action="store_true", help="Run API tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--existing", action="store_true", help="Run existing validation scripts only")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker-dependent tests")
    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", default="test_output", help="Output directory for results")
    
    args = parser.parse_args()
    
    print("🚀 OneDocs RAG System Test Runner")
    print("="*60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup environment
    if not setup_test_environment():
        sys.exit(1)
    
    # Determine which tests to run
    run_all = not any([args.unit, args.integration, args.api, args.performance, args.existing])
    
    results = {}
    
    # Run tests based on arguments
    if args.unit or run_all:
        results["unit_tests"] = run_unit_tests(
            verbose=args.verbose, 
            coverage=not args.no_coverage
        )
    
    if args.integration or run_all:
        results["integration_tests"] = run_integration_tests(
            verbose=args.verbose,
            skip_docker=args.skip_docker
        )
    
    if args.api or run_all:
        results["api_tests"] = run_api_tests(verbose=args.verbose)
    
    if args.performance or run_all:
        results["performance_tests"] = run_performance_tests()
    
    if args.existing or run_all:
        results["existing_scripts"] = run_existing_validation_scripts()
    
    # Generate summary
    summary = generate_test_summary(results)
    
    # Save results
    results_file = save_test_results(summary, args.output)
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Overall Success: {'✅ PASS' if summary['overall_success'] else '❌ FAIL'}")
    print(f"Test Suites Run: {summary['statistics']['total_test_suites']}")
    print(f"Successful Suites: {summary['statistics']['successful_suites']}")
    print(f"Docker Services Available: {summary['statistics']['docker_services_available']}/3")
    print(f"\nDetailed results saved to: {results_file}")
    
    # Print individual test results
    for test_type, result in results.items():
        if isinstance(result, dict):
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            print(f"  {test_type}: {status}")
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    status = "✅ PASS" if item.get("success") else "❌ FAIL"
                    script_name = item.get("script", "unknown")
                    print(f"  {script_name}: {status}")
    
    print(f"\nTest artifacts saved in: {Path(args.output).absolute()}")
    print("  - HTML Coverage Report: htmlcov_unit/index.html")
    print("  - JSON Reports: *.json")
    print("  - JUnit XML: *.xml")
    
    # Exit with appropriate code
    sys.exit(0 if summary["overall_success"] else 1)


if __name__ == "__main__":
    main()