-- 통합 products
CREATE TABLE products_all AS
SELECT * FROM products_001
UNION ALL
SELECT * FROM products_002
UNION ALL
SELECT * FROM products_003;

-- 통합 reviews
CREATE TABLE reviews_all AS
SELECT * FROM reviews_001
UNION ALL
SELECT * FROM reviews_002
UNION ALL
SELECT * FROM reviews_003;