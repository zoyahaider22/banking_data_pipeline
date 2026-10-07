-- Analytical queries against database/analytics.db
-- Grain of fact_transaction: one row = one banking transaction.
-- amount is always positive. total_amount is gross volume (money in + money out).
-- net_cash_flow = credits minus debits (CREDIT adds, DEBIT subtracts).

-- Q1. Transaction count and total amount by branch
SELECT
    b.branch_id,
    b.branch_name,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.amount), 2) AS total_amount,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE -f.amount END), 2) AS net_cash_flow
FROM fact_transaction AS f
JOIN dim_branch AS b ON b.branch_id = f.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY b.branch_id;

-- Q2. Transaction count and total amount by transaction type
SELECT
    f.transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.amount), 2) AS total_amount
FROM fact_transaction AS f
GROUP BY f.transaction_type
ORDER BY f.transaction_type;

-- Q3. Transaction activity by customer
SELECT
    c.customer_id,
    c.customer_name,
    c.customer_segment,
    COUNT(*) AS transaction_count,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE 0 END), 2) AS total_credits,
    ROUND(SUM(CASE WHEN f.transaction_type = 'DEBIT' THEN f.amount ELSE 0 END), 2) AS total_debits,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE -f.amount END), 2) AS net_cash_flow
FROM fact_transaction AS f
JOIN dim_customer AS c ON c.customer_id = f.customer_id
GROUP BY c.customer_id, c.customer_name, c.customer_segment
ORDER BY transaction_count DESC, c.customer_id;

-- Q4. Transaction activity by account
SELECT
    a.account_id,
    a.account_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.amount), 2) AS total_amount
FROM fact_transaction AS f
JOIN dim_account AS a ON a.account_id = f.account_id
GROUP BY a.account_id, a.account_type
ORDER BY total_amount DESC, a.account_id;

-- Q5. Transaction activity by date
SELECT
    d.full_date,
    d.day_name,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.amount), 2) AS total_amount,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE -f.amount END), 2) AS net_cash_flow
FROM fact_transaction AS f
JOIN dim_date AS d ON d.date_key = f.date_key
GROUP BY d.date_key, d.full_date, d.day_name
ORDER BY d.date_key;

-- Q6. Fact joined to two dimensions: activity by customer segment and branch
SELECT
    c.customer_segment,
    b.branch_name,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.amount), 2) AS total_amount
FROM fact_transaction AS f
JOIN dim_customer AS c ON c.customer_id = f.customer_id
JOIN dim_branch AS b ON b.branch_id = f.branch_id
GROUP BY c.customer_segment, b.branch_name
ORDER BY c.customer_segment, b.branch_name;

-- Q7. Our own question: which accounts have more money going out than coming in?
SELECT
    a.account_id,
    a.account_type,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE 0 END), 2) AS total_credits,
    ROUND(SUM(CASE WHEN f.transaction_type = 'DEBIT' THEN f.amount ELSE 0 END), 2) AS total_debits,
    ROUND(SUM(CASE WHEN f.transaction_type = 'CREDIT' THEN f.amount ELSE -f.amount END), 2) AS net_cash_flow
FROM fact_transaction AS f
JOIN dim_account AS a ON a.account_id = f.account_id
GROUP BY a.account_id, a.account_type
HAVING net_cash_flow < 0
ORDER BY net_cash_flow, a.account_id;