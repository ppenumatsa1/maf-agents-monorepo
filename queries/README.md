# Queries

Shared KQL queries for App Insights / Log Analytics.

## Environment

- Resource group: rg-maf-dev
- App Insights: mafs5ixpqx3hitri-appi
- Log Analytics workspace: mafs5ixpqx3hitri-law

## 1) End-to-end trace by correlation id

```
let correlationId = "<correlation_id>";
union isfuzzy=true requests, dependencies, traces, customMetrics
| where tostring(customDimensions["app.correlation_id"]) == correlationId
| project timestamp, itemType, name, operation_Id, duration, resultCode, success, customDimensions
| order by timestamp asc
```

## 2) Latest workflow spans (custom spans)

```
traces
| where message has "workflow." or name has "workflow."
| project timestamp, operation_Id, name, message, severityLevel, customDimensions
| order by timestamp desc
| take 200
```

## 2b) App-only custom spans (noise reduced)

```
dependencies
| where name startswith "app."
| project timestamp, operation_Id, name, duration, customDimensions
| order by timestamp desc
| take 200
```

## 3) Request + dependencies for a single operation

```
let op = "<operation_id>";
requests
| where operation_Id == op
| project timestamp, name, duration, resultCode, success, operation_Id
| union (dependencies | where operation_Id == op | project timestamp, name, duration, resultCode, success, operation_Id)
| order by timestamp asc
```

## 4) Azure AI Foundry call latency

```
dependencies
| where target has "services.ai.azure.com"
| project timestamp, name, target, duration, resultCode, success, operation_Id
| order by timestamp desc
| take 200
```
