"""Mock data for Planning operations - used when PLANNING_MOCK_MODE=true."""

from typing import Any

MOCK_APPLICATIONS: dict[str, Any] = {
    "items": [
        {
            "name": "PlanApp",
            "type": "Planning",
            "description": "Mock Planning Application for Testing"
        }
    ]
}

MOCK_JOBS: dict[str, Any] = {
    "items": [
        {
            "jobId": "101",
            "jobName": "Export Metadata",
            "jobType": "Export Metadata",
            "status": "Completed",
            "startTime": "2023-10-27T10:00:00Z",
            "endTime": "2023-10-27T10:05:00Z"
        },
        {
            "jobId": "102",
            "jobName": "Business Rule",
            "jobType": "Rules",
            "status": "Running",
            "startTime": "2023-10-27T11:00:00Z"
        }
    ]
}

MOCK_JOB_STATUS: dict[str, dict[str, Any]] = {
    "101": {
        "jobId": "101",
        "jobName": "Export Metadata",
        "status": "Success",
        "details": "Metadata exported successfully",
        "log": "Export completed in 2s."
    },
    "102": {
        "jobId": "102",
        "jobName": "Business Rule",
        "status": "Running",
        "details": "Executing rule..."
    }
}

MOCK_JOB_RESULT: dict[str, Any] = {
    "jobId": "103",
    "jobName": "Business Rule",
    "status": "Submitted",
    "details": "Job submitted for processing."
}

MOCK_DIMENSIONS: dict[str, Any] = {
    "items": [
        {"name": "Account", "type": "Account"},
        {"name": "Entity", "type": "Entity"},
        {"name": "Period", "type": "Time"},
        {"name": "Scenario", "type": "Scenario"},
        {"name": "Version", "type": "Version"},
        {"name": "Years", "type": "Time"},
        {"name": "CostCenter", "type": "CostCenter"},
        {"name": "Region", "type": "Region"}
    ]
}

MOCK_MEMBERS: dict[str, Any] = {
    "items": [
        {"name": "NetIncome", "description": "Net Income", "parent": "Root"},
        {"name": "Revenue", "description": "Total Revenue", "parent": "NetIncome"},
        {"name": "Expenses", "description": "Total Expenses", "parent": "NetIncome"}
    ]
}

MOCK_MEMBER: dict[str, Any] = {
    "name": "NetIncome",
    "description": "Net Income",
    "parent": "Root",
    "children": [
        {"name": "Revenue", "description": "Total Revenue"},
        {"name": "Expenses", "description": "Total Expenses"}
    ]
}

MOCK_DATA_SLICE: dict[str, Any] = {
    "pov": ["Year", "Scenario"],
    "columns": [{"2024": ["Jan"]}],
    "rows": [{"headers": ["Net Income"], "data": [1000]}]
}

MOCK_SUBSTITUTION_VARIABLES: dict[str, Any] = {
    "items": [
        {
            "name": "CurrYear",
            "value": "FY24",
            "planType": "FinPlan"
        },
        {
            "name": "CurrPeriod",
            "value": "Jan",
            "planType": "FinPlan"
        }
    ]
}

MOCK_DOCUMENTS: dict[str, Any] = {
    "items": [
        {
            "name": "Budget Guidelines",
            "type": "Document",
            "description": "Budget planning guidelines"
        }
    ]
}

MOCK_SNAPSHOTS: dict[str, Any] = {
    "items": [
        {
            "snapshotId": "1",
            "name": "Q1 Snapshot",
            "description": "Q1 2024 snapshot",
            "createdDate": "2024-03-31T00:00:00Z"
        }
    ]
}


