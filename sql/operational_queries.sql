-- Week 4 Banking Database
-- SQL Analysis Queries
--
-- Purpose:
-- Analyze validated banking transactions using the
-- relational database model.
--
-- Required concepts:
-- JOIN
-- GROUP BY / aggregation
-- CASE
-- CTE
-- Window functions
-- Original banking business question


-- ============================================================
-- QUERY 01: Transaction details with customer information
-- ============================================================

SELECT
    t.transaction_id,
    t.transaction_date,
    t.transaction_type,
    t.amount,
    t.currency,
    a.account_id,
    c.customer_id,
    c.customer_name
FROM bank_transaction AS t
JOIN account AS a
    ON t.account_id = a.account_id
JOIN customer AS c
    ON a.customer_id = c.customer_id
ORDER BY
    t.transaction_date,
    t.transaction_id;

-- ============================================================
-- QUERY 02: Transaction details with branch information
-- ============================================================

SELECT
    t.transaction_id,
    t.transaction_date,
    t.transaction_type,
    t.amount,
    a.account_id,
    b.branch_id,
    b.branch_name,
    b.city,
    b.state
FROM bank_transaction AS t
JOIN account AS a
    ON t.account_id = a.account_id
JOIN branch AS b
    ON a.branch_id = b.branch_id
ORDER BY
    b.branch_id,
    t.transaction_id;

-- ============================================================
-- QUERY 03: Total transaction amount
-- ============================================================

SELECT
    ROUND(SUM(amount), 2) AS total_transaction_amount
FROM bank_transaction;         

-- ============================================================
-- QUERY 04: CREDIT vs DEBIT transaction summary
-- ============================================================

SELECT
    transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS average_amount
FROM bank_transaction
GROUP BY transaction_type
ORDER BY transaction_type;

-- ============================================================
-- QUERY 05: Customer-level transaction summary
-- ============================================================

SELECT
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_transaction_amount,
    ROUND(AVG(t.amount), 2) AS average_transaction_amount
FROM customer AS c
JOIN account AS a
    ON c.customer_id = a.customer_id
JOIN bank_transaction AS t
    ON a.account_id = t.account_id
GROUP BY
    c.customer_id,
    c.customer_name,
    c.customer_segment
ORDER BY
    total_transaction_amount DESC;

-- ============================================================
-- QUERY 06: Branch-level transaction summary
-- ============================================================

SELECT
    b.branch_id,
    b.branch_name,
    b.city,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_transaction_amount,
    ROUND(AVG(t.amount), 2) AS average_transaction_amount
FROM branch AS b
JOIN account AS a
    ON b.branch_id = a.branch_id
JOIN bank_transaction AS t
    ON a.account_id = t.account_id
GROUP BY
    b.branch_id,
    b.branch_name,
    b.city
ORDER BY
    total_transaction_amount DESC;

-- ============================================================
-- QUERY 07: Transaction classification using CASE
-- ============================================================

SELECT
    transaction_id,
    account_id,
    transaction_type,
    amount,
    CASE
        WHEN amount < 100 THEN 'Small'
        WHEN amount BETWEEN 100 AND 499.99 THEN 'Medium'
        ELSE 'Large'
    END AS amount_band
FROM bank_transaction
ORDER BY amount DESC;

-- ============================================================
-- QUERY 08: Credit and debit transaction summary
-- ============================================================

SELECT
    transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS average_amount,
    ROUND(MIN(amount), 2) AS minimum_amount,
    ROUND(MAX(amount), 2) AS maximum_amount
FROM bank_transaction
GROUP BY transaction_type
ORDER BY total_amount DESC;

-- ============================================================
-- QUERY 09: Rank customers by total transaction amount
-- ============================================================

WITH customer_totals AS (
    SELECT
        c.customer_id,
        c.customer_name,
        ROUND(SUM(t.amount), 2) AS total_amount
    FROM customer AS c
    JOIN account AS a
        ON c.customer_id = a.customer_id
    JOIN bank_transaction AS t
        ON a.account_id = t.account_id
    GROUP BY
        c.customer_id,
        c.customer_name
)

