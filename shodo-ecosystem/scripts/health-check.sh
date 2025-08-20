#!/bin/bash

# Comprehensive Health Check and Validation Script
# System-wide operational verification

set -e

echo "Shodo Ecosystem - Comprehensive Health Check"
echo "============================================"

# Status reporting functions
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo "[OK] $message"
            ;;
        "WARN")
            echo "[WARN] $message"
            ;;
        "ERROR")
            echo "[ERROR] $message"
            ;;
        "INFO")
            echo "[INFO] $message"
            ;;
    esac
}

# Service connectivity verification
check_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}
    
    if curl -f -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        print_status "OK" "$service_name is responding"
        return 0
    else
        print_status "ERROR" "$service_name is not responding at $url"
        return 1
    fi
}

# JSON response validation
check_json_endpoint() {
    local name=$1
    local url=$2
    local expected_field=$3
    
    response=$(curl -s "$url" 2>/dev/null)
    if echo "$response" | jq -e ".$expected_field" >/dev/null 2>&1; then
        print_status "OK" "$name JSON response is valid"
        return 0
    else
        print_status "ERROR" "$name JSON response is invalid"
        echo "Response: $response"
        return 1
    fi
}

# Docker Compose service verification
check_docker_services() {
    echo ""
    echo "Docker Services Status"
    echo "---------------------"
    
    services=$(docker-compose ps --services 2>/dev/null || echo "")
    if [ -z "$services" ]; then
        print_status "WARN" "Docker Compose not running or no services defined"
        return 1
    fi
    
    for service in $services; do
        status=$(docker-compose ps -q "$service" | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
        case $status in
            "running")
                print_status "OK" "Service $service is running"
                ;;
            "exited")
                print_status "ERROR" "Service $service has exited"
                ;;
            "not_found")
                print_status "WARN" "Service $service not found"
                ;;
            *)
                print_status "WARN" "Service $service status: $status"
                ;;
        esac
    done
}

# Network connectivity verification
check_network_connectivity() {
    echo ""
    echo "Network Connectivity"
    echo "-------------------"
    
    # Internal network verification
    if docker network ls | grep -q shodo-network; then
        print_status "OK" "Shodo network exists"
    else
        print_status "WARN" "Shodo network not found"
    fi
    
    # External connectivity verification
    if curl -s --connect-timeout 5 https://httpbin.org/status/200 >/dev/null; then
        print_status "OK" "External connectivity available"
    else
        print_status "WARN" "External connectivity limited"
    fi
}

# Core API endpoint verification
check_core_apis() {
    echo ""
    echo "Core API Endpoints"
    echo "-----------------"
    
    base_url="http://localhost"
    
    # Health check verification
    check_service "Health Check" "$base_url/health"
    check_json_endpoint "Health Check" "$base_url/health" "status"
    
    # Simple health check verification
    check_service "Simple Health" "$base_url/health/simple"
    
    # Root endpoint verification
    check_service "Root Endpoint" "$base_url/"
    check_json_endpoint "Root Endpoint" "$base_url/" "name"
    
    # Metrics verification
    if check_service "Metrics" "$base_url/metrics"; then
        # Prometheus format verification
        if curl -s "$base_url/metrics" | grep -q "# HELP"; then
            print_status "OK" "Metrics format is valid"
        else
            print_status "WARN" "Metrics format may be invalid"
        fi
    fi
    
    # API documentation verification (development environment only)
    if curl -s "$base_url/api/docs" | grep -q "Swagger"; then
        print_status "OK" "API documentation is available"
    else
        print_status "INFO" "API documentation not available (production mode)"
    fi
}

