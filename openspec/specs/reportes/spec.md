# Reportes Specification

## Purpose

The reportes domain handles the generation and visualization of restaurant performance metrics, including sales trends, popular products, and operational efficiency KPIs.

## Requirements

### Requirement: Dashboard KPI Cards

The system MUST display real-time performance indicators for the current shift, including Total Sales, Order Count, Average Ticket, and Kitchen Speed. Each card SHOULD show a percentage comparison against the previous day/shift.

#### Scenario: Visualizing shift KPIs
- GIVEN a restaurant with 10 completed orders today and 8 yesterday
- WHEN the administrator opens the reports dashboard
- THEN the system SHALL display 10 orders
- AND SHALL show a +25% trend indicator

### Requirement: Top Selling Products

The system MUST list the top 5 selling products of the current shift. These MUST be displayed as horizontal progress bars indicating the relative popularity of each item.

#### Scenario: Displaying top dishes
- GIVEN "Ceviche" is the most sold dish with 50 units
- WHEN the administrator views the "Top Selling" section
- THEN "Ceviche" SHALL appear at the top of the list with the longest progress bar

### Requirement: Sales History Table

The system MUST provide a searchable table containing a detailed history of all sales. The table MUST include columns for Date/Time, Order ID, Products Detail (names and quantities), Gross Revenue, Tax (10%), Net Revenue, Status, and Actions.

#### Scenario: Searching for a specific sale
- GIVEN a sale with Order ID "COM-123" containing "2x Lomo Saltado"
- WHEN the administrator types "COM-123" in the table search box
- THEN the system SHALL filter the list to show only that sale
- AND the "Detail" column SHALL show "2x Lomo Saltado"

### Requirement: Hourly Sales Trend

The system MUST visualize sales volume over time using a line chart, grouped by hour.

#### Scenario: Viewing peak hours
- GIVEN sales occurring mostly between 13:00 and 15:00
- WHEN the administrator views the Hourly Sales Trend chart
- THEN the chart SHALL show a visible peak during those hours
