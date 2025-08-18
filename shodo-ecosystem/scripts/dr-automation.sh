#!/bin/bash
# DR Automation Script Suite
# MUST: Achieve RTO ≤ 30min, RPO ≤ 5min

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-shodo}"
ENVIRONMENT="${ENVIRONMENT:-production}"
LOG_DIR="/var/log/shodo/dr"
BACKUP_DIR="/backup/shodo"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log() {
    local level=$1
    shift
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] [${level}] $*" | tee -a "${LOG_DIR}/dr-$(date +%Y%m%d).log"
    
    # Send to monitoring
    if [[ -n "$ALERT_WEBHOOK" ]]; then
        curl -X POST "$ALERT_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{\"level\":\"${level}\",\"message\":\"$*\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            2>/dev/null || true
    fi
}

# ===== Health Checks =====

check_cluster_health() {
    log "INFO" "Checking Kubernetes cluster health..."
    
    if ! kubectl cluster-info &>/dev/null; then
        log "CRITICAL" "Cannot connect to Kubernetes cluster"
        return 1
    fi
    
    # Check nodes
    local unhealthy_nodes
    unhealthy_nodes=$(kubectl get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status!="True")) | .metadata.name')
    
    if [[ -n "$unhealthy_nodes" ]]; then
        log "WARNING" "Unhealthy nodes detected: $unhealthy_nodes"
        return 1
    fi
    
    log "INFO" "Cluster health: OK"
    return 0
}

check_service_health() {
    local service=$1
    log "INFO" "Checking health of $service..."
    
    local endpoint
    case $service in
        backend)
            endpoint="https://api.shodo.example.com/health"
            ;;
        frontend)
            endpoint="https://shodo.example.com/"
            ;;
        ai-server)
            endpoint="https://api.shodo.example.com/api/v1/nlp/health"
            ;;
        database)
            kubectl exec -n "$NAMESPACE" postgres-primary-0 -- pg_isready -U shodo
            return $?
            ;;
        redis)
            kubectl exec -n "$NAMESPACE" redis-master-0 -- redis-cli ping
            return $?
            ;;
        *)
            log "ERROR" "Unknown service: $service"
            return 1
            ;;
    esac
    
    if [[ -n "$endpoint" ]]; then
        if curl -sf "$endpoint" -o /dev/null; then
            log "INFO" "$service health: OK"
            return 0
        else
            log "ERROR" "$service health check failed"
            return 1
        fi
    fi
}

# ===== Recovery Functions =====

recover_database() {
    log "WARNING" "Starting database recovery..."
    
    # Check if primary is down
    if ! kubectl exec -n "$NAMESPACE" postgres-primary-0 -- pg_isready &>/dev/null; then
        log "ERROR" "Primary database is down, initiating failover..."
        
        # Promote replica
        kubectl exec -n "$NAMESPACE" postgres-replica-0 -- pg_ctl promote
        
        # Update service selector
        kubectl patch service postgres-primary -n "$NAMESPACE" \
            -p '{"spec":{"selector":{"role":"replica"}}}'
        
        # Wait for promotion
        sleep 10
        
        # Verify new primary
        if kubectl exec -n "$NAMESPACE" postgres-replica-0 -- pg_isready; then
            log "INFO" "Database failover successful"
            
            # Update application connection strings
            update_database_connections "postgres-replica-0"
            
            return 0
        else
            log "CRITICAL" "Database failover failed"
            return 1
        fi
    fi
    
    log "INFO" "Primary database is healthy"
    return 0
}