SELECT
    customer_id,
    customer_name,
    total_amount,
    RANK() OVER (
        ORDER BY total_amount DESC
    ) AS customer_rank
FROM customer_totals
ORDER BY customer_rank;

-- ============================================================
-- QUERY 10: Running total of transactions by date
-- ============================================================

SELECT
    transaction_id,
    transaction_date,
    transaction_type,
    amount,
    SUM(amount) OVER (
        ORDER BY transaction_date, transaction_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM bank_transaction
ORDER BY
    transaction_date,
    transaction_id;

-- ============================================================
-- QUERY 11: Transaction activity by account
-- ============================================================

SELECT
    a.account_id,
    a.account_type,
    a.account_status,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_amount,
    ROUND(AVG(t.amount), 2) AS average_amount
FROM account AS a
LEFT JOIN bank_transaction AS t
    ON a.account_id = t.account_id
GROUP BY
    a.account_id,
    a.account_type,
    a.account_status
ORDER BY
    total_amount DESC;

-- ============================================================
-- QUERY 12: Customers and their branch accounts
-- ============================================================

SELECT
    c.customer_id,
    c.customer_name,
    a.account_id,
    a.account_type,
    b.branch_name,
    b.city
FROM customer AS c
JOIN account AS a
    ON c.customer_id = a.customer_id
JOIN branch AS b
    ON a.branch_id = b.branch_id
ORDER BY
    c.customer_id,
    a.account_id;        

-- ============================================================
-- QUERY 13: Credit and debit activity by branch
-- ============================================================

SELECT
    b.branch_id,
    b.branch_name,
    t.transaction_type,
    COUNT(t.transaction_id) AS transaction_count,
    ROUND(SUM(t.amount), 2) AS total_amount
FROM branch AS b
JOIN account AS a
    ON b.branch_id = a.branch_id
JOIN bank_transaction AS t
    ON a.account_id = t.account_id
GROUP BY
    b.branch_id,
    b.branch_name,
    t.transaction_type
ORDER BY
    b.branch_id,
    t.transaction_type;

-- ============================================================
-- QUERY 14: Customers above the average customer total
-- Original business question:
-- Which customers have transaction totals above the
-- average customer transaction total?
-- ============================================================

WITH customer_totals AS (
    SELECT
        c.customer_id,
        c.customer_name,
        ROUND(SUM(t.amount), 2) AS total_amount
    FROM customer AS c
    JOIN account AS a
        ON c.customer_id = a.customer_id
    JOIN bank_transaction AS t
        ON a.account_id = t.account_id
    GROUP BY
        c.customer_id,
        c.customer_name
),

average_customer_total AS (
    SELECT
        AVG(total_amount) AS average_total
    FROM customer_totals
)

SELECT
    ct.customer_id,
    ct.customer_name,
    ct.total_amount,
    ROUND(act.average_total, 2) AS average_customer_total
FROM customer_totals AS ct
CROSS JOIN average_customer_total AS act
WHERE ct.total_amount > act.average_total
ORDER BY ct.total_amount DESC;

-- ============================================================
-- QUERY 15: Each customer's percentage of total transaction amount
-- ============================================================

WITH customer_totals AS (
    SELECT
        c.customer_id,
        c.customer_name,
        SUM(t.amount) AS total_amount
    FROM customer AS c
    JOIN account AS a
        ON c.customer_id = a.customer_id
    JOIN bank_transaction AS t
        ON a.account_id = t.account_id
    GROUP BY
        c.customer_id,
        c.customer_name
)

SELECT
    customer_id,
    customer_name,
    ROUND(total_amount, 2) AS total_amount,
    ROUND(
        total_amount * 100.0 /
        SUM(total_amount) OVER (),
        2
    ) AS percentage_of_total
FROM customer_totals
ORDER BY
    percentage_of_total DESC;