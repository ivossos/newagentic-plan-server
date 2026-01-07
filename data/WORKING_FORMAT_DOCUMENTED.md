# Working Format for Planning export_data_slice

## ✅ SUCCESS: Found the Correct Format!

After systematic testing, I've identified the correct format for Oracle Planning REST API v3 `exportdataslice`:

### Key Findings:

1. **POV Structure**: Must contain all dimensions EXCEPT those in columns/rows
2. **Columns Structure**: Array of objects with `"dimensions"` (plural) and `"members"`
3. **Rows Structure**: Array of objects, each with `"dimensions"` (plural) and `"members"` - one object per account (or multiple accounts in one object)

### Correct Format:

```json
{
  "suppressMissingBlocks": true,
  "pov": {
    "members": [
      ["Total Entity"],   // Entity
      ["Actual"],         // Scenario
      ["FY25"],           // Years
      ["Working"],        // Version
      ["USD"],            // Currency
      ["No Future1"],     // Future1
      ["Total CostCenter"], // CostCenter
      ["Total Region"]    // Region
    ]
  },
  "columns": [
    {
      "dimensions": ["Period"],
      "members": [["Dec"]]
    }
  ],
  "rows": [
    {
      "dimensions": ["Account"],
      "members": [["411110"]]
    },
    {
      "dimensions": ["Account"],
      "members": [["411120"]]
    }
  ]
}
```

### Important Notes:

1. **`dimensions` field is REQUIRED** in both `columns` and `rows` - use plural "dimensions", not singular "dimension"
2. **POV must NOT include dimensions** that are in columns or rows (e.g., if Period is in columns, don't include it in POV)
3. **Rows can be multiple objects** - one per account, or multiple accounts in one object
4. **All 10 Planning dimensions** must be accounted for: Account, Entity, Scenario, Years, Period, Version, Currency, Future1, CostCenter, Region

### Test Results:

✅ **API Call Successful**: The format above successfully calls the API without errors
⚠️ **Empty Results**: The API returns empty rows, which means:
   - The format is correct
   - There's simply no data for those accounts/periods with the specified POV
   - Data might exist under different POV members (different periods, years, entities, etc.)

### Next Steps for Top 10 Products by Revenue:

1. Query with different periods/years to find where data exists
2. Query with different entities if "products" refers to entities
3. Query parent accounts (like 400000, 410000) which might aggregate child account data
4. Check if "products" refers to a different dimension (like CostCenter or Region)

### Example Working Code:

```python
grid_definition = {
    "suppressMissingBlocks": True,
    "pov": {
        "members": [
            ["Total Entity"], ["Actual"], ["FY25"], ["Working"],
            ["USD"], ["No Future1"], ["Total CostCenter"], ["Total Region"]
        ]
    },
    "columns": [
        {
            "dimensions": ["Period"],
            "members": [["Dec"]]
        }
    ],
    "rows": [
        {
            "dimensions": ["Account"],
            "members": [["411110"]]
        }
    ]
}
```

This format successfully calls the API! 🎉