# Database connectivity verification
check_database() {
    echo ""
    echo "Database Connectivity"
    echo "--------------------"
    
    # PostgreSQL connectivity verification
    if docker-compose exec -T postgres pg_isready -U shodo >/dev/null 2>&1; then
        print_status "OK" "PostgreSQL is ready"
        
        # Table verification
        table_count=$(docker-compose exec -T postgres psql -U shodo -d shodo -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        if [ "$table_count" -gt 0 ]; then
            print_status "OK" "Database has $table_count tables"
        else
            print_status "WARN" "Database has no tables - may need initialization"
        fi
    else
        print_status "ERROR" "PostgreSQL is not ready"
    fi
    
    # Redis connectivity verification
    if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        print_status "OK" "Redis is responding"
    else
        print_status "WARN" "Redis is not responding"
    fi
}

# AI server verification
check_ai_server() {
    echo ""
    echo "AI Server Status"
    echo "---------------"
    
    ai_url="http://localhost:8001"
    
    if check_service "AI Server" "$ai_url/health"; then
        # Model information verification
        if check_json_endpoint "AI Server" "$ai_url/health" "status"; then
            model=$(curl -s "$ai_url/health" | jq -r '.model // "unknown"' 2>/dev/null)
            engine=$(curl -s "$ai_url/health" | jq -r '.engine // "unknown"' 2>/dev/null)
            print_status "OK" "AI Server - Model: $model, Engine: $engine"
        fi
    fi
}

# Frontend verification
check_frontend() {
    echo ""
    echo "Frontend Status"
    echo "--------------"
    
    frontend_url="http://localhost:3000"
    
    if check_service "Frontend" "$frontend_url"; then
        # React application verification
        if curl -s "$frontend_url" | grep -q "react"; then
            print_status "OK" "Frontend React app is loaded"
        else
            print_status "WARN" "Frontend may not be a React app"
        fi
    fi
}

# Resource usage verification
check_resource_usage() {
    echo ""
    echo "Resource Usage"
    echo "-------------"
    
    # Docker container resource usage
    if command -v docker >/dev/null 2>&1; then
        echo "Container Resource Usage:"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || print_status "WARN" "Could not get container stats"
    fi
    
    # System resource verification
    if command -v free >/dev/null 2>&1; then
        memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
        print_status "INFO" "System memory usage: ${memory_usage}%"
    fi
    
    if command -v df >/dev/null 2>&1; then
        disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
        print_status "INFO" "Disk usage: ${disk_usage}%"
        
        if [ "$disk_usage" -gt 90 ]; then
            print_status "WARN" "High disk usage detected"
        fi
    fi
}

# Performance testing
performance_test() {
    echo ""
    echo "Performance Test"
    echo "---------------"
    
    # Response time testing
    base_url="http://localhost"
    
    for endpoint in "/health/simple" "/"; do
        start_time=$(date +%s%N)
        if curl -s -o /dev/null "$base_url$endpoint"; then
            end_time=$(date +%s%N)
            response_time=$(( (end_time - start_time) / 1000000 ))
            
            if [ "$response_time" -lt 100 ]; then
                print_status "OK" "$endpoint response time: ${response_time}ms"
            elif [ "$response_time" -lt 500 ]; then
                print_status "WARN" "$endpoint response time: ${response_time}ms (slow)"
            else
                print_status "ERROR" "$endpoint response time: ${response_time}ms (too slow)"
            fi
        else
            print_status "ERROR" "$endpoint is not responding"
        fi
    done
}

# Security verification
security_check() {
    echo ""
    echo "Security Check"
    echo "-------------"
    
    base_url="http://localhost"
    
    # Security header verification
    headers=$(curl -s -I "$base_url/" 2>/dev/null)
    
    security_headers=(
        "X-Content-Type-Options"
        "X-Frame-Options"
        "X-XSS-Protection"
    )
    
    for header in "${security_headers[@]}"; do
        if echo "$headers" | grep -qi "$header"; then
            print_status "OK" "Security header $header is present"
        else
            print_status "WARN" "Security header $header is missing"
        fi
    done
    
    # HTTPS redirect verification (production environment)
    if [ "${ENVIRONMENT:-development}" = "production" ]; then
        if curl -s -I "http://localhost/" | grep -qi "location.*https"; then
            print_status "OK" "HTTPS redirect is configured"
        else
            print_status "WARN" "HTTPS redirect not detected"
        fi
    fi
}

# Log analysis
check_logs() {
    echo ""
    echo "Log Analysis"
    echo "-----------"
    
    # Error log verification
    error_count=$(docker-compose logs --tail=100 2>/dev/null | grep -i error | wc -l)
    if [ "$error_count" -eq 0 ]; then
        print_status "OK" "No recent errors in logs"
    elif [ "$error_count" -lt 5 ]; then
        print_status "WARN" "$error_count recent errors found"
    else
        print_status "ERROR" "$error_count recent errors found - check logs"
    fi
    
    # Warning log verification
    warning_count=$(docker-compose logs --tail=100 2>/dev/null | grep -i warning | wc -l)
    if [ "$warning_count" -lt 3 ]; then
        print_status "OK" "Minimal warnings in logs ($warning_count)"
    else
        print_status "WARN" "$warning_count warnings found"
    fi
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    echo "Starting comprehensive health check at $(date)"
    echo ""
    
    # Execute all checks
    check_docker_services
    check_network_connectivity
    check_core_apis
    check_database
    check_ai_server
    check_frontend
    check_resource_usage
    performance_test
    security_check
    check_logs
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "============================================"
    echo "Health Check Completed in ${duration}s"
    echo ""
    
    # Overall assessment
    if grep -q "\[ERROR\]" /tmp/health_check.log 2>/dev/null; then
        print_status "ERROR" "System has critical issues"
        echo ""
        echo "Recommended actions:"
        echo "  1. Check error logs: docker-compose logs"
        echo "  2. Restart services: docker-compose restart"
        echo "  3. Full reset: docker-compose down && docker-compose up -d"
        exit 1
    elif grep -q "\[WARN\]" /tmp/health_check.log 2>/dev/null; then
        print_status "WARN" "System is operational but has warnings"
        echo ""
        echo "Consider reviewing warnings for optimization"
        exit 0
    else
        print_status "OK" "All systems are healthy"
        echo ""
        echo "System is ready for use"
        echo ""
        echo "Quick Links:"
        echo "  App:     http://localhost"
        echo "  API:     http://localhost/api/docs"
        echo "  Health:  http://localhost/health"
        echo "  Metrics: http://localhost/metrics"
        exit 0
    fi
}

# Log output to file
exec > >(tee /tmp/health_check.log)
exec 2>&1

# Execute main function
main "$@"