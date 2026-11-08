
SELECT
    CAST(account_id AS VARCHAR) AS account_id,
    CAST(customer_id AS VARCHAR) AS customer_id,
    TRIM(CAST(account_type AS VARCHAR)) AS account_type,
    CAST(opened_date AS DATE) AS opened_date,
    UPPER(TRIM(CAST(account_status AS VARCHAR))) AS account_status

FROM {{ ref('accounts') }}
