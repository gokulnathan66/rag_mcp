"""
HTTP Monitoring Dashboard for MCP Server.

This module provides:
- Comprehensive monitoring dashboard views
- Real-time metrics aggregation and analysis
- Performance trend analysis
- Alert generation and monitoring
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

import logfire
from pydantic import BaseModel

from .http_monitoring import HTTPMonitor, get_http_monitor
from .http_connection_manager import HTTPConnectionManager, get_connection_manager
from .config import HTTPTransportConfig


logger = logging.getLogger(__name__)


class MonitoringDashboard(BaseModel):
    """Comprehensive monitoring dashboard data."""
    
    # Timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Overview metrics
    overview: Dict[str, Any]
    
    # Performance metrics
    performance: Dict[str, Any]
    
    # Traffic analysis
    traffic: Dict[str, Any]
    
    # Error analysis
    errors: Dict[str, Any]
    
    # Connection analysis
    connections: Dict[str, Any]
    
    # Alerts and recommendations
    alerts: List[Dict[str, Any]]
    recommendations: List[str]
    
    # Health status
    health_status: str  # "healthy", "degraded", "unhealthy"


class HTTPMonitoringDashboard:
    """
    HTTP monitoring dashboard for comprehensive system monitoring.
    
    This class provides:
    - Real-time metrics aggregation
    - Performance trend analysis
    - Alert generation
    - Health status assessment
    """
    
    def __init__(
        self,
        http_monitor: Optional[HTTPMonitor] = None,
        connection_manager: Optional[HTTPConnectionManager] = None,
        config: Optional[HTTPTransportConfig] = None
    ):
        """
        Initialize monitoring dashboard.
        
        Args:
            http_monitor: HTTP monitor instance
            connection_manager: HTTP connection manager instance
            config: HTTP transport configuration
        """
        self.http_monitor = http_monitor or get_http_monitor()
        self.connection_manager = connection_manager or get_connection_manager()
        self.config = config
        
        # Alert thresholds
        self.error_rate_threshold = 10.0  # Percentage
        self.response_time_threshold = 5.0  # Seconds
        self.connection_utilization_threshold = 80.0  # Percentage
        self.requests_per_second_threshold = 100.0  # RPS
        
        logger.info("HTTP monitoring dashboard initialized")
        
        logfire.info(
            "HTTP monitoring dashboard initialized",
            error_rate_threshold=self.error_rate_threshold,
            response_time_threshold=self.response_time_threshold,
            connection_utilization_threshold=self.connection_utilization_threshold,
            component="monitoring_dashboard"
        )
    
    async def get_dashboard_data(self) -> MonitoringDashboard:
        """
        Get comprehensive dashboard data.
        
        Returns:
            MonitoringDashboard with all monitoring information
        """
        if not self.http_monitor:
            logger.warning("HTTP monitor not available for dashboard")
            return self._create_empty_dashboard()
        
        try:
            # Get base metrics
            metrics = await self.http_monitor.get_metrics()
            
            # Get detailed analysis
            error_breakdown = await self.http_monitor.get_error_breakdown()
            performance_analysis = await self.http_monitor.get_performance_analysis()
            traffic_analysis = await self.http_monitor.get_traffic_analysis()
            
            # Get connection information
            connection_stats = {}
            if self.connection_manager:
                connection_stats = await self.connection_manager.get_connection_stats()
            
            # Generate alerts and recommendations
            alerts = await self._generate_alerts(metrics, error_breakdown, performance_analysis)
            recommendations = await self._generate_recommendations(metrics, performance_analysis)
            
            # Determine health status
            health_status = self._determine_health_status(metrics, alerts)
            
            # Create overview
            overview = {
                "uptime_seconds": metrics.uptime_seconds,
                "total_requests": metrics.total_requests,
                "requests_per_second": metrics.requests_per_second,
                "success_rate": ((metrics.successful_requests / max(metrics.total_requests, 1)) * 100),
                "active_connections": metrics.active_connections,
                "connection_utilization": metrics.connection_utilization,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate
            }
            
            # Create performance summary
            performance = {
                "response_times": {
                    "avg": metrics.avg_response_time,
                    "min": metrics.min_response_time,
                    "max": metrics.max_response_time,
                    "p95": metrics.p95_response_time,
                    "p99": metrics.p99_response_time
                },
                "throughput": {
                    "requests_per_second": metrics.requests_per_second,
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests
                },
                "analysis": performance_analysis
            }
            
            # Create connections summary
            connections = {
                "current": {
                    "active": metrics.active_connections,
                    "peak": metrics.peak_connections,
                    "total": metrics.total_connections,
                    "utilization": metrics.connection_utilization
                },
                "stats": connection_stats
            }
            
            dashboard = MonitoringDashboard(
                overview=overview,
                performance=performance,
                traffic=traffic_analysis,
                errors=error_breakdown,
                connections=connections,
                alerts=alerts,
                recommendations=recommendations,
                health_status=health_status
            )
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Error generating dashboard data: {e}", exc_info=True)
            
            logfire.error(
                "Dashboard data generation error",
                error=str(e),
                component="monitoring_dashboard"
            )
            
            return self._create_empty_dashboard()
    
    async def _generate_alerts(
        self,
        metrics: Any,
        error_breakdown: Dict[str, Any],
        performance_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []
        
        # Error rate alert
        if metrics.error_rate > self.error_rate_threshold:
            alerts.append({
                "type": "error_rate",
                "severity": "high" if metrics.error_rate > 20 else "medium",
                "message": f"Error rate {metrics.error_rate:.1f}% exceeds threshold {self.error_rate_threshold}%",
                "value": metrics.error_rate,
                "threshold": self.error_rate_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Response time alert
        if metrics.p95_response_time > self.response_time_threshold:
            alerts.append({
                "type": "response_time",
                "severity": "high" if metrics.p95_response_time > 10 else "medium",
                "message": f"P95 response time {metrics.p95_response_time:.3f}s exceeds threshold {self.response_time_threshold}s",
                "value": metrics.p95_response_time,
                "threshold": self.response_time_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Connection utilization alert
        if metrics.connection_utilization > self.connection_utilization_threshold:
            alerts.append({
                "type": "connection_utilization",
                "severity": "high" if metrics.connection_utilization > 95 else "medium",
                "message": f"Connection utilization {metrics.connection_utilization:.1f}% exceeds threshold {self.connection_utilization_threshold}%",
                "value": metrics.connection_utilization,
                "threshold": self.connection_utilization_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # High request rate alert
        if metrics.requests_per_second > self.requests_per_second_threshold:
            alerts.append({
                "type": "high_traffic",
                "severity": "medium",
                "message": f"Request rate {metrics.requests_per_second:.1f} RPS exceeds threshold {self.requests_per_second_threshold} RPS",
                "value": metrics.requests_per_second,
                "threshold": self.requests_per_second_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Server error rate alert (5xx responses)
        server_error_rate = (metrics.status_5xx / max(metrics.total_requests, 1)) * 100
        if server_error_rate > 1.0:  # More than 1% server errors
            alerts.append({
                "type": "server_errors",
                "severity": "high",
                "message": f"Server error rate {server_error_rate:.1f}% indicates system issues",
                "value": server_error_rate,
                "threshold": 1.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return alerts
    
    async def _generate_recommendations(
        self,
        metrics: Any,
        performance_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on current metrics."""
        recommendations = []
        
        # Performance recommendations
        if metrics.avg_response_time > 1.0:
            recommendations.append("Consider optimizing request processing to reduce response times")
        
        if metrics.connection_utilization > 70:
            recommendations.append("Consider increasing max_concurrent_connections or implementing connection pooling")
        
        if metrics.error_rate > 5:
            recommendations.append("Investigate and fix sources of errors to improve reliability")
        
        if metrics.requests_per_second > 50:
            recommendations.append("Monitor system resources and consider implementing load balancing")
        
        # Traffic pattern recommendations
        if metrics.cors_preflight_requests > metrics.mcp_tool_requests * 0.5:
            recommendations.append("High CORS preflight traffic detected - consider optimizing CORS configuration")
        
        if metrics.health_check_requests > metrics.total_requests * 0.3:
            recommendations.append("High health check traffic - consider adjusting health check frequency")
        
        # Resource utilization recommendations
        if metrics.avg_response_size > 1024 * 1024:  # 1MB
            recommendations.append("Large response sizes detected - consider implementing response compression")
        
        if metrics.p99_response_time > metrics.avg_response_time * 5:
            recommendations.append("High response time variance - investigate outlier requests")
        
        return recommendations
    
    def _determine_health_status(self, metrics: Any, alerts: List[Dict[str, Any]]) -> str:
        """Determine overall health status based on metrics and alerts."""
        high_severity_alerts = [alert for alert in alerts if alert.get("severity") == "high"]
        medium_severity_alerts = [alert for alert in alerts if alert.get("severity") == "medium"]
        
        if high_severity_alerts:
            return "unhealthy"
        elif medium_severity_alerts or metrics.error_rate > 5:
            return "degraded"
        else:
            return "healthy"
    
    def _create_empty_dashboard(self) -> MonitoringDashboard:
        """Create empty dashboard when monitoring is not available."""
        return MonitoringDashboard(
            overview={
                "uptime_seconds": 0,
                "total_requests": 0,
                "requests_per_second": 0,
                "success_rate": 0,
                "active_connections": 0,
                "connection_utilization": 0,
                "avg_response_time": 0,
                "error_rate": 0
            },
            performance={
                "response_times": {
                    "avg": 0, "min": 0, "max": 0, "p95": 0, "p99": 0
                },
                "throughput": {
                    "requests_per_second": 0,
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0
                },
                "analysis": {"performance_score": 0, "issues": [], "recommendations": []}
            },
            traffic={"request_types": {}, "status_codes": {}, "bandwidth": {}},
            errors={"total_errors": 0, "error_types": {}, "recent_error_rate_per_second": 0},
            connections={"current": {}, "stats": {}},
            alerts=[],
            recommendations=["HTTP monitoring not available"],
            health_status="unknown"
        )
    
    async def log_dashboard_summary(self) -> None:
        """Log dashboard summary for monitoring."""
        dashboard = await self.get_dashboard_data()
        
        logger.info(
            f"HTTP Dashboard Summary - "
            f"Health: {dashboard.health_status}, "
            f"RPS: {dashboard.overview['requests_per_second']:.1f}, "
            f"Success: {dashboard.overview['success_rate']:.1f}%, "
            f"Connections: {dashboard.overview['active_connections']}, "
            f"Alerts: {len(dashboard.alerts)}"
        )
        
        # Log detailed dashboard data with Logfire
        logfire.info(
            "HTTP monitoring dashboard summary",
            health_status=dashboard.health_status,
            overview=dashboard.overview,
            alert_count=len(dashboard.alerts),
            high_severity_alerts=len([a for a in dashboard.alerts if a.get("severity") == "high"]),
            recommendation_count=len(dashboard.recommendations),
            component="monitoring_dashboard"
        )
        
        # Log alerts if any
        for alert in dashboard.alerts:
            if alert.get("severity") == "high":
                logger.warning(f"High severity alert: {alert['message']}")
                logfire.warning(
                    "High severity monitoring alert",
                    alert_type=alert["type"],
                    message=alert["message"],
                    value=alert.get("value"),
                    threshold=alert.get("threshold"),
                    component="monitoring_dashboard"
                )
    
    async def check_and_log_alerts(self) -> None:
        """Check for alerts and log them appropriately."""
        if not self.http_monitor:
            return
        
        try:
            # Check error rate alerts
            await self.http_monitor.log_error_rate_alert(self.error_rate_threshold)
            
            # Check performance alerts
            await self.http_monitor.log_performance_alert(self.response_time_threshold)
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}", exc_info=True)
            
            logfire.error(
                "Alert checking error",
                error=str(e),
                component="monitoring_dashboard"
            )


