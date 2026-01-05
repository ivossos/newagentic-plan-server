"""Data tools - export_data_slice, smart_retrieve, copy_data, clear_data."""

from typing import Any, Optional, List

from planning_agent.client.planning_client import PlanningClient

_client: PlanningClient = None
_app_name: str = None


def set_client(client: PlanningClient):
    global _client
    _client = client


def set_app_name(app_name: str):
    global _app_name
    _app_name = app_name


def _build_grid_definition(
    account: str,
    entity: str,
    period: str,
    years: str,
    scenario: str,
    version: str,
    currency: str,
    cost_center: str,
    future1: str,
    region: str
) -> dict[str, Any]:
    """Build the correct grid definition for PlanApp's 10 dimensions.
    
    Based on WORKING_FORMAT_DOCUMENTED.md:
    - POV: 8 dimensions (Entity, Scenario, Years, Version, Currency, Future1, CostCenter, Region)
    - Columns: Period with "dimensions" key (plural)
    - Rows: Account with "dimensions" key (plural)
    
    The key insight is that rows and columns MUST have "dimensions" (plural) field.
    """
    return {
        "suppressMissingBlocks": True,
        "pov": {
            "members": [
                [entity],        # Entity
                [scenario],      # Scenario
                [years],         # Years
                [version],       # Version
                [currency],      # Currency
                [future1],       # Future1
                [cost_center],   # CostCenter
                [region]         # Region
            ]
        },
        "columns": [
            {
                "dimensions": ["Period"],
                "members": [[period]]
            }
        ],
        "rows": [
            {
                "dimensions": ["Account"],
                "members": [[account]]
            }
        ]
    }


async def export_data_slice(
    plan_type: str,
    grid_definition: dict[str, Any]
) -> dict[str, Any]:
    """Export a specific data slice (grid) from the application / Exportar um slice de dados.

    Args:
        plan_type: The name of the plan type (e.g., 'FinPlan', 'FinRPT').
        grid_definition: The data grid definition with pov, columns, and rows.

    Returns:
        dict: The exported data slice with rows and column values.
    """
    result = await _client.export_data_slice(_app_name, plan_type, grid_definition)
    return {"status": "success", "data": result}


