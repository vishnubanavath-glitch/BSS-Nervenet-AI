# Nervenet System Architecture & Design

This document describes the updated system design patterns, component relationships, data flow sequences, and database schemas of the integrated Nervenet platform.

---

## 1. Integrated System Architecture

The Nervenet application utilizes a decoupled, high-performance architecture supporting real-time streaming, homomorphic data tokenization (privacy), and Model Context Protocol (MCP) database security.

```mermaid
graph TD
    %% Styling
    classDef react fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef django fill:#0f5132,stroke:#198754,stroke-width:2px,color:#fff;
    classDef mcp fill:#3c2005,stroke:#b45309,stroke-width:1.5px,color:#fff;
    classDef external fill:#0f172a,stroke:#475569,stroke-width:1.5px,color:#d1d5db;

    %% React Client
    subgraph Frontend [React SPA Client]
        UI[React View components]:::react
        Zustand[Zustand Store: auth & chat]:::react
        Axios[Axios HTTP Client]:::react
        WS[WebSocket Client]:::react
    end

    %% Django Engine
    subgraph Backend [Django Core Engine]
        API[Django View Routers]:::django
        ASGI[ASGI / WS Handler]:::django
        Manager[ConversationManager]:::django
        Privacy[PrivacyEngine]:::django
        SQLite[(SQLite DB: History/State)]:::django
    end

    %% Database MCP Subprocess
    subgraph MCPLayer [Database MCP Subprocess]
        MCP[FastMCP Server]:::mcp
        Pool[MySQL Connection Pool]:::mcp
    end

    %% External Services
    LLM[Anthropic Claude API]:::external
    MySQL[(Production MySQL DB)]:::external

    %% Connections
    UI <--> Zustand
    Zustand --> Axios
    Zustand --> WS

    Axios <-->|HTTPS REST API| API
    WS <-->|WebSocket Stream| ASGI

    API <--> Manager
    ASGI <--> Manager
    Manager <--> SQLite
    Manager <--> Privacy

    Manager <-->|Anonymized Prompts| LLM
    Manager <-->|Stdio / JSON-RPC| MCP
    
    MCP <--> Pool
    Pool <-->|Secure SQL Queries| MySQL
```

1. **React SPA Client**: Employs Zustand stores for authentication and conversation state. Features dynamic Markdown rendering alongside an isolated sandboxed iframe for rendering dynamic visual HTML assets (like Chart.js configurations) and Mermaid diagrams on the fly.
2. **Django Core Engine (ASGI)**: Manages authentication, SQLite message logs, token tracking, user wallets, and privacy mappings. Utilizes `daphne`/ASGI Channels to support concurrent WebSockets.
3. **Database MCP Subprocess**: Secure Model Context Protocol database interface running as an isolated subprocess (`stdin`/`stdout`). It connects to the MySQL production database, validating that all SQL calls are strictly read-only SELECT queries.

---

## 2. Privacy Anonymization & Tool Calling sequence

All user queries containing sensitive customer data (mobile numbers, UIDs, etc.) are homomorphically tokenized using the backend `PrivacyEngine` before prompt delivery to Claude.

```mermaid
sequenceDiagram
    autonumber
    actor User as User Chat Client
    participant React as React (Zustand & WebSocket)
    participant Django as Django ASGI Engine
    participant Privacy as Privacy Engine
    participant Claude as Claude LLM API
    participant MCP as Database MCP Server (Subprocess)
    participant MySQL as MySQL Database

    User->>React: Sends: "Show energy history for consumer 5912345"
    React->>Django: Sends WS Frame: { action: 'message', prompt: '...' }
    
    activate Django
    Note over Django: Load Session Memory & _privacy_state
    Django->>Privacy: Mask raw prompt: "5912345"
    Privacy-->>Django: Returns anonymized: "Show energy history for <//UID-abc123xyz456//>"
    
    Django->>Claude: Invoke LLM (with anonymized history & prompt)
    activate Claude
    
    Claude-->>Django: Suggests Tool: execute_sql(sql="SELECT * FROM billing_transactions WHERE consumer_no = '<//UID-abc123xyz456//>'")
    Note over Django: Intercept Tool Call Parameters
    
    Django->>Privacy: Detokenize parameters: "<//UID-abc123xyz456//>"
    Privacy-->>Django: Returns raw value: "5912345"
    
    Django->>MCP: Call execute_sql(sql="SELECT * FROM ... WHERE consumer_no = '5912345'") over stdin/stdout
    activate MCP
    Note over MCP: Validate read-only SQL
    MCP->>MySQL: Run Query
    activate MySQL
    MySQL-->>MCP: Returns raw JSON rows: [{"consumer_no": "5912345", "billing_amt": 150.0}]
    deactivate MySQL
    
    MCP->>Privacy: Encrypt result row fields
    Privacy-->>MCP: Returns: [{"consumer_no": "<//UID-abc123xyz456//>", "billing_amt": 150.0}]
    MCP-->>Django: Return encrypted JSON string over stdout
    deactivate MCP

    Django->>Claude: Feed anonymized tool results back to LLM context
    
    Claude-->>Django: Returns Response: "Consumer <//UID-abc123xyz456//> has a billing amount of $150.0"
    deactivate Claude
    
    Django->>Django: Write anonymized history to SQLite Database
    Django->>Privacy: Detokenize final text
    Privacy-->>Django: Returns: "Consumer 5912345 has a billing amount of $150.0"
    
    Django-->>React: Stream text token-by-token (Done event has telemetry metadata)
    deactivate Django
    
    React->>User: Displays text & renders telemetry token usage + pricing costs
```

---

## 3. Database Schema Mappings

The MCP server connects to the `analytics_demo` MySQL database containing 7 tables:

1. **`consumer_master`**: Base customer registration (PII: `consumer_name`, `consumer_no`, `mobile_no`, `address`).
2. **`billing_transactions`**: Historical energy charge invoices and arrear statuses.
3. **`meter_readings`**: Monthly consumption records (PII: `latitude`, `longitude`, `gps_captured`). Contains reader logs.
4. **`feeder_master`**: Electricity feeder networks.
5. **`dtr_master`**: Distribution Transformer Stations.
6. **`meter_reader_master`**: Meter readers (PII: `meter_reader_name`, `mobile_no`).
7. **`hierarchy`**: Circles, divisions, subdivisions, and sections defining company organizational hierarchy.
