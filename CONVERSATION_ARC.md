# Conversation Arc & MCP Capabilities

This document provides a visual ASCII sequence diagram of the data lifecycle (Conversation Arc) and lists the tools, services, and security rules available inside the Database MCP server.

---

## 1. The Conversation Arc (Data Lifecycle & Flow)

```
+------------------+     +--------------------+     +-------------------+     +----------------+
|   User Browser   |     |   Django Backend   |     |   Anthropic API   |     |  Database MCP  |
|   (React UI)     |     |  (Privacy Engine)  |     |   (Claude LLM)    |     |  (MySQL Pool)  |
+------------------+     +--------------------+     +-------------------+     +----------------+
         |                          |                         |                        |
         |  1. Send user prompt     |                         |                        |
         |------------------------->|                         |                        |
         |  (e.g., "Account 59001") |  2. Mask PII to tokens  |                        |
         |                          |     (e.g., <//UID-xx//>)|                        |
         |                          |                         |                        |
         |                          |  3. Send masked prompt  |                        |
         |                          |------------------------>|                        |
         |                          |                         |                        |
         |                          |  4. Request SQL tool    |                        |
         |                          |<------------------------|                        |
         |                          |     (e.g., execute_sql) |                        |
         |                          |                         |                        |
         |                          |  5. Detokenize query    |                        |
         |                          |  6. Call execute_sql    |                        |
         |                          |------------------------------------------------->|
         |                          |                         |                        |  7. Run query
         |                          |                         |                        |-----> [MySQL]
         |                          |                         |                        |       |
         |                          |                         |                        |       | Raw rows
         |                          |                         |                        |<------|
         |                          |                         |                        |
         |                          |                         |                        |  8. Encrypt PII
         |                          |                         |                        |     in results
         |                          |  9. Return tokenized    |                        |
         |                          |     JSON payload        |                        |
         |                          |<-------------------------------------------------|
         |                          |                         |                        |
         |                          |  10. Feed results       |                        |
         |                          |------------------------>|                        |
         |                          |                         |                        |
         |                          |  11. Final text response|                        |
         |                          |      (with tokens)      |                        |
         |                          |<------------------------|                        |
         |                          |                         |                        |
         |                          |  12. Detokenize response|                        |
         |                          |      to plain text      |                        |
         |                          |                         |                        |
         |  13. Stream raw reply    |                         |                        |
         |<-------------------------|                         |                        |
         |  (React UI renders D2,   |                         |                        |
         |   Vega-Lite & HTML/SVG)  |                         |                        |
         |                          |                         |                        |
```

---

## 2. Model Context Protocol (MCP) Capabilities

The Database MCP server (`database_mcp` app) exposes multiple tools and services to query the production database securely and efficiently.

### 🛠️ Core Database Tools
* **`execute_sql(sql, max_rows)`:** Automatically validates, optimizes, and executes read-only SQL queries. It automatically appends limits and intercepts metadata requests.
* **`validate_sql(sql)`:** Validates that a SQL statement is syntactically correct and contains only read-only `SELECT` commands.

### 📊 Metadata & Inspection Tools
* **`discover_database()`:** Discovers table counts, schema size, and overview of the database.
* **`list_tables()`:** Returns a list of all tables in the database.
* **`describe_table(table_name)`:** Retrieves fields, types, indexes, and constraints for a specific table.
* **`list_relationships()` / `relationship_graph()`:** Maps foreign key relations between tables to help the LLM construct correct `JOIN` queries.
* **`search_schema(keyword)`:** Performs a fuzzy metadata search for columns or tables matching a keyword.
* **`database_statistics()`:** Provides total database disk space, index length, and total row counts.

### 🩺 Utility & Management Tools
* **`health_check()`:** Pings the MySQL connection pool and checks the health of the in-memory metadata cache.
* **`refresh_metadata()`:** Force-updates the schema cache dynamically without restarting the subprocess server.

### 🚀 Optimization & Routing Services (Under the Hood)
1. **Strict Read-Only Enforcement:** Rejects any `INSERT`, `UPDATE`, `DELETE`, `DROP`, or `ALTER` actions instantly before passing them to the database.
2. **Intent Router ([router.py](file:///e:/BSS/nervenet/backend%20-%20nervenet/database_mcp/services/router.py)):** Intercepts general queries like `SHOW TABLES` or `DESCRIBE` and routes them to fast, cached Python tools rather than executing database commands.
3. **Query Optimization:** Enforces a maximum rows returned cap and checks the complexity of execution paths (such as checking unindexed joins) to keep database resource usage low.
4. **Connection Pooling:** Maintains persistent MySQL connections to avoid reconnection delays.

---

## 3. Frontend Visualization Capabilities

After the backend securely streams the text back to the browser (Step 13), the React UI intercepts specific syntax to render rich visual elements:

* **Vega & Vega-Lite:** Any ````vega` or ````vegalite` markdown block is natively rendered into an interactive chart (bar, pie, line, etc.) representing the SQL results.
* **D2 Diagrams:** Any ````d2` markdown block is compiled via WASM in the browser to draw responsive flowcharts, mindmaps, and relationship graphs (automatically supporting light/dark mode).
* **Sandboxed HTML/SVG:** Custom interactive dashboards or raw SVG files generated by the LLM are safely rendered within an isolated, responsive `BlobIframe` component.
