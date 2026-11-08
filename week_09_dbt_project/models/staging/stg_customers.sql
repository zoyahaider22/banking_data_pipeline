
SELECT
    CAST(customer_id AS VARCHAR) AS customer_id,
    TRIM(CAST(customer_name AS VARCHAR)) AS customer_name,
    TRIM(CAST(city AS VARCHAR)) AS city,
    TRIM(CAST(customer_segment AS VARCHAR)) AS customer_segment

FROM {{ ref('customers') }}
