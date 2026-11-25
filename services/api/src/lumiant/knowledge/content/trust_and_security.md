# How Lumiant answers and keeps data safe

## Where the numbers come from
Every figure comes from a validated query against the customer's data through Lumiant's query engine. The AI assistant chooses analyses and writes the sentence around the results, but it never writes SQL and never calculates figures itself. Every number in an answer is checked against the query results before it is shown; an answer that contains a number not found in the results is withheld.

## Provenance
Every result carries its source: the dataset, the fields, the filters, the time of the data and the rule version used. Open the Source slip on any figure to see it.

## Access scope
Users only see the warehouses their role allows, and roles without cost access never see values or prices. The scope is applied by the server on every query, including the assistant's; the assistant cannot widen it.

## Read-only connection
Lumiant reads the customer's data warehouse with a read-only connection. It never posts transactions, changes master data or writes back to the ERP.

## Synthetic data
Demo tenants use synthetic data generated for demonstration. They are labelled SYNTHETIC on every screen and are never presented as customer data.

## External AI
An external AI provider is only used when the deployment configures it and the organisation has approved it. Without approval the assistant uses built-in question matching. Only the question and a capped summary of the tool results are sent to the provider, never credentials, SQL or physical table names.

## Audit trail
Every query, every assistant tool call and every disclosure to an external AI provider is recorded in the audit log with the user, the time and the outcome.