# Global dashboard instance
_monitoring_dashboard: Optional[HTTPMonitoringDashboard] = None


def get_monitoring_dashboard() -> Optional[HTTPMonitoringDashboard]:
    """Get the global monitoring dashboard instance."""
    return _monitoring_dashboard


def initialize_monitoring_dashboard(
    http_monitor: Optional[HTTPMonitor] = None,
    connection_manager: Optional[HTTPConnectionManager] = None,
    config: Optional[HTTPTransportConfig] = None
) -> HTTPMonitoringDashboard:
    """
    Initialize the global monitoring dashboard.
    
    Args:
        http_monitor: HTTP monitor instance
        connection_manager: HTTP connection manager instance
        config: HTTP transport configuration
        
    Returns:
        HTTPMonitoringDashboard instance
    """
    global _monitoring_dashboard
    if _monitoring_dashboard is None:
        _monitoring_dashboard = HTTPMonitoringDashboard(
            http_monitor=http_monitor,
            connection_manager=connection_manager,
            config=config
        )
        logger.info("Global monitoring dashboard initialized")
    return _monitoring_dashboard


def shutdown_monitoring_dashboard() -> None:
    """Shutdown the global monitoring dashboard."""
    global _monitoring_dashboard
    if _monitoring_dashboard is not None:
        logger.info("Shutting down monitoring dashboard")
        _monitoring_dashboard = None


