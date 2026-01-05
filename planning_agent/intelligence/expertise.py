"""Oracle EPM Cloud Planning Module Expertise."""

MODULE_EXPERTISE = """
### Financials (OFS_Financials)
- **Cube**: OEP_FS (Financials) or custom BSO/ASO.
- **Key Features**: Revenue Planning, Expense Planning, Balance Sheet, Cash Flow, Income Statement.
- **Typical Dimensions**: Account, Period, Years, Scenario, Version, Entity, Plan Element (OEP_PlanElement).
- **Key Members**: 
    - OFS_Revenue Planning, OFS_Expense Planning.
    - OFS_Net Income, OFS_Gross Profit.
    - OFS_Total Assets, OFS_Total Liabilities.

### Workforce (OEP_WFP)
- **Cube**: OEP_WFP (Workforce) or custom BSO/ASO.
- **Key Features**: Compensation Planning, Headcount Analysis, Demographics, Strategic Workforce Planning.
- **Typical Dimensions**: Employee, Job, Property, Union Code, Gender, Highest Education Degree.
- **Key Members**:
    - OWP_Total Compensation, OWP_Basic Salary, OWP_Benefits, OWP_Taxes.
    - OWP_Total Headcount, OWP_FTE.
    - OWP_New Hires, OWP_Departures.

### Projects (OEP_PFP)
- **Cube**: OEP_PFP (Projects) or custom BSO/ASO.
- **Key Features**: Project Financial Planning, Contract Projects, Capital Projects, Indirect Projects.
- **Typical Dimensions**: Project, Resource Class, Vendor, Stage, Program.
- **Key Members**:
    - OPF_Total Project Revenue, OPF_Total Project Expense.
    - OPF_ROI, OPF_NPV, OPF_Payback Period.
    - OPF_Labor, OPF_Material, OPF_Equipment.

### Capital / Assets (OEP_CPX)
- **Cube**: OEP_CPX (Capital) or custom BSO/ASO.
- **Key Features**: New Asset Planning, Existing Asset management, Intangibles, Lease Assets (IFRS16/ASC842).
- **Typical Dimensions**: Asset Class, Asset Detail, Vendor.
- **Key Members**:
    - OCX_Total Capital Expenditure.
    - OCX_Depreciation, OCX_Amortization.
    - OCX_NBV (Net Book Value), OCX_Accumulated Depreciation.
"""

SYSTEM_PROMPT_ADDITION = """
You have deep expertise in the following Oracle EPM Cloud Planning modules:
1. **Financials**: Budgeting and forecasting for income statement, balance sheet, and cash flow.
2. **Workforce**: Planning for headcount, compensation, and non-compensation expenses.
3. **Projects**: Managing financial plans for contract, capital, and internal projects.
4. **Capital (Assets)**: Planning for new and existing assets, including depreciation and leases.

When a user asks about these topics, use the specific terminology, dimensions, and cube references associated with them.
For example, if asked about "Salary", refer to Workforce module and OWP_Basic Salary.
If asked about "Depreciation", refer to Capital module and OCX_Depreciation.
"""
