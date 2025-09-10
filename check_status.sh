#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    Service Health Check Dashboard${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    local service=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${GREEN}✅ $service is running on port $port${NC}"
        return 0
    else
        echo -e "${RED}❌ $service is NOT running on port $port${NC}"
        return 1
    fi
}

# Function to check health endpoint
check_health() {
    local url=$1
    local service=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" $url 2>/dev/null)
    
    if [ "$response" == "200" ]; then
        echo -e "${GREEN}   ├─ Health check: OK (200)${NC}"
        
        # Get detailed health info if available
        if [ "$service" == "FastAPI" ]; then
            health_data=$(curl -s $url 2>/dev/null)
            echo -e "${GREEN}   └─ Response: $health_data${NC}"
        fi
    elif [ "$response" == "000" ]; then
        echo -e "${YELLOW}   └─ Health check: Service not responding${NC}"
    else
        echo -e "${YELLOW}   └─ Health check: HTTP $response${NC}"
    fi
}

# Function to check Docker services
check_docker_service() {
    local service=$1
    
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$service"; then
        status=$(docker ps --format "{{.Status}}" -f "name=$service")
        echo -e "${GREEN}✅ Docker: $service - $status${NC}"
    else
        echo -e "${RED}❌ Docker: $service is not running${NC}"
    fi
}

echo -e "${YELLOW}1. Application Services${NC}"
echo "----------------------------------------"

# Check FastAPI
check_port 8080 "FastAPI"
if [ $? -eq 0 ]; then
    check_health "http://localhost:8080/health" "FastAPI"
    echo -e "${BLUE}   📖 API Docs: http://localhost:8080/docs${NC}"
fi
echo ""

# Check Streamlit
check_port 8501 "Streamlit"
if [ $? -eq 0 ]; then
    echo -e "${BLUE}   🎨 UI: http://localhost:8501${NC}"
fi
echo ""

echo -e "${YELLOW}2. Docker Services${NC}"
echo "----------------------------------------"

# Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
else
    # Check individual services
    check_docker_service "main-milvus-1"
    check_docker_service "main-minio-1"
    check_docker_service "main-etcd-1"
    check_docker_service "main-attu-1"
    
    echo ""
    echo -e "${YELLOW}3. Service Interfaces${NC}"
    echo "----------------------------------------"
    
    # MinIO
    if docker ps | grep -q "main-minio-1"; then
        echo -e "${GREEN}✅ MinIO Console: http://localhost:9001${NC}"
        echo -e "   └─ Credentials: minioadmin/minioadmin"
    fi
    
    # Milvus Attu
    if docker ps | grep -q "main-attu-1"; then
        echo -e "${GREEN}✅ Milvus Attu: http://localhost:8000${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}4. Resource Usage${NC}"
echo "----------------------------------------"

# Show Python processes
python_procs=$(ps aux | grep python | grep -E "(production_server|streamlit)" | grep -v grep)
if [ ! -z "$python_procs" ]; then
    echo -e "${GREEN}Python Processes:${NC}"
    echo "$python_procs" | while read line; do
        pid=$(echo $line | awk '{print $2}')
        cpu=$(echo $line | awk '{print $3}')
        mem=$(echo $line | awk '{print $4}')
        cmd=$(echo $line | awk '{for(i=11;i<=NF;i++) printf "%s ", $i}')
        echo -e "   PID: $pid | CPU: ${cpu}% | MEM: ${mem}% | ${cmd:0:50}..."
    done
else
    echo -e "${YELLOW}No Python services running${NC}"
fi

echo ""
echo -e "${YELLOW}5. Port Summary${NC}"
echo "----------------------------------------"
echo "Service         | Port  | Status"
echo "----------------|-------|--------"

# Check all relevant ports
ports=("8080:FastAPI" "8501:Streamlit" "9000:MinIO-API" "9001:MinIO-Console" "19530:Milvus" "8000:Attu" "2379:ETCD")

for port_info in "${ports[@]}"; do
    IFS=':' read -r port service <<< "$port_info"
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        printf "%-15s | %-5s | ✅\n" "$service" "$port"
    else
        printf "%-15s | %-5s | ❌\n" "$service" "$port"
    fi
done

echo ""
echo -e "${YELLOW}6. Quick Tests${NC}"
echo "----------------------------------------"

# Test MinIO connection
if docker ps | grep -q "main-minio-1"; then
    buckets=$(docker exec main-minio-1 mc ls local 2>/dev/null | wc -l)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ MinIO: $buckets buckets found${NC}"
    fi
fi

# Test Milvus connection via API if FastAPI is running
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    collections=$(curl -s http://localhost:8080/health 2>/dev/null | grep -o '"collections":[0-9]*' | grep -o '[0-9]*')
    if [ ! -z "$collections" ]; then
        echo -e "${GREEN}✅ Milvus: $collections collections available${NC}"
    fi
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}         Check Complete${NC}"
echo -e "${BLUE}========================================${NC}"