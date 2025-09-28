# ADR 0002: Unity Catalog Mapping for Data Products

## Status
Proposed

## Context
Unity Catalog provides centralized governance, access control, and lineage tracking across Databricks workspaces. Following ADR-001's medallion architecture inside data products guidelines, we need to establish how data products map to Unity Catalog's three-level hierarchy (catalog.schema.table) to ensure consistent governance and discoverability.

Data products represent autonomous software development lifecycle scopes in our decentralized data architecture, making them natural candidates for catalog-level isolation in Unity Catalog.

## Decision

### Unity Catalog Mapping Structure
- **Catalog**: `{environment}_{domain}_{product_name}_dp`
  - Examples: `dev_sales_orders_dp`, `prod_finance_revenue_dp`
- **Schemas**: `bronze`, `silver`, `gold` (aligned with medallion layers from ADR-001)
- **Tables**: `{source_or_entity}_{type}_tbl`
  - Examples: `orders_data_tbl`, `customer_metrics_tbl`

### Access Control Strategy
- **Bronze Schema**: Data engineers and ETL service accounts only
- **Silver Schema**: Data analysts and approved business users
- **Gold Schema**: Business stakeholders and BI tools
- **Cross-layer**: Row-level security and column masking applied as needed

### Governance Features
- **Lineage**: Automatic tracking across medallion layers within each data product
- **Data Classification**: Sensitive data tagged at column level
- **Audit Logging**: All access and modifications tracked per data product catalog

## Consequences

### Positive
- **Isolation**: Each data product has dedicated catalog ensuring clear boundaries
- **Governance**: Consistent access patterns aligned with medallion architecture
- **Discoverability**: Standardized naming enables automated discovery and cataloging
- **Compliance**: Centralized audit trails and data classification per data product

### Negative
- **Catalog Proliferation**: Each data product creates a separate catalog
- **Cross-Product Queries**: Joining data across products requires cross-catalog permissions
- **Management Overhead**: More catalogs to provision and maintain

### Risks & Mitigations
- **Risk**: Catalog sprawl becomes unmanageable
  - **Mitigation**: Implement automated catalog lifecycle management and naming conventions
- **Risk**: Complex cross-product access patterns
  - **Mitigation**: Define clear data sharing contracts through output ports (ADR-001)
- **Risk**: Inconsistent governance across catalogs
  - **Mitigation**: Standardized templates and automated policy enforcement

## References
- [Databricks Medallion Architecture Guide](https://docs.databricks.com/lakehouse/medallion.html)
- [Unity Catalog Best Practices](https://docs.databricks.com/data-governance/unity-catalog/best-practices.html)
- [Data Mesh Principles](https://martinfowler.com/articles/data-mesh-principles.html)

## Related ADRs
- ADR-001: Medallion Architecture Mapping to Data Product Internals