# Utility functions for monitoring integration

async def create_monitoring_report() -> Dict[str, Any]:
    """
    Create comprehensive monitoring report.
    
    Returns:
        Dictionary with monitoring report data
    """
    dashboard = get_monitoring_dashboard()
    if not dashboard:
        return {"error": "Monitoring dashboard not available"}
    
    try:
        dashboard_data = await dashboard.get_dashboard_data()
        
        return {
            "timestamp": dashboard_data.timestamp.isoformat(),
            "health_status": dashboard_data.health_status,
            "summary": dashboard_data.overview,
            "performance": dashboard_data.performance,
            "alerts": dashboard_data.alerts,
            "recommendations": dashboard_data.recommendations
        }
        
    except Exception as e:
        logger.error(f"Error creating monitoring report: {e}", exc_info=True)
        return {"error": f"Failed to create monitoring report: {str(e)}"}


async def get_health_summary() -> Dict[str, Any]:
    """
    Get simplified health summary for quick status checks.
    
    Returns:
        Dictionary with health summary
    """
    dashboard = get_monitoring_dashboard()
    if not dashboard:
        return {
            "status": "unknown",
            "message": "Monitoring not available"
        }
    
    try:
        dashboard_data = await dashboard.get_dashboard_data()
        
        return {
            "status": dashboard_data.health_status,
            "uptime_seconds": dashboard_data.overview["uptime_seconds"],
            "requests_per_second": dashboard_data.overview["requests_per_second"],
            "success_rate": dashboard_data.overview["success_rate"],
            "active_connections": dashboard_data.overview["active_connections"],
            "alert_count": len(dashboard_data.alerts),
            "timestamp": dashboard_data.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}"
        }