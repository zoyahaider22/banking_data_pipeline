
SELECT
    transaction_id,
    amount

FROM {{ ref('transactions') }}

WHERE TRY_CAST(amount AS DECIMAL(18, 2)) < 0