async def smart_retrieve(
    account: str,
    entity: str = "E501",
    period: str = "YearTotal",
    years: str = "FY25",
    scenario: str = "Actual",
    version: str = "Final",
    currency: str = "USD",
    cost_center: str = "CC9999",
    future1: str = "Total Plan",
    region: str = "R131",
    plan_type: str = "FinPlan"
) -> dict[str, Any]:
    """Smart data retrieval with automatic 10-dimension handling for PlanApp / Recuperacao inteligente de dados.

    PlanApp has 10 dimensions: Years, Period, Scenario, Version, Currency, Entity, CostCenter, Future1, Region, Account.
    POV: Entity, Scenario, Years, Version, Currency, Future1, CostCenter, Region (8 dims)
    Columns: Period
    Rows: Account

    Args:
        account: The Account member (e.g., '400000', '410000').
        entity: The Entity member (default: 'E501' - L7 Chicago). Use 'All Entity' for rollup.
        period: The Period member (default: 'YearTotal'). Options: Jan-Dec, Q1-Q4, YearTotal.
        years: The Years member (default: 'FY25'). Options: FY23, FY24, FY25.
        scenario: The Scenario member (default: 'Actual'). Options: Actual, Forecast.
        version: The Version member (default: 'Final').
        currency: The Currency member (default: 'USD').
        cost_center: The CostCenter member (default: 'CC9999' for rollup). 
            Options: CC1000 (Rooms), CC2000 (F&B), CC3000 (Other), CC4000 (Misc).
        future1: The Future1 member (default: 'Total Plan' - Dynamic Calc total).
        region: The Region member (default: 'R131' - Illinois where E501 has data).
        plan_type: The plan type (default: 'FinPlan'). Options: FinPlan, FinRPT.

    Returns:
        dict: The retrieved data for the specified dimensions.
    """
    grid_definition = _build_grid_definition(
        account=account,
        entity=entity,
        period=period,
        years=years,
        scenario=scenario,
        version=version,
        currency=currency,
        cost_center=cost_center,
        future1=future1,
        region=region
    )
    
    try:
        result = await _client.export_data_slice(_app_name, plan_type, grid_definition)
        
        # Extract value from result
        value = None
        if result and "rows" in result and len(result["rows"]) > 0:
            row = result["rows"][0]
            if "data" in row and len(row["data"]) > 0:
                try:
                    value = float(row["data"][0])
                except (ValueError, TypeError):
                    value = row["data"][0]
        
        return {
            "status": "success", 
            "data": result,
            "value": value,
            "pov": {
                "years": years,
                "period": period,
                "scenario": scenario,
                "version": version,
                "currency": currency,
                "entity": entity,
                "cost_center": cost_center,
                "future1": future1,
                "region": region,
                "account": account
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def smart_retrieve_revenue(
    entity: str = "E501",
    period: str = "YearTotal",
    years: str = "FY25",
    scenario: str = "Actual",
    cost_center: str = "CC9999",
    plan_type: str = "FinPlan"
) -> dict[str, Any]:
    """Retrieve revenue accounts (400000, 410000, 420000) for an entity / Recuperar contas de receita.

    Args:
        entity: The Entity member (default: 'E501').
        period: The Period member (default: 'YearTotal').
        years: The Years member (default: 'FY25').
        scenario: The Scenario member (default: 'Actual').
        cost_center: The CostCenter member (default: 'CC9999').
        plan_type: The plan type (default: 'FinPlan').

    Returns:
        dict: Revenue breakdown by account.
    """
    revenue_accounts = ["400000", "410000", "420000"]
    results = {}
    
    for account in revenue_accounts:
        try:
            grid_definition = _build_grid_definition(
                account=account,
                entity=entity,
                period=period,
                years=years,
                scenario=scenario,
                version="Final",
                currency="USD",
                cost_center=cost_center,
                future1="Total Plan",
                region="R131"
            )
            result = await _client.export_data_slice(_app_name, plan_type, grid_definition)

            # Extract value from result
            value = 0.0
            if result and "rows" in result and len(result["rows"]) > 0:
                row = result["rows"][0]
                if "data" in row and len(row["data"]) > 0:
                    try:
                        value = float(row["data"][0])
                    except (ValueError, TypeError):
                        value = 0.0

            results[account] = value
        except Exception as e:
            results[account] = {"error": str(e)}

    return {
        "status": "success",
        "data": {
            "entity": entity,
            "period": period,
            "years": years,
            "scenario": scenario,
            "cost_center": cost_center,
            "revenue_breakdown": results,
            "summary": {
                "total_revenue_400000": results.get("400000", 0.0),
                "rooms_revenue_410000": results.get("410000", 0.0),
                "fb_revenue_420000": results.get("420000", 0.0)
            }
        }
    }


async def smart_retrieve_monthly(
    account: str,
    entity: str = "E501",
    years: str = "FY25",
    scenario: str = "Actual",
    cost_center: str = "CC9999",
    plan_type: str = "FinPlan"
) -> dict[str, Any]:
    """Retrieve monthly data for an account / Recuperar dados mensais para uma conta.

    Args:
        account: The Account member (e.g., '400000', '410000').
        entity: The Entity member (default: 'E501').
        years: The Years member (default: 'FY25').
        scenario: The Scenario member (default: 'Actual').
        cost_center: The CostCenter member (default: 'CC9999').
        plan_type: The plan type (default: 'FinPlan').

    Returns:
        dict: Monthly breakdown for the account.
    """
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    results = {}
    
    for month in months:
        try:
            grid_definition = _build_grid_definition(
                account=account,
                entity=entity,
                period=month,
                years=years,
                scenario=scenario,
                version="Final",
                currency="USD",
                cost_center=cost_center,
                future1="Total Plan",
                region="R131"
            )
            result = await _client.export_data_slice(_app_name, plan_type, grid_definition)
            
            # Extract value from result
            value = 0.0
            if result and "rows" in result and len(result["rows"]) > 0:
                row = result["rows"][0]
                if "data" in row and len(row["data"]) > 0:
                    try:
                        value = float(row["data"][0])
                    except (ValueError, TypeError):
                        value = 0.0
            
            results[month] = value
        except Exception as e:
            results[month] = 0.0
    
    # Calculate YTD and full year
    ytd_months = ["Jan", "Feb", "Mar", "Apr", "May"]  # CurrMonth = May
    ytd_total = sum(results.get(m, 0.0) for m in ytd_months if isinstance(results.get(m), (int, float)))
    full_year = sum(v for v in results.values() if isinstance(v, (int, float)))
    
    return {
        "status": "success",
        "data": {
            "entity": entity,
            "account": account,
            "years": years,
            "scenario": scenario,
            "cost_center": cost_center,
            "monthly_data": results,
            "summary": {
                "ytd_jan_may": ytd_total,
                "full_year": full_year
            }
        }
    }


async def smart_retrieve_variance(
    account: str,
    entity: str = "E501",
    period: str = "YearTotal",
    years: str = "FY25",
    prior_year: str = "FY24",
    cost_center: str = "CC9999",
    plan_type: str = "FinPlan"
) -> dict[str, Any]:
    """Retrieve variance analysis (Actual vs Forecast, Current vs Prior Year) / Analise de variancia.

    Args:
        account: The Account member (e.g., '400000', '410000').
        entity: The Entity member (default: 'E501').
        period: The Period member (default: 'YearTotal').
        years: The Years member (default: 'FY25').
        prior_year: The prior year for comparison (default: 'FY24').
        cost_center: The CostCenter member (default: 'CC9999').
        plan_type: The plan type (default: 'FinPlan').

    Returns:
        dict: Variance analysis with Actual, Forecast, Prior Year.
    """
    scenarios = {
        "current_actual": {"scenario": "Actual", "years": years},
        "current_forecast": {"scenario": "Forecast", "years": years},
        "prior_actual": {"scenario": "Actual", "years": prior_year}
    }
    
    results = {}
    
    for key, params in scenarios.items():
        try:
            grid_definition = _build_grid_definition(
                account=account,
                entity=entity,
                period=period,
                years=params["years"],
                scenario=params["scenario"],
                version="Final",
                currency="USD",
                cost_center=cost_center,
                future1="Total Plan",
                region="R131"
            )
            result = await _client.export_data_slice(_app_name, plan_type, grid_definition)
            
            # Extract value from result
            value = 0.0
            if result and "rows" in result and len(result["rows"]) > 0:
                row = result["rows"][0]
                if "data" in row and len(row["data"]) > 0:
                    try:
                        value = float(row["data"][0])
                    except (ValueError, TypeError):
                        value = 0.0
            
            results[key] = value
        except Exception as e:
            results[key] = 0.0
    
    # Calculate variances
    actual = results.get("current_actual", 0.0)
    forecast = results.get("current_forecast", 0.0)
    prior = results.get("prior_actual", 0.0)
    
    var_to_forecast = actual - forecast if forecast else 0.0
    var_to_prior = actual - prior if prior else 0.0
    var_pct_forecast = (var_to_forecast / forecast * 100) if forecast else 0.0
    var_pct_prior = (var_to_prior / prior * 100) if prior else 0.0
    
    return {
        "status": "success",
        "data": {
            "entity": entity,
            "account": account,
            "period": period,
            "years": years,
            "values": results,
            "variance": {
                "actual_vs_forecast": var_to_forecast,
                "actual_vs_forecast_pct": round(var_pct_forecast, 2),
                "actual_vs_prior_year": var_to_prior,
                "actual_vs_prior_year_pct": round(var_pct_prior, 2)
            }
        }
    }


async def copy_data(
    from_scenario: Optional[str] = None,
    to_scenario: Optional[str] = None,
    from_year: Optional[str] = None,
    to_year: Optional[str] = None,
    from_period: Optional[str] = None,
    to_period: Optional[str] = None
) -> dict[str, Any]:
    """Copy data between scenarios, years, or periods / Copiar dados entre cenarios.

    Args:
        from_scenario: Source scenario.
        to_scenario: Target scenario.
        from_year: Source year.
        to_year: Target year.
        from_period: Source period.
        to_period: Target period.

    Returns:
        dict: Job submission result.
    """
    parameters = {}
    if from_scenario:
        parameters["fromScenario"] = from_scenario
    if to_scenario:
        parameters["toScenario"] = to_scenario
    if from_year:
        parameters["fromYear"] = from_year
    if to_year:
        parameters["toYear"] = to_year
    if from_period:
        parameters["fromPeriod"] = from_period
    if to_period:
        parameters["toPeriod"] = to_period

    result = await _client.copy_data(_app_name, parameters)
    return {"status": "success", "data": result}


async def clear_data(
    scenario: Optional[str] = None,
    year: Optional[str] = None,
    period: Optional[str] = None
) -> dict[str, Any]:
    """Clear data for specified scenario, year, and period / Limpar dados.

    Args:
        scenario: Scenario to clear.
        year: Year to clear.
        period: Period to clear.

    Returns:
        dict: Job submission result.
    """
    parameters = {}
    if scenario:
        parameters["scenario"] = scenario
    if year:
        parameters["year"] = year
    if period:
        parameters["period"] = period

    result = await _client.clear_data(_app_name, parameters)
    return {"status": "success", "data": result}


TOOL_DEFINITIONS = [
    {
        "name": "export_data_slice",
        "description": "Export a specific data slice (grid) from the application / Exportar um slice de dados",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "description": "The name of the plan type (e.g., 'FinPlan', 'FinRPT')",
                },
                "grid_definition": {
                    "type": "object",
                    "description": "The data grid definition with pov, columns, and rows",
                },
            },
            "required": ["plan_type", "grid_definition"],
        },
    },
    {
        "name": "smart_retrieve",
        "description": "Smart data retrieval with automatic 10-dimension handling for PlanApp (EPBCS) / Recuperacao inteligente com tratamento automatico das 10 dimensoes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "The Account member (e.g., '400000' Total Revenue, '410000' Rooms, '420000' F&B)",
                },
                "entity": {
                    "type": "string",
                    "description": "The Entity member (default: 'E501' L7 Chicago). Use 'All Entity' for rollup.",
                },
                "period": {
                    "type": "string",
                    "description": "The Period member (default: 'YearTotal'). Options: Jan-Dec, Q1-Q4, YearTotal.",
                },
                "years": {
                    "type": "string",
                    "description": "The Years member (default: 'FY25'). Options: FY23, FY24, FY25.",
                },
                "scenario": {
                    "type": "string",
                    "description": "The Scenario member (default: 'Actual'). Options: Actual, Forecast.",
                },
                "version": {
                    "type": "string",
                    "description": "The Version member (default: 'Final').",
                },
                "currency": {
                    "type": "string",
                    "description": "The Currency member (default: 'USD').",
                },
                "cost_center": {
                    "type": "string",
                    "description": "The CostCenter member (default: 'CC9999'). CC1000=Rooms, CC2000=F&B, CC3000=Other, CC4000=Misc.",
                },
                "future1": {
                    "type": "string",
                    "description": "The Future1 member (default: 'Total Plan' - Dynamic Calc total).",
                },
                "region": {
                    "type": "string",
                    "description": "The Region member (default: 'R131' - Illinois where E501 has data). Use 'All Region' for rollup.",
                },
                "plan_type": {
                    "type": "string",
                    "description": "The plan type (default: 'FinPlan'). Options: FinPlan, FinRPT.",
                },
            },
            "required": ["account"],
        },
    },
    {
        "name": "smart_retrieve_revenue",
        "description": "Retrieve revenue accounts (400000 Total, 410000 Rooms, 420000 F&B) for an entity / Recuperar contas de receita",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "The Entity member (default: 'E501').",
                },
                "period": {
                    "type": "string",
                    "description": "The Period member (default: 'YearTotal').",
                },
                "years": {
                    "type": "string",
                    "description": "The Years member (default: 'FY25').",
                },
                "scenario": {
                    "type": "string",
                    "description": "The Scenario member (default: 'Actual').",
                },
                "cost_center": {
                    "type": "string",
                    "description": "The CostCenter member (default: 'CC9999').",
                },
                "plan_type": {
                    "type": "string",
                    "description": "The plan type (default: 'FinPlan').",
                },
            },
        },
    },
    {
        "name": "smart_retrieve_monthly",
        "description": "Retrieve monthly data (Jan-Dec) for an account / Recuperar dados mensais para uma conta",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "The Account member (e.g., '400000', '410000').",
                },
                "entity": {
                    "type": "string",
                    "description": "The Entity member (default: 'E501').",
                },
                "years": {
                    "type": "string",
                    "description": "The Years member (default: 'FY25').",
                },
                "scenario": {
                    "type": "string",
                    "description": "The Scenario member (default: 'Actual').",
                },
                "cost_center": {
                    "type": "string",
                    "description": "The CostCenter member (default: 'CC9999').",
                },
                "plan_type": {
                    "type": "string",
                    "description": "The plan type (default: 'FinPlan').",
                },
            },
            "required": ["account"],
        },
    },
    {
        "name": "smart_retrieve_variance",
        "description": "Retrieve variance analysis (Actual vs Forecast, Current vs Prior Year) / Analise de variancia",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "The Account member (e.g., '400000', '410000').",
                },
                "entity": {
                    "type": "string",
                    "description": "The Entity member (default: 'E501').",
                },
                "period": {
                    "type": "string",
                    "description": "The Period member (default: 'YearTotal').",
                },
                "years": {
                    "type": "string",
                    "description": "The Years member (default: 'FY25').",
                },
                "prior_year": {
                    "type": "string",
                    "description": "The prior year for comparison (default: 'FY24').",
                },
                "cost_center": {
                    "type": "string",
                    "description": "The CostCenter member (default: 'CC9999').",
                },
                "plan_type": {
                    "type": "string",
                    "description": "The plan type (default: 'FinPlan').",
                },
            },
            "required": ["account"],
        },
    },
    {
        "name": "copy_data",
        "description": "Copy data between scenarios, years, or periods / Copiar dados entre cenarios",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_scenario": {"type": "string", "description": "Source scenario"},
                "to_scenario": {"type": "string", "description": "Target scenario"},
                "from_year": {"type": "string", "description": "Source year"},
                "to_year": {"type": "string", "description": "Target year"},
                "from_period": {"type": "string", "description": "Source period"},
                "to_period": {"type": "string", "description": "Target period"},
            },
        },
    },
    {
        "name": "clear_data",
        "description": "Clear data for specified scenario, year, and period / Limpar dados",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "description": "Scenario to clear"},
                "year": {"type": "string", "description": "Year to clear"},
                "period": {"type": "string", "description": "Period to clear"},
            },
        },
    },
]