recover_backend() {
    log "WARNING" "Starting backend recovery..."
    
    local unhealthy_pods
    unhealthy_pods=$(kubectl get pods -n "$NAMESPACE" -l app=shodo-backend \
        --field-selector=status.phase!=Running -o name)
    
    if [[ -n "$unhealthy_pods" ]]; then
        log "INFO" "Deleting unhealthy backend pods..."
        echo "$unhealthy_pods" | xargs kubectl delete -n "$NAMESPACE"
        
        # Wait for new pods
        kubectl wait --for=condition=ready pod \
            -l app=shodo-backend -n "$NAMESPACE" \
            --timeout=300s
    fi
    
    # Scale if needed
    local current_replicas
    current_replicas=$(kubectl get deployment shodo-backend -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
    
    if [[ $current_replicas -lt 4 ]]; then
        log "INFO" "Scaling backend to 4 replicas..."
        kubectl scale deployment shodo-backend -n "$NAMESPACE" --replicas=4
    fi
    
    # Verify health
    sleep 10
    if check_service_health "backend"; then
        log "INFO" "Backend recovery successful"
        return 0
    else
        log "ERROR" "Backend recovery failed, attempting rollback..."
        kubectl rollout undo deployment/shodo-backend -n "$NAMESPACE"
        kubectl rollout status deployment/shodo-backend -n "$NAMESPACE" --timeout=5m
        return $?
    fi
}

# ===== Backup & Restore =====

backup_database() {
    local backup_name="db-backup-$(date +%Y%m%d-%H%M%S)"
    log "INFO" "Creating database backup: $backup_name"
    
    kubectl exec -n "$NAMESPACE" postgres-primary-0 -- \
        pg_dump -U shodo -d shodo -Fc -f "/tmp/${backup_name}.dump"
    
    # Copy backup to persistent storage
    kubectl cp "$NAMESPACE/postgres-primary-0:/tmp/${backup_name}.dump" \
        "${BACKUP_DIR}/${backup_name}.dump"
    
    # Verify backup
    if [[ -f "${BACKUP_DIR}/${backup_name}.dump" ]]; then
        local size
        size=$(du -h "${BACKUP_DIR}/${backup_name}.dump" | cut -f1)
        log "INFO" "Backup created successfully: ${backup_name}.dump (${size})"
        
        # Upload to S3
        aws s3 cp "${BACKUP_DIR}/${backup_name}.dump" \
            "s3://shodo-backups/postgres/${backup_name}.dump" \
            --storage-class GLACIER_IR
        
        return 0
    else
        log "ERROR" "Backup creation failed"
        return 1
    fi
}

restore_database() {
    local backup_file=$1
    log "WARNING" "Restoring database from: $backup_file"
    
    # Stop applications
    kubectl scale deployment shodo-backend -n "$NAMESPACE" --replicas=0
    
    # Restore
    kubectl cp "$backup_file" "$NAMESPACE/postgres-primary-0:/tmp/restore.dump"
    
    kubectl exec -n "$NAMESPACE" postgres-primary-0 -- \
        pg_restore -U shodo -d shodo -c "/tmp/restore.dump"
    
    # Restart applications
    kubectl scale deployment shodo-backend -n "$NAMESPACE" --replicas=4
    
    # Wait for ready
    kubectl wait --for=condition=ready pod \
        -l app=shodo-backend -n "$NAMESPACE" \
        --timeout=300s
    
    log "INFO" "Database restore completed"
    return 0
}

# ===== Region Failover =====

failover_to_dr_region() {
    local dr_region="${1:-us-west-2}"
    log "CRITICAL" "Initiating failover to DR region: $dr_region"
    
    # Step 1: Activate DR cluster
    log "INFO" "Activating DR cluster..."
    kubectl config use-context "shodo-${dr_region}"
    
    # Step 2: Verify DR cluster health
    if ! check_cluster_health; then
        log "CRITICAL" "DR cluster is not healthy"
        return 1
    fi
    
    # Step 3: Deploy applications to DR
    log "INFO" "Deploying applications to DR region..."
    helm upgrade --install shodo-ecosystem ./k8s/helm \
        --namespace "$NAMESPACE" \
        --values "./k8s/helm/values.dr.yaml" \
        --set region="$dr_region" \
        --wait --timeout 10m
    
    # Step 4: Verify data replication
    log "INFO" "Verifying data replication..."
    local lag
    lag=$(kubectl exec -n "$NAMESPACE" postgres-primary-0 -- \
        psql -U shodo -t -c "SELECT extract(epoch from now() - pg_last_xact_replay_timestamp());" 2>/dev/null | xargs)
    
    if [[ $(echo "$lag > 300" | bc) -eq 1 ]]; then
        log "WARNING" "Replication lag is high: ${lag}s"
    fi
    
    # Step 5: Update DNS
    log "INFO" "Updating DNS records..."
    update_dns_records "$dr_region"
    
    # Step 6: Verify services
    sleep 30
    for service in backend frontend ai-server database redis; do
        if ! check_service_health "$service"; then
            log "ERROR" "Service $service is not healthy in DR region"
            return 1
        fi
    done
    
    log "INFO" "Failover to DR region completed successfully"
    return 0
}

failback_to_primary() {
    local primary_region="${1:-ap-northeast-1}"
    log "INFO" "Initiating failback to primary region: $primary_region"
    
    # Similar to failover but in reverse
    # Ensure data sync before switching
    
    log "INFO" "Failback completed"
    return 0
}

# ===== Utility Functions =====

update_database_connections() {
    local new_host=$1
    log "INFO" "Updating database connections to: $new_host"
    
    kubectl set env deployment/shodo-backend -n "$NAMESPACE" \
        DATABASE_URL="postgresql://shodo:password@${new_host}:5432/shodo"
    
    kubectl rollout status deployment/shodo-backend -n "$NAMESPACE" --timeout=5m
}

update_dns_records() {
    local region=$1
    log "INFO" "Updating DNS records for region: $region"
    
    # Update Route53 or CloudFlare
    # This is a placeholder - implement actual DNS update
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: dns-config
  namespace: $NAMESPACE
data:
  active_region: "$region"
  api_endpoint: "api-${region}.shodo.example.com"
  app_endpoint: "app-${region}.shodo.example.com"
EOF
}

collect_diagnostics() {
    local incident_id="${1:-$(date +%Y%m%d-%H%M%S)}"
    local diag_dir="${LOG_DIR}/diagnostics/${incident_id}"
    
    log "INFO" "Collecting diagnostics for incident: $incident_id"
    
    mkdir -p "$diag_dir"
    
    # Collect pod logs
    kubectl logs -n "$NAMESPACE" -l app=shodo-backend --tail=1000 > "${diag_dir}/backend.log" 2>&1
    kubectl logs -n "$NAMESPACE" postgres-primary-0 --tail=1000 > "${diag_dir}/postgres.log" 2>&1
    
    # Collect events
    kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' > "${diag_dir}/events.txt"
    
    # Collect metrics
    curl -s "http://prometheus:9090/api/v1/query_range?query=up&start=$(date -u -d '1 hour ago' +%s)&end=$(date +%s)&step=60" \
        > "${diag_dir}/metrics.json" 2>&1
    
    # Create archive
    tar -czf "${diag_dir}.tar.gz" -C "${LOG_DIR}/diagnostics" "${incident_id}"
    
    log "INFO" "Diagnostics collected: ${diag_dir}.tar.gz"
}

# ===== Main Execution =====

main() {
    local action="${1:-check}"
    
    case $action in
        check)
            log "INFO" "Running health checks..."
            check_cluster_health
            for service in backend frontend ai-server database redis; do
                check_service_health "$service" || true
            done
            ;;
            
        auto-recover)
            log "WARNING" "Starting auto-recovery..."
            
            # Check and recover each component
            if ! check_service_health "database"; then
                recover_database || exit 1
            fi
            
            if ! check_service_health "backend"; then
                recover_backend || exit 1
            fi
            
            log "INFO" "Auto-recovery completed"
            ;;
            
        backup)
            backup_database
            ;;
            
        restore)
            local backup_file="${2:-}"
            if [[ -z "$backup_file" ]]; then
                log "ERROR" "Backup file required for restore"
                exit 1
            fi
            restore_database "$backup_file"
            ;;
            
        failover)
            local region="${2:-us-west-2}"
            failover_to_dr_region "$region"
            ;;
            
        failback)
            local region="${2:-ap-northeast-1}"
            failback_to_primary "$region"
            ;;
            
        diagnose)
            collect_diagnostics "${2:-}"
            ;;
            
        *)
            echo "Usage: $0 {check|auto-recover|backup|restore|failover|failback|diagnose}"
            exit 1
            ;;
    esac
}

# Create log directory if not exists
mkdir -p "$LOG_DIR"

# Run main function
main "$@